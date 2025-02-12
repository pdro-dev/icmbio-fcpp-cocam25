import streamlit as st
import sqlite3
import json
import pandas as pd

# 📌 Verifica se o usuário está logado antes de permitir acesso à página
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

st.set_page_config(
    page_title="Cadastro de Regras de Negócio",
    page_icon=":infinity:",
    layout="wide"
)

DB_PATH = "database/app_data.db"

# 📌 Função para recuperar iniciativas disponíveis para o usuário
def get_iniciativas_usuario(perfil, setor):
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT id_iniciativa, nome_iniciativa FROM td_iniciativas"
    
    if perfil != "admin":
        query += " WHERE id_iniciativa IN (SELECT id_iniciativa FROM tf_cadastros_iniciativas WHERE id_demandante = (SELECT id_demandante FROM td_demandantes WHERE nome_demandante = ?))"
        iniciativas = pd.read_sql_query(query, conn, params=[setor])
    else:
        iniciativas = pd.read_sql_query(query, conn)

    conn.close()
    return iniciativas


def carregar_dados_iniciativa(id_iniciativa):
    """Retorna a última versão dos dados da iniciativa cadastrada."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT * FROM tf_cadastro_regras_negocio 
        WHERE id_iniciativa = ? 
        ORDER BY data_hora DESC LIMIT 1
    """
    dados = pd.read_sql_query(query, conn, params=[id_iniciativa])
    conn.close()

    return dados.iloc[0] if not dados.empty else None


def carregar_resumo_iniciativa(setor):
    """Carrega o resumo da iniciativa a partir da tabela td_dados_resumos_sei filtrando apenas pelo setor demandante."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT * FROM td_dados_resumos_sei 
        WHERE demandante = ?
    """
    dados = pd.read_sql_query(query, conn, params=[setor])
    conn.close()
    return dados if not dados.empty else None



def salvar_dados_iniciativa(id_iniciativa, usuario, objetivo_geral, objetivos_especificos, eixos_tematicos, acoes_manejo, insumos):
    """Salva um novo registro de detalhamento da iniciativa, mantendo no máximo 3 registros no histórico."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Contar quantos registros já existem para essa iniciativa
    cursor.execute("SELECT COUNT(*) FROM tf_cadastro_regras_negocio WHERE id_iniciativa = ?", (id_iniciativa,))
    total_registros = cursor.fetchone()[0]

    # Se já houver 3 registros, apagar o mais antigo antes de inserir um novo
    if total_registros >= 3:
        cursor.execute("""
            DELETE FROM tf_cadastro_regras_negocio 
            WHERE id IN (
                SELECT id FROM tf_cadastro_regras_negocio 
                WHERE id_iniciativa = ? 
                ORDER BY data_hora ASC LIMIT 1
            )
        """, (id_iniciativa,))

    # Convertendo os dados para JSON
    objetivos_json = json.dumps(objetivos_especificos)
    eixos_json = json.dumps(eixos_tematicos)
    acoes_json = json.dumps(acoes_manejo)
    insumos_json = json.dumps(insumos)

    # Inserindo novo registro
    cursor.execute("""
        INSERT INTO tf_cadastro_regras_negocio 
        (id_iniciativa, usuario, objetivo_geral, objetivo_especifico, eixos_tematicos, acoes_manejo, insumos)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (id_iniciativa, usuario, objetivo_geral, objetivos_json, eixos_json, acoes_json, insumos_json))

    conn.commit()
    conn.close()


# 📌 Inicializa variáveis no session_state se ainda não existirem
if "edit_objetivo" not in st.session_state:
    st.session_state["edit_objetivo"] = None

# 📌 Seleção da Iniciativa
st.header("📝 Cadastro de Regras de Negócio")

st.divider()

perfil = st.session_state["perfil"]
setor = st.session_state["setor"]


st.subheader("Iniciativas Estruturantes", help="Iniciativas disponíveis para o usuário: filtro pelo setor demandante cadastrado com o perfil")

# 🔍 Obtendo as iniciativas disponíveis para o usuário
iniciativas = get_iniciativas_usuario(perfil, setor)

if iniciativas.empty:
    st.warning("🚫 Nenhuma iniciativa disponível para você.")
    st.stop()



nova_iniciativa = st.selectbox(
    "Selecione a Iniciativa:",
    options=iniciativas["id_iniciativa"],
    format_func=lambda x: iniciativas.set_index("id_iniciativa").loc[x, "nome_iniciativa"]
)

# 📌 Se o usuário mudar de iniciativa, reinicializar os dados armazenados na sessão
if "id_iniciativa_atual" not in st.session_state or st.session_state["id_iniciativa_atual"] != nova_iniciativa:
    st.session_state["id_iniciativa_atual"] = nova_iniciativa
    st.session_state["objetivos_especificos"] = []  # 🔥 Resetando os objetivos específicos



st.divider()

st.caption("Resumo Executivo da Iniciativa", help="ref.: documentos SEI")

# 📌 Função para tratar valores nulos do banco
def tratar_valor(valor):
    """ Substitui valores None ou 'NULL' por 'Sem Informação' """
    if pd.isna(valor) or valor is None or str(valor).strip().lower() == "null":
        return "(sem informação)"
    return str(valor).strip()

# 🔍 Carregar o resumo da iniciativa baseado no setor demandante
resumos = carregar_resumo_iniciativa(setor)

if resumos is not None:
    for _, resumo in resumos.iterrows():
        nome_iniciativa = tratar_valor(resumo.get("iniciativa", "Iniciativa Desconhecida"))

        with st.expander(f"📖 {nome_iniciativa}", expanded=False):
            st.divider()
            st.write(f"**🎯 Objetivo Geral:** {tratar_valor(resumo.get('objetivo_geral'))}")
            st.divider()
            st.write(f"**🏢 Diretoria:** {tratar_valor(resumo.get('diretoria'))}")
            st.write(f"**📌 Coordenação Geral:** {tratar_valor(resumo.get('coordenação_geral'))}")
            st.write(f"**🗂 Coordenação:** {tratar_valor(resumo.get('coordenação'))}")
            st.write(f"**📍 Demandante:** {tratar_valor(resumo.get('demandante'))}")
            st.divider()
            st.write(f"**📝 Introdução:** {tratar_valor(resumo.get('introdução'))}")
            st.divider()
            st.write(f"**💡 Justificativa:** {tratar_valor(resumo.get('justificativa'))}")
            st.divider()
            st.write(f"**🏞 Unidades de Conservação / Benefícios:** {tratar_valor(resumo.get('unidades_de_conservação_beneficiadas'))}")
            st.divider()
            st.write(f"**🔬 Metodologia:** {tratar_valor(resumo.get('metodologia'))}")



st.divider()

# 📌 Carregar dados da iniciativa selecionada
dados_iniciativa = carregar_dados_iniciativa(nova_iniciativa)


# 📌 Verificação e acesso aos dados corretamente
objetivo_geral = dados_iniciativa.get("objetivo_geral", "Sem Informação") if dados_iniciativa is not None else "Sem Informação"

# 📌 Campo de entrada do Objetivo Geral
st.subheader("🎯 Objetivo Geral", help="Declaração ampla e inspiradora do propósito macro a ser alcançado no longo prazo.")
objetivo_geral = st.text_area(
    "Descreva o Objetivo Geral da Iniciativa:",
    value=objetivo_geral,
    height=140,
    placeholder="Propósito macro a ser alcançado no longo prazo."
)

st.divider()

# 📌 Objetivos Específicos
st.subheader("🎯 Objetivos Específicos", help="Objetivos específicos são resultados concretos e mensuráveis que contribuem diretamente para o Objetivo Geral.")

if "objetivos_especificos" not in st.session_state or not st.session_state["objetivos_especificos"]:
    if dados_iniciativa is not None and not dados_iniciativa.empty:
        st.session_state["objetivos_especificos"] = json.loads(dados_iniciativa.get("objetivo_especifico", "[]"))
    else:
        st.session_state["objetivos_especificos"] = []

# 📌 Função para abrir o **dialog modal**
@st.dialog("📝 Editar Objetivo Específico", width="large")
def editar_objetivo_especifico(index):
    """Abre o modal de edição de um objetivo específico"""
    novo_texto = st.text_area("Edite o objetivo específico:", value=st.session_state["objetivos_especificos"][index], height=70)
    
    col1, col2 = st.columns(2)
    salvar = col1.button("💾 Salvar Alteração")
    cancelar = col2.button("❌ Cancelar")

    if salvar:
        st.session_state["objetivos_especificos"][index] = novo_texto
        st.rerun()

    if cancelar:
        st.rerun()


# 📌 Campo para adicionar novos objetivos específicos
novo_objetivo = st.text_area("Novo Objetivo Específico", height=70, placeholder="Resultados concretos e mensuráveis que contribuem diretamente para o Objetivo Geral.")

if st.button("➕ Adicionar Objetivo Específico"):
    if novo_objetivo:
        st.session_state["objetivos_especificos"].append(novo_objetivo)
        st.rerun()

# 📌 Expanders para exibir objetivos específicos com numeração e botão de exclusão
for i, objetivo in enumerate(st.session_state["objetivos_especificos"]):
    with st.expander(f"🎯 Obj. Específico {i + 1}: {objetivo}", expanded=False):
        # 📊 Estatísticas associadas ao objetivo (exemplo fictício)
        num_ucs = 5  # 🔥 Buscar do BD
        num_eixos = 3  # 🔥 Buscar do BD
        num_acoes = 8  # 🔥 Buscar do BD
        num_insumos = 12  # 🔥 Buscar do BD

        st.markdown(f"""
        **📍 Unidades de Conservação Associadas:** {num_ucs}  
        **🗂️ Eixos Temáticos:** {num_eixos}  
        **⚙️ Ações de Manejo Vinculadas:** {num_acoes}  
        **📦 Insumos Relacionados:** {num_insumos}  
        """)

        # 📌 Criando três colunas: uma grande (para espaçamento) e uma pequena para os botões
        col_space, col_buttons = st.columns([5, 1])

        # Botões alinhados à direita dentro da coluna pequena
        with col_buttons:
            if st.button("✏️ Editar", key=f"edit-{i}"):
                editar_objetivo_especifico(i)

            if st.button("❌ Remover", key=f"remove-{i}"):
                del st.session_state["objetivos_especificos"][i]
                st.rerun()

st.divider()

# 📌 Botão de salvar
if st.button("💾 Salvar Cadastro"):
    salvar_dados_iniciativa(
        nova_iniciativa,
        st.session_state["cpf"],
        objetivo_geral,
        st.session_state["objetivos_especificos"],
        [],  # Eixos Temáticos (placeholder)
        [],  # Ações de Manejo (placeholder)
        []   # Insumos (placeholder)
    )
    st.success("✅ Cadastro atualizado com sucesso!")

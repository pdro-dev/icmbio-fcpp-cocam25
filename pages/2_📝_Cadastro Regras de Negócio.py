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


##########################################################################################


st.divider()

# 📌 Objetivos Específicos
st.subheader("🎯 Objetivos Específicos", help="Objetivos específicos são resultados concretos e mensuráveis que contribuem diretamente para o Objetivo Geral.")

if "objetivos_especificos" not in st.session_state or not st.session_state["objetivos_especificos"]:
    if dados_iniciativa is not None and not dados_iniciativa.empty:
        st.session_state["objetivos_especificos"] = json.loads(dados_iniciativa.get("objetivo_especifico", "[]"))
    else:
        st.session_state["objetivos_especificos"] = []




def get_options_from_table(table_name, id_col, name_col, filter_col=None, filter_val=None):
    """Busca os valores de uma tabela e retorna um dicionário {id: nome}.
       Se filter_col e filter_val forem fornecidos, filtra os resultados.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = f"SELECT {id_col}, {name_col} FROM {table_name}"
    params = ()
    if filter_col and filter_val:
        query += f" WHERE {filter_col} = ?"
        params = (filter_val,)

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in results}

# 📌 Carregar opções do banco de dados com os nomes corretos
eixos_opcoes = get_options_from_table("td_samge_processos", "id_p", "nome")
insumos_opcoes = get_options_from_table("td_insumos", "id", "elemento_despesa")


# 📌 Modal de edição de objetivo específico
@st.dialog("📝 Editar Objetivo Específico", width="large")
def editar_objetivo_especifico(index):
    """Modal para editar um objetivo específico e seus relacionamentos"""

    if "detalhamento_objetivos" not in st.session_state:
        st.session_state["detalhamento_objetivos"] = {}

    # 📌 Garante que cada objetivo tenha um ID único
    if "objetivos_ids" not in st.session_state:
        st.session_state["objetivos_ids"] = {}

    if index not in st.session_state["objetivos_ids"]:
        st.session_state["objetivos_ids"][index] = index + 1  # Gera um ID sequencial

    id_objetivo = st.session_state["objetivos_ids"][index]
    objetivo = st.session_state["objetivos_especificos"][index]

    edit_mode = st.toggle("✏️ Editar Objetivo", key=f"toggle_edit_{index}")

    objetivo_editado = st.text_area(
        "Objetivo Específico:",
        value=objetivo,
        height=70,
        disabled=not edit_mode
    )

    if edit_mode and objetivo_editado != objetivo:
        st.session_state["objetivos_especificos"][index] = objetivo_editado

    st.divider()

    # 📌 Seção: Eixos Temáticos
    with st.expander("📂 Eixos Temáticos", expanded=True):
        if "eixos_tematicos" not in st.session_state:
            st.session_state["eixos_tematicos"] = {}

        eixos_selecionados = st.multiselect(
            "Selecione os Eixos Temáticos:",
            options=list(eixos_opcoes.keys()),
            format_func=lambda x: eixos_opcoes[x],
            key=f"eixos_{id_objetivo}"
        )

        if eixos_selecionados:
            st.session_state["eixos_tematicos"][id_objetivo] = {
                "eixos": eixos_selecionados,
                "acoes_manejo": {}
            }

    # 📌 Seção: Ações de Manejo (Filtradas pelo Eixo Temático)
    with st.expander("⚙️ Ações de Manejo", expanded=False):
        if id_objetivo in st.session_state["eixos_tematicos"]:
            eixos_selecionados = st.session_state["eixos_tematicos"][id_objetivo]["eixos"]
            eixo_acao_map = {}

            for eixo_id in eixos_selecionados:
                # 📌 Busca as ações de manejo associadas ao processo/eixo temático selecionado
                acoes_opcoes = get_options_from_table("td_samge_acoes_manejo", "id_ac", "nome", "processo_id", eixo_id)

                acoes_selecionadas = st.multiselect(
                    f"📌 Ações de Manejo para **{eixos_opcoes[eixo_id]}**:",
                    options=list(acoes_opcoes.keys()),
                    format_func=lambda x: acoes_opcoes[x],
                    key=f"acoes_{id_objetivo}_{eixo_id}"
                )
                
                if acoes_selecionadas:
                    eixo_acao_map[eixo_id] = acoes_selecionadas

            if eixo_acao_map:
                st.session_state["eixos_tematicos"][id_objetivo]["acoes_manejo"] = eixo_acao_map


    # 📌 Seção: Insumos
        with st.expander("📦 Insumos", expanded=False):
            insumo_map = {}
            for eixo in dados_objetivo.get("eixos_tematicos", []):
                eixo_id = eixo["id_eixo"]

                for acao in eixo.get("acoes_manejo", []):
                    acao_id = acao["id_acao"]

                    # 🔥 Verifica se a chave acao_id existe no dicionário antes de acessá-la
                    nome_acao = acoes_opcoes.get(acao_id, "Ação Não Encontrada")
                    nome_eixo = eixos_opcoes.get(eixo_id, "Eixo Não Encontrado")

                    insumos_selecionados = st.multiselect(
                        f"📌 Insumos para {nome_acao} ({nome_eixo}):",
                        options=list(insumos_opcoes.keys()),
                        format_func=lambda x: insumos_opcoes[x],
                        default=acao.get("insumos", []),
                        key=f"insumos_{id_objetivo}_{eixo_id}_{acao_id}"
                    )

                    acao["insumos"] = insumos_selecionados


            if insumo_map:
                st.session_state["eixos_tematicos"][id_objetivo]["insumos"] = insumo_map

    st.divider()

    # 📌 Botões de ação no modal
    col1, col2 = st.columns(2)
    salvar = col1.button("💾 Salvar Alteração", key=f"salvar_obj_{index}")
    cancelar = col2.button("❌ Cancelar", key=f"cancelar_obj_{index}")

    if salvar:
        st.session_state["objetivos_especificos"][index] = objetivo_editado
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
        # 📌 Criando três colunas: uma grande (para espaçamento) e uma pequena para os botões
        col_space, col_buttons = st.columns([10, 1])
        
        with col_space:
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

        

        # Botões alinhados à direita dentro da coluna pequena
        with col_buttons:
            if st.button("📝", key=f"edit-{i}", use_container_width=True):
                editar_objetivo_especifico(i)

            if st.button("❌", key=f"remove-{i}", use_container_width=True):
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

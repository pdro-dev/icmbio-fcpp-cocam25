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
    page_icon="📌",
    layout="wide"
)

DB_PATH = "database/app_data.db"

# 📌 Funções para recuperar os dados
def get_iniciativas_usuario(perfil, setor):
    """Retorna as iniciativas disponíveis para o usuário."""
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
    """Carrega os dados já cadastrados para uma iniciativa."""
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM tf_cadastro_regras_negocio WHERE id_iniciativa = ?"
    dados = pd.read_sql_query(query, conn, params=[id_iniciativa])
    conn.close()
    
    if dados.empty:
        return None
    return dados.iloc[0]


def salvar_dados_iniciativa(id_iniciativa, objetivo_geral, objetivos_especificos):
    """Salva ou atualiza os dados da iniciativa na tabela."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    objetivos_json = json.dumps(objetivos_especificos)

    cursor.execute("""
        INSERT INTO tf_cadastro_regras_negocio (id_iniciativa, objetivo_geral, objetivo_especifico)
        VALUES (?, ?, ?)
        ON CONFLICT(id_iniciativa) DO UPDATE SET 
            objetivo_geral = excluded.objetivo_geral,
            objetivo_especifico = excluded.objetivo_especifico
    """, (id_iniciativa, objetivo_geral, objetivos_json))

    conn.commit()
    conn.close()


# 📌 Inicializa variáveis no session_state se ainda não existirem
if "edit_objetivo" not in st.session_state:
    st.session_state["edit_objetivo"] = None

# 📌 Seleção da Iniciativa
st.title("📝 Cadastro de Regras de Negócio")

st.divider()

perfil = st.session_state["perfil"]
setor = st.session_state["setor"]

st.subheader("📌 Selecione uma Iniciativa")
iniciativas = get_iniciativas_usuario(perfil, setor)

if iniciativas.empty:
    st.warning("🚫 Nenhuma iniciativa disponível para você.")
    st.stop()

id_iniciativa = st.selectbox(
    "Escolha uma iniciativa:",
    options=iniciativas["id_iniciativa"],
    format_func=lambda x: iniciativas.set_index("id_iniciativa").loc[x, "nome_iniciativa"]
)

# 📌 Carregar dados da iniciativa
dados_iniciativa = carregar_dados_iniciativa(id_iniciativa)



# 📌 Campos de entrada
st.subheader("🎯 Objetivo Geral")
objetivo_geral = st.text_area(
    "Descreva o Objetivo Geral da Iniciativa:",
    value=dados_iniciativa["objetivo_geral"] if dados_iniciativa else "",
    height=140
)

st.divider()

st.subheader("🎯 Objetivos Específicos")

# 📌 Inicializa a variável na sessão se ainda não existir
if "objetivos_especificos" not in st.session_state:
    st.session_state["objetivos_especificos"] = json.loads(dados_iniciativa["objetivo_especifico"]) if dados_iniciativa else []


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
        st.session_state["edit_objetivo"] = None  # Define como None para evitar erro
        st.rerun()

    if cancelar:
        st.session_state["edit_objetivo"] = None  # Define como None para evitar erro
        st.rerun()


# 📌 Campo para adicionar novos objetivos específicos
novo_objetivo = st.text_area("Novo Objetivo Específico", height=70, placeholder="Digite um novo objetivo específico aqui...")

if st.button("➕ Adicionar Objetivo Específico"):
    if novo_objetivo:
        st.session_state["objetivos_especificos"].append(novo_objetivo)
        st.rerun()

# 📌 Expanders para exibir objetivos específicos
for i, objetivo in enumerate(st.session_state["objetivos_especificos"]):
    with st.expander(f"🎯 {objetivo}", expanded=False):
        col1, col2 = st.columns([5, 1])

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

        # Botão para abrir um **diálogo modal**
        if col2.button("✏️ Editar", key=f"edit-{i}"):
            st.session_state["edit_objetivo"] = i
            editar_objetivo_especifico(i)

st.divider()

# 📌 Botão de salvar
if st.button("💾 Salvar Cadastro"):
    salvar_dados_iniciativa(id_iniciativa, objetivo_geral, st.session_state["objetivos_especificos"])
    st.success("✅ Cadastro atualizado com sucesso!")

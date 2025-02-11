import streamlit as st
import sqlite3
import json
import pandas as pd


# 📌 Verifica se o usuário está logado antes de permitir acesso à página
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

st.set_page_config(
    page_title="Casdastrar Detalhamento",
    page_icon="♾️",
    layout="wide"
    )


# 📌 Conectar ao banco
DB_PATH = "database/app_data.db"


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


def salvar_dados_iniciativa(id_iniciativa, objetivo_geral, objetivos_especificos, eixos_tematicos):
    """Salva ou atualiza os dados da iniciativa na tabela."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    objetivos_json = json.dumps(objetivos_especificos)
    eixos_json = json.dumps(eixos_tematicos)

    cursor.execute("""
        INSERT INTO tf_cadastro_regras_negocio (id_iniciativa, objetivo_geral, objetivo_especifico, eixos_tematicos)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id_iniciativa) DO UPDATE SET 
            objetivo_geral = excluded.objetivo_geral,
            objetivo_especifico = excluded.objetivo_especifico,
            eixos_tematicos = excluded.eixos_tematicos
    """, (id_iniciativa, objetivo_geral, objetivos_json, eixos_json))

    conn.commit()
    conn.close()


# 📌 Verifica login
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login para acessar esta seção.")
    st.stop()

perfil = st.session_state["perfil"]
setor = st.session_state["setor"]

st.title("📝 Cadastro de Regras de Negócio")


# 📌 Seleção da Iniciativa
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
objetivo_geral = st.text_area("🎯 Objetivo Geral", value=dados_iniciativa["objetivo_geral"] if dados_iniciativa else "")

st.subheader("🎯 Objetivos Específicos")
objetivos_especificos = json.loads(dados_iniciativa["objetivo_especifico"]) if dados_iniciativa else []
novo_objetivo = st.text_input("Novo Objetivo Específico")
if st.button("➕ Adicionar Objetivo Específico"):
    if novo_objetivo:
        objetivos_especificos.append(novo_objetivo)
        st.rerun()

# 📌 Exibir os objetivos específicos já cadastrados
for i, objetivo in enumerate(objetivos_especificos):
    col1, col2 = st.columns([4, 1])
    col1.text_input(f"Objetivo {i+1}", value=objetivo, key=f"obj-{i}")
    if col2.button("❌ Remover", key=f"remover-{i}"):
        objetivos_especificos.pop(i)
        st.rerun()


# 📌 Eixos Temáticos
st.subheader("🗂️ Eixos Temáticos")
eixos_disponiveis = ["Conservação", "Educação Ambiental", "Gestão de Recursos", "Infraestrutura"]  # 🔥 Precisamos buscar do BD futuramente

eixos_tematicos = json.loads(dados_iniciativa["eixos_tematicos"]) if dados_iniciativa else []
novo_eixo = st.selectbox("Selecione um eixo temático:", [""] + eixos_disponiveis)
if st.button("➕ Adicionar Eixo Temático"):
    if novo_eixo and novo_eixo not in eixos_tematicos:
        eixos_tematicos.append(novo_eixo)
        st.experimental_rerun()

# 📌 Exibir eixos temáticos já cadastrados
for i, eixo in enumerate(eixos_tematicos):
    col1, col2 = st.columns([4, 1])
    col1.text_input(f"Eixo {i+1}", value=eixo, key=f"eixo-{i}", disabled=True)
    if col2.button("❌ Remover", key=f"remover-eixo-{i}"):
        eixos_tematicos.pop(i)
        st.experimental_rerun()

# 📌 Botão de salvar
if st.button("💾 Salvar Cadastro"):
    salvar_dados_iniciativa(id_iniciativa, objetivo_geral, objetivos_especificos, eixos_tematicos)
    st.success("✅ Cadastro atualizado com sucesso!")


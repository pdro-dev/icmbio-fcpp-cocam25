import streamlit as st
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


@st.cache_data
def load_data():
    return pd.read_json("dados/base_iniciativas_consolidada.json")

df = load_data()

if st.session_state["perfil"] == "admin":
    df_filtrado = df  # Admin vê todos os registros
    df = df_filtrado
else:
    df_filtrado = df[df["DEMANDANTE"] == st.session_state["setor"]]
    df = df_filtrado


st.title("Cadastro de Detalhamento")

iniciativa = st.selectbox("Escolha uma iniciativa", df["Nome da Proposta/Iniciativa Estruturante"].unique())
detalhes = st.text_area("Detalhamento do Projeto")

if st.button("Salvar Detalhamento"):
    st.success("Detalhamento salvo com sucesso!")

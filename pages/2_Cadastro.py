import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    return pd.read_json("dados/base_iniciativas_consolidada.json")

df = load_data()

st.title("Cadastro de Detalhamento")

iniciativa = st.selectbox("Escolha uma iniciativa", df["Nome da Proposta/Iniciativa Estruturante"].unique())
detalhes = st.text_area("Detalhamento do Projeto")

if st.button("Salvar Detalhamento"):
    st.success("Detalhamento salvo com sucesso!")

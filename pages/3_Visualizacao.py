import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    return pd.read_json("dados/base_iniciativas_consolidada.json")

df = load_data()

st.title("Visualização de Detalhamentos")

iniciativa = st.selectbox("Escolha uma iniciativa", df["Nome da Proposta/Iniciativa Estruturante"].unique())

st.subheader(f"Detalhes da iniciativa: {iniciativa}")
st.write("Aqui serão exibidos os detalhes cadastrados.")

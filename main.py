import streamlit as st
import pandas as pd

# Carregar os dados
@st.cache_data
def load_data():
    return pd.read_json("dados/base_iniciativas_consolidada.json")

df = load_data()

# Configurar o menu lateral
st.sidebar.title("Menu")
page = st.sidebar.radio("Navegação", ["Consulta", "Cadastro de Detalhamento", "Visualização"])

if page == "Consulta":
    st.title("Consulta de Iniciativas Estruturantes")
    st.dataframe(df)

elif page == "Cadastro de Detalhamento":
    st.title("Cadastro de Detalhamento")
    iniciativa = st.selectbox("Escolha uma iniciativa", df["Nome da Proposta/Iniciativa Estruturante"].unique())
    detalhes = st.text_area("Detalhamento do Projeto")
    if st.button("Salvar Detalhamento"):
        st.success("Detalhamento salvo com sucesso!")

elif page == "Visualização":
    st.title("Visualização de Detalhamentos")
    iniciativa = st.selectbox("Escolha uma iniciativa", df["Nome da Proposta/Iniciativa Estruturante"].unique())
    st.subheader(f"Detalhes da iniciativa: {iniciativa}")
    st.write("(Exibir detalhes cadastrados aqui)")


import streamlit as st
import os

# Importe a função de inicialização
from init_db import init_database

# Caminho onde o DB será criado
db_path = "database/app_data.db"

# Verifica se o banco já existe. Caso não exista, cria.
if not os.path.exists(db_path):
    init_database()


    

st.set_page_config(page_title="Gestão de Recursos", layout="wide")

st.markdown(
    """
    # SAMGePlan

    ### Cadastro de Instrumentos e Projetos 
    *Construção de Regras de Negócio (financeiro | insumos)*

    ---

    👉 **Use o menu lateral para acessar as diferentes funcionalidades.**
    """
)

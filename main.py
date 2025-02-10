import streamlit as st
import os

# Importe a função de inicialização
from init_db import init_database

# Caminho onde o DB será criado
db_path = "database/app_data.db"

# Verifica se o banco já existe. Caso não exista, cria.
if not os.path.exists(db_path):
    init_database()




st.set_page_config(page_title="SAMGePlan (v.0)", layout="wide")




st.markdown(
    """
    # SAMGePlan

    ### Cadastro de Instrumentos e Projetos 
    *Construção de Regras de Negócio (financeiro | insumos)*

    ---

    #### Planejamento Compensação Ambiental - FCA 2025
    *Iniciativas Estruturantes - Coordenações Gerais*

    ---

    **⬅** **Use o menu lateral para acessar as diferentes funcionalidades.**

    """
)


# st.markdown("""
#     <svg width="30" height="30" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
#       <path d="M15 6L9 12L15 18" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
#     </svg>
#     <b>Use o menu lateral para acessar as diferentes funcionalidades.</b>
# """, unsafe_allow_html=True)
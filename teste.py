import streamlit as st
import pandas as pd
import sqlite3
import os

# Supondo que seu arquivo init_db.py esteja no mesmo diretório ou em um módulo importável
from init_db import init_database

st.title("Teste de Consulta SQLite")

# Verifica se o arquivo do DB existe
db_path = "database/app_data.db"
st.write("Arquivo app_data.db existe?", os.path.exists(db_path))

# Função para ler dados do banco
@st.cache_data
def load_data_from_db():
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM cadastros_iniciais", conn)
    conn.close()
    return df

# Botão para RECRIAR/Reiniciar o banco
if st.button("Recriar Banco de Dados"):
    # Se existir, remove o arquivo
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Chama a função init_database() do seu script init_db.py
    try:
        init_database()  # recria o banco a partir do JSON
        st.success("Banco de dados recriado com sucesso!")
        # Podemos forçar a reexecução para atualizar a interface
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao recriar o banco: {e}")

# Se o banco existir, tenta carregar e exibir os dados
if os.path.exists(db_path):
    try:
        df = load_data_from_db()
        st.dataframe(df)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
else:
    st.warning("Banco de dados não encontrado. Verifique se executou o init_db.py.")

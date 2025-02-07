import streamlit as st
import pandas as pd
import sqlite3

def load_data_from_db():
    conn = sqlite3.connect("database/app_data.db")
    df = pd.read_sql_query("SELECT * FROM cadastros_iniciais", conn)
    conn.close()
    return df

def app():
    st.title("Visualização de Detalhamentos")

    df = load_data_from_db()

    # Filtra pelo nome do demandante, por exemplo
    demandantes = df["DEMANDANTE"].unique()
    demanda_selecionada = st.selectbox("Escolha um demandante", demandantes)

    df_filtrado = df[df["DEMANDANTE"] == demanda_selecionada]
    st.write(df_filtrado)

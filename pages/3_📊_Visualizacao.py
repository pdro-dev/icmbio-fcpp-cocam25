import streamlit as st
import pandas as pd
import psycopg2

# 📌 Verifica se o usuário está logado antes de permitir acesso à página
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

def get_connection():
    return psycopg2.connect(
        host="10.197.42.64",
        database="teste",
        user="postgres",
        password="asd"
    )

def load_data_from_db():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM tf_cadastros_iniciativas", conn)
    conn.close()
    return df

def app():
    st.title("Visualização de Detalhamentos")

    df = load_data_from_db()

    if st.session_state["perfil"] == "admin":
        df_filtrado = df  # Admin vê todos os registros
    else:
        df_filtrado = df[df["DEMANDANTE"] == st.session_state["setor"]]

    # Filtra pelo nome do demandante, por exemplo
    demandantes = df_filtrado["DEMANDANTE"].unique()
    demanda_selecionada = st.selectbox("Escolha um demandante", demandantes)

    df_filtrado = df_filtrado[df_filtrado["DEMANDANTE"] == demanda_selecionada]
    st.write(df_filtrado)
    st.write(st.session_state)

app()

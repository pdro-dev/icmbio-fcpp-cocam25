import streamlit as st
import os
import psycopg2
import json
import pandas as pd

# Como o banco agora é online (PostgreSQL), não usamos mais o init_db
# e a variável db_path não é necessária.
# Se desejar, você pode desativar a opção de recriar o banco.

# -----------------------------------------------------------------------------
#                     Função para conexão com o PostgreSQL
# -----------------------------------------------------------------------------
def get_connection():
    return psycopg2.connect(
        host="10.197.42.64",
        database="teste",
        user="postgres",
        password="asd"
    )

# -----------------------------------------------------------------------------
#                     Configuração da Página
# -----------------------------------------------------------------------------
st.set_page_config(page_title="🔬 Testes & Configurações", page_icon="⚙️", layout="wide")
st.title("🔬 Página de Testes e Configurações")

# -----------------------------------------------------------------------------
#                     Verificação de Login e Permissão
# -----------------------------------------------------------------------------
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

perfil = st.session_state.get("perfil", "comum")
# Como não usamos um arquivo local, removemos a variável db_path.

st.sidebar.subheader("⚙️ Configurações")

# -----------------------------------------------------------------------------
# Para ambiente online, a opção de recriar o banco não se aplica.
with st.sidebar.expander("🛠 Opções Avançadas", expanded=False):
    st.info("A recriação do banco não é permitida neste ambiente online.")
    if st.button("🗑 Limpar Cache"):
        st.cache_data.clear()
        st.success("✅ Cache limpo com sucesso!")
        st.rerun()
    # Exibe toggle para "Itens Omissos na Soma"
    exibir_itens_omissos = st.checkbox("🔎 Exibir Itens Omissos na Soma", value=False)

# -----------------------------------------------------------------------------
# Área de Testes para Variáveis e Componentes
st.header("🛠 Testes de Variáveis & Componentes")

# Teste de variável: usa a variável de sessão "id_iniciativa_atual" ou 0
nova_iniciativa = st.session_state["id_iniciativa_atual"] if "id_iniciativa_atual" in st.session_state else 0

# Primeiro teste: executar uma query simples via cursor
conn = get_connection()
cursor = conn.cursor()
cursor.execute("""
    SELECT objetivo_geral
    FROM td_dados_resumos_sei
    WHERE id_resumo = %s
    LIMIT 1
""", (nova_iniciativa,))
row_resumo = cursor.fetchone()
cursor.close()
conn.close()
st.write("DEBUG row_resumo:", row_resumo)

# Segundo teste: executar outra query para depuração
conn = get_connection()
cursor = conn.cursor()
cursor.execute("""
    SELECT id_resumo, objetivo_geral
    FROM td_dados_resumos_sei
    WHERE id_resumo = %s
    LIMIT 1
""", (nova_iniciativa,))
row_resumo = cursor.fetchone()
cursor.close()
conn.close()
st.write("DEBUG row_resumo:", row_resumo)
st.write("DEBUG nova_iniciativa:", nova_iniciativa)

st.success("🚀 Testes finalizados! Ajuste os componentes conforme necessário.")

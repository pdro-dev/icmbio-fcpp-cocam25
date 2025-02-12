import streamlit as st
import os
import sqlite3
from init_db import init_database, init_samge_database  # Importa as funções de inicialização do banco


# 📌 Configuração da Página
st.set_page_config(page_title="🔬 Testes & Configurações", page_icon="⚙️", layout="wide")

st.title("🔬 Página de Testes e Configurações")

# 📌 Verifica se o usuário está logado e tem permissão
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

perfil = st.session_state.get("perfil", "comum")
db_path = "database/app_data.db"

st.sidebar.subheader("⚙️ Configurações")

# 📌 Verifica se o usuário logado é ADMIN para exibir opções avançadas
# if perfil == "admin":
if True:
    with st.sidebar.expander("🛠 Opções Avançadas", expanded=False):
        # 🔄 Botão para recriar o banco de dados
        if st.button("🔄 Recriar Banco de Dados"):
            if os.path.exists(db_path):
                os.remove(db_path)
            try:
                init_database()
                init_samge_database()
                st.success("✅ Banco de dados recriado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao recriar o banco: {e}")

        # 🗑 Botão para limpar cache
        if st.button("🗑 Limpar Cache"):
            st.cache_data.clear()
            st.success("✅ Cache limpo com sucesso!")
            st.rerun()

        # 🔎 Toggle para exibir ou não "Itens Omissos na Soma"
        exibir_itens_omissos = st.checkbox("🔎 Exibir Itens Omissos na Soma", value=False)

# 📌 Área de Testes para Variáveis e Componentes
st.header("🛠 Testes de Variáveis & Componentes")







# # 🎯 Testando uma variável de sessão
# if "teste_variavel" not in st.session_state:
#     st.session_state["teste_variavel"] = 0

# col1, col2 = st.columns(2)
# with col1:
#     st.metric("📊 Valor da Variável de Teste", st.session_state["teste_variavel"])
# with col2:
#     if st.button("➕ Incrementar"):
#         st.session_state["teste_variavel"] += 1
#         st.rerun()
#     if st.button("➖ Decrementar"):
#         st.session_state["teste_variavel"] -= 1
#         st.rerun()

# # 📌 Testando um input de texto
# st.subheader("📝 Entrada de Texto")
# texto_teste = st.text_input("Digite algo:", value="Teste de entrada")

# # 📌 Testando um selectbox com opções dinâmicas
# st.subheader("📌 Seleção de Opções")
# opcoes_teste = ["Opção 1", "Opção 2", "Opção 3"]
# selecao = st.selectbox("Escolha uma opção:", opcoes_teste)

# # 📌 Testando exibição de DataFrame (Tabela Fictícia)
# st.subheader("📊 Teste de DataFrame")
# import pandas as pd
# df_teste = pd.DataFrame({
#     "Coluna A": [1, 2, 3, 4, 5],
#     "Coluna B": ["A", "B", "C", "D", "E"],
#     "Valor": [100, 200, 300, 400, 500]
# })
# st.dataframe(df_teste)

# # 📌 Testando um gráfico simples
# st.subheader("📈 Teste de Gráfico")
# import matplotlib.pyplot as plt  

# fig, ax = plt.subplots()
# ax.plot(df_teste["Coluna A"], df_teste["Valor"], marker="o", linestyle="-", color="blue")
# ax.set_title("Gráfico de Teste")
# ax.set_xlabel("Eixo X")
# ax.set_ylabel("Eixo Y")
# st.pyplot(fig)

st.success("🚀 Testes finalizados! Ajuste os componentes conforme necessário.")

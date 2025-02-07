import streamlit as st
import pandas as pd
import sqlite3
import os

from init_db import init_database

db_path = "database/app_data.db"

st.title("Consulta de Iniciativas Registradas")

@st.cache_data
def load_data_from_db():
    """Carrega os dados da tabela 'cadastros_iniciais' do SQLite."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM cadastros_iniciais", conn)
    conn.close()
    return df

# Botão para recriar o banco de dados
if st.button("Recriar Banco de Dados"):
    if os.path.exists(db_path):
        os.remove(db_path)
    try:
        init_database()
        st.success("Banco de dados recriado com sucesso!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao recriar o banco: {e}")

# Botão para limpar o cache
if st.button("Limpar Cache"):
    st.cache_data.clear()
    st.success("Cache limpo com sucesso!")
    st.rerun()

# Verifica se o banco de dados existe antes de continuar
if not os.path.exists(db_path):
    st.warning("Banco de dados não encontrado. Verifique se executou o init_db.py.")
else:
    try:
        df = load_data_from_db()

        if df.empty:
            st.warning("Nenhum dado encontrado no banco de dados.")
        else:
            # 📌 Layout para Filtros: Título + Botão "Limpar Filtros"
            col1, col2 = st.sidebar.columns([3, 1])
            col1.header("Filtros")

            # Botão Limpar Filtros
            with col2:
                if st.button("🧹", help="Limpar Filtros"):
                    st.session_state.clear()
                    st.rerun()

            # 📊 Estatísticas Dinâmicas dentro de Expanders
            with st.expander("📊 Estatísticas Gerais", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("📌 Total de Iniciativas", df["Nome da Proposta/Iniciativa Estruturante"].nunique())
                col2.metric("🏞 Total de UCs", df["Unidade de Conservação"].nunique())
                col3.metric("💰 Valor Alocado", f"R$ {df['VALOR TOTAL ALOCADO'].astype(float).sum():,.2f}")
                col4.metric("💰 Valor Total da Iniciativa", f"R$ {df['Valor Total da Iniciativa'].astype(float).sum():,.2f}")

                # Ajuste na fonte para melhor visualização
                st.markdown(
                    """
                    <style>
                    div[data-testid="stMetricValue"] {
                        font-size: 20px !important;
                        font-weight: bold;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )

            # Estatísticas por Gerência Regional com Totais
            with st.expander("📌 Estatísticas por Gerência Regional"):
                gr_stats = df.groupby("GR").agg({
                    "Nome da Proposta/Iniciativa Estruturante": "nunique",
                    "Unidade de Conservação": "nunique",
                    "VALOR TOTAL ALOCADO": lambda x: x.astype(float).sum(),
                    "Valor Total da Iniciativa": lambda x: x.astype(float).sum()
                }).rename(columns={
                    "Nome da Proposta/Iniciativa Estruturante": "Total de Iniciativas",
                    "Unidade de Conservação": "Total de UCs"
                }).reset_index()

                # Adicionando a linha de totais
                total_row = pd.DataFrame({
                    "GR": ["Total Geral"],
                    "Total de Iniciativas": [gr_stats["Total de Iniciativas"].sum()],
                    "Total de UCs": [gr_stats["Total de UCs"].sum()],
                    "VALOR TOTAL ALOCADO": [gr_stats["VALOR TOTAL ALOCADO"].sum()],
                    "Valor Total da Iniciativa": [gr_stats["Valor Total da Iniciativa"].sum()]
                })

                gr_stats = pd.concat([gr_stats, total_row], ignore_index=True)

                # Ajuste para largura total
                st.dataframe(gr_stats.style.format({
                    "VALOR TOTAL ALOCADO": "R$ {:,.2f}",
                    "Valor Total da Iniciativa": "R$ {:,.2f}"
                }), use_container_width=True)

            # Estatísticas por Bioma com Totais
            with st.expander("🌱 Estatísticas por Bioma"):
                bioma_stats = df.groupby("BIOMA").agg({
                    "Nome da Proposta/Iniciativa Estruturante": "nunique",
                    "Unidade de Conservação": "nunique",
                    "VALOR TOTAL ALOCADO": lambda x: x.astype(float).sum(),
                    "Valor Total da Iniciativa": lambda x: x.astype(float).sum()
                }).rename(columns={
                    "Nome da Proposta/Iniciativa Estruturante": "Total de Iniciativas",
                    "Unidade de Conservação": "Total de UCs"
                }).reset_index()

                # Adicionando a linha de totais
                total_bioma_row = pd.DataFrame({
                    "BIOMA": ["Total Geral"],
                    "Total de Iniciativas": [bioma_stats["Total de Iniciativas"].sum()],
                    "Total de UCs": [bioma_stats["Total de UCs"].sum()],
                    "VALOR TOTAL ALOCADO": [bioma_stats["VALOR TOTAL ALOCADO"].sum()],
                    "Valor Total da Iniciativa": [bioma_stats["Valor Total da Iniciativa"].sum()]
                })

                bioma_stats = pd.concat([bioma_stats, total_bioma_row], ignore_index=True)

                # Ajuste para largura total
                st.dataframe(bioma_stats.style.format({
                    "VALOR TOTAL ALOCADO": "R$ {:,.2f}",
                    "Valor Total da Iniciativa": "R$ {:,.2f}"
                }), use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")

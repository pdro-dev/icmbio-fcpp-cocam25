import streamlit as st
import pandas as pd
import sqlite3
import os

from init_db import init_database

db_path = "database/app_data.db"

st.subheader("Informações sobre as Iniciativas Estruturantes")

@st.cache_data
def load_data_from_db():
    """Carrega os dados da tabela 'cadastros_iniciais' do SQLite."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM cadastros_iniciais", conn)
    conn.close()
    return df

# 📌 Verifica se o banco de dados existe antes de continuar
if not os.path.exists(db_path):
    st.warning("Banco de dados não encontrado. Verifique se executou o init_db.py.")
else:
    df = load_data_from_db()  # ⬅️ Agora `df` é carregado antes dos filtros

    if df.empty:
        st.warning("Nenhum dado encontrado no banco de dados.")
    else:
        # 📌 Layout para Filtros: Título + Botão "Limpar Filtros" ao lado
        col1, col2 = st.sidebar.columns([3, 1])
        col1.header("Filtros")

        with col2:
            st.markdown(
                """
                <style>
                div.stButton > button {
                    width: 100%;
                    padding: 5px 10px;
                    font-size: 12px;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            if st.button("🧹", help="Limpar Filtros"):
                # Resetando os filtros para "Todos"
                st.session_state["filtro_demandante"] = "Todos"
                st.session_state["filtro_uc"] = "Todas"
                st.session_state["filtro_gr"] = "Todos"
                st.session_state["filtro_uf"] = "Todas"
                st.session_state["filtro_bioma"] = "Todos"
                st.session_state["filtro_categoria"] = "Todas"
                st.session_state["iniciativa_selecionada"] = "Selecione uma opção..."
                st.rerun()

        # 📌 Aplicação de Filtros no Menu Lateral
        filtro_demandante = st.sidebar.selectbox("📌 Demandante", ["Todos"] + sorted(df["DEMANDANTE"].dropna().unique().tolist()), key="filtro_demandante")
        if filtro_demandante != "Todos":
            df = df[df["DEMANDANTE"] == filtro_demandante]

        filtro_uc = st.sidebar.selectbox("🏞 Unidade de Conservação", ["Todas"] + sorted(df["Unidade de Conservação"].dropna().unique().tolist()), key="filtro_uc")
        if filtro_uc != "Todas":
            df = df[df["Unidade de Conservação"] == filtro_uc]

        filtro_gr = st.sidebar.selectbox("🏢 Gerência Regional", ["Todos"] + sorted(df["GR"].dropna().unique().tolist()), key="filtro_gr")
        if filtro_gr != "Todos":
            df = df[df["GR"] == filtro_gr]

        filtro_uf = st.sidebar.selectbox("📍 UF (Estado)", ["Todas"] + sorted(df["UF"].dropna().unique().tolist()), key="filtro_uf")
        if filtro_uf != "Todas":
            df = df[df["UF"] == filtro_uf]

        filtro_bioma = st.sidebar.selectbox("🌱 Bioma", ["Todos"] + sorted(df["BIOMA"].dropna().unique().tolist()), key="filtro_bioma")
        if filtro_bioma != "Todos":
            df = df[df["BIOMA"] == filtro_bioma]

        filtro_categoria = st.sidebar.selectbox("🏷 Categoria UC", ["Todas"] + sorted(df["CATEGORIA UC"].dropna().unique().tolist()), key="filtro_categoria")
        if filtro_categoria != "Todas":
            df = df[df["CATEGORIA UC"] == filtro_categoria]

        # 📌 Expander de Configurações (agora no final)
        with st.sidebar.expander("⚙️ Configurações", expanded=False):
            if st.button("🔄 Recriar Banco de Dados"):
                if os.path.exists(db_path):
                    os.remove(db_path)
                try:
                    init_database()
                    st.success("Banco de dados recriado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao recriar o banco: {e}")

            if st.button("🗑 Limpar Cache"):
                st.cache_data.clear()
                st.success("Cache limpo com sucesso!")
                st.rerun()

            # ✅ Toggle para ativar/desativar a exibição de "Itens Omissos na Soma"
            exibir_itens_omissos = st.checkbox("🔎 Exibir Itens Omissos na Soma", value=False)

        # 📊 Estatísticas Dinâmicas dentro de Expanders
        with st.expander("📊 Estatísticas Gerais", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📌 Total de Iniciativas", df["Nome da Proposta/Iniciativa Estruturante"].nunique())
            col2.metric("🏞 Total de UCs", df["Unidade de Conservação"].nunique())
            col3.metric("💰 Valor Alocado", f"R$ {df['VALOR TOTAL ALOCADO'].astype(float).sum():,.2f}")
            col4.metric("💰 Valor Total da Iniciativa", f"R$ {df['Valor Total da Iniciativa'].astype(float).sum():,.2f}")

            st.markdown(
                """
                <style>
                div[data-testid="stMetricValue"] {
                    font-size: 16px !important;
                    font-weight: bold;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

        # 📌 Função para Destacar Totais na Tabela e Identificar Itens Omissos
        def destacar_totais(df, coluna_grupo):
            df_total = df.groupby(coluna_grupo).agg({
                "Nome da Proposta/Iniciativa Estruturante": "nunique",
                "Unidade de Conservação": "nunique",
                "VALOR TOTAL ALOCADO": lambda x: x.astype(float).sum(),
                "Valor Total da Iniciativa": lambda x: x.astype(float).sum()
            }).rename(columns={
                "Nome da Proposta/Iniciativa Estruturante": "Total de Iniciativas",
                "Unidade de Conservação": "Total de UCs"
            }).reset_index()

            total_geral = pd.DataFrame({
                coluna_grupo: ["Total Geral"],
                "Total de Iniciativas": [df_total["Total de Iniciativas"].sum()],
                "Total de UCs": [df_total["Total de UCs"].sum()],
                "VALOR TOTAL ALOCADO": [df_total["VALOR TOTAL ALOCADO"].sum()],
                "Valor Total da Iniciativa": [df_total["Valor Total da Iniciativa"].sum()]
            })

            df_total = pd.concat([df_total, total_geral], ignore_index=True)

            # 🔎 Identificando Registros que Estão Fora da Soma
            soma_agregada = df_total[df_total[coluna_grupo] == "Total Geral"]["VALOR TOTAL ALOCADO"].values[0]
            soma_total_real = df["VALOR TOTAL ALOCADO"].astype(float).sum()

            itens_omissos = df[df["VALOR TOTAL ALOCADO"].astype(float) + df["Valor Total da Iniciativa"].astype(float) == 0]

            return df_total.style.format({
                "VALOR TOTAL ALOCADO": "R$ {:,.2f}",
                "Valor Total da Iniciativa": "R$ {:,.2f}"
            }).apply(lambda x: ['background-color: #D3D3D3 ; color: #000000' if x.name == len(df_total) - 1 else '' for _ in x], axis=1), itens_omissos


        # 📊 Estatísticas Agregadas
        for nome, coluna in [
            ("📌 Estatísticas por Demandante", "DEMANDANTE"),
            ("📌 Estatísticas por Iniciativa", "Nome da Proposta/Iniciativa Estruturante"),
            ("🏞 Estatísticas por Unidade de Conservação", "Unidade de Conservação"),
            ("🏢 Estatísticas por Gerência Regional", "GR"),
            ("🌱 Estatísticas por Bioma", "BIOMA"),
            ("🏷 Estatísticas por Categoria UC", "CATEGORIA UC"),
            ("📍 Estatísticas por UF", "UF"),
        ]:
            with st.expander(nome):
                df_agregado, itens_fora = destacar_totais(df, coluna)
                st.dataframe(df_agregado, use_container_width=True)

                # ✅ Exibir Itens Omissos somente se o toggle estiver ativado
                if exibir_itens_omissos and not itens_fora.empty:
                    st.subheader(f"🔎 Itens Omissos na Soma - {coluna}")
                    st.dataframe(itens_fora, use_container_width=True)


        # 📌 Seção de visualização detalhada da iniciativa selecionada
        st.divider()
        
        # 📌 Seção de visualização detalhada da iniciativa selecionada
        st.subheader("📋 Resumo Executivo da Iniciativa")

        iniciativa_selecionada = st.selectbox(
            "Selecione uma iniciativa:", 
            ["Selecione uma opção..."] + df["Nome da Proposta/Iniciativa Estruturante"].dropna().unique().tolist()
        )

        # Filtra apenas se uma iniciativa for selecionada
        if iniciativa_selecionada != "Selecione uma opção...":
            df_iniciativa = df[df["Nome da Proposta/Iniciativa Estruturante"] == iniciativa_selecionada]


        df_iniciativa = df[df["Nome da Proposta/Iniciativa Estruturante"] == iniciativa_selecionada]

        if not df_iniciativa.empty:
            demandante = df_iniciativa["DEMANDANTE"].iloc[0]
            gr_list = sorted(df_iniciativa["GR"].unique())
            bioma_list = sorted(df_iniciativa["BIOMA"].unique())
            uf_list = sorted(df_iniciativa["UF"].unique())
            valor_total_alocado = df_iniciativa["VALOR TOTAL ALOCADO"].sum()
            valor_total_iniciativa = df_iniciativa["Valor Total da Iniciativa"].sum()

            unidades = df_iniciativa[["Unidade de Conservação", "VALOR TOTAL ALOCADO", "Valor Total da Iniciativa"]]

            # 📌 Layout do relatório
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### 📌 Informações Gerais")
                st.markdown(f"**📌 Demandante:** {demandante}")

                # 📌 Exibição compacta de listas com tags estilizadas
                st.markdown("**📍 Gerências Regionais:**", unsafe_allow_html=True)
                st.markdown(" ".join([f"<span class='tag'>{gr}</span>" for gr in gr_list]), unsafe_allow_html=True)

                st.markdown("**🌿 Biomas:**", unsafe_allow_html=True)
                st.markdown(" ".join([f"<span class='tag'>{bioma}</span>" for bioma in bioma_list]), unsafe_allow_html=True)

                st.markdown("**📍 UFs:**", unsafe_allow_html=True)
                st.markdown(" ".join([f"<span class='tag'>{uf}</span>" for uf in uf_list]), unsafe_allow_html=True)

            with col2:
                st.markdown("#### 📊 Valores Financeiros")
                st.metric(label="💰 Valor Total Alocado", value=f"R$ {valor_total_alocado:,.2f}")
                st.metric(label="🏗 Valor Total da Iniciativa", value=f"R$ {valor_total_iniciativa:,.2f}")
                st.divider()

                # 📌 Tabela de Estatísticas dentro da mesma coluna
                st.markdown("##### 📊 Estatísticas da Iniciativa")
                uc_list = sorted(df_iniciativa["Unidade de Conservação"].unique())

                estatisticas = pd.DataFrame({
                    "Indicador": ["Gerências Regionais", "Unidades de Conservação", "Biomas", "UFs"],
                    "Quantidade": [len(gr_list), len(uc_list), len(bioma_list), len(uf_list)]
                })

                # Aplicando um estilo mais compacto
                st.dataframe(
                    estatisticas.style.set_properties(**{
                        "border": "1px solid #444",
                        "font-size": "10px"
                    }),
                    hide_index=True,
                    use_container_width=True
                )


            # 📌 Tabelas de Unidades de Conservação
            st.markdown("#### 🌍 Unidades de Conservação e Valores")

            unidades_alocadas = unidades[unidades["VALOR TOTAL ALOCADO"] > 0]
            unidades_iniciativa = unidades[unidades["Valor Total da Iniciativa"] > 0]

            # 📌 Expander para "Valores Alocados"
            with st.expander("💰 Valores Alocados", expanded=False):
                st.dataframe(
                    unidades_alocadas.rename(columns={"VALOR TOTAL ALOCADO": "Valor Alocado (R$)"}),
                    hide_index=True,
                    use_container_width=True
                )

            # 📌 Expander para "Valores da Iniciativa"
            with st.expander("💰 Valores da Iniciativa", expanded=False):
                st.dataframe(
                    unidades_iniciativa.rename(columns={"Valor Total da Iniciativa": "Valor da Iniciativa (R$)"}),
                    hide_index=True,
                    use_container_width=True
                )


        # 📌 CSS para as tags minimalistas
        st.markdown("""
            <style>
            .tag {
                display: inline-block;
                background-color: #2c3e50;
                color: white;
                padding: 5px 10px;
                margin: 3px;
                border-radius: 12px;
                font-size: 12px;
            }
            </style>
            """, unsafe_allow_html=True)
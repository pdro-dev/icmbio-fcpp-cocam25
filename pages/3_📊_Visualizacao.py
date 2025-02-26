import streamlit as st
import pandas as pd
import sqlite3

# Verifica se o usuário está logado
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

def load_data_from_db():
    conn = sqlite3.connect("database/app_data.db")
    df = pd.read_sql_query("SELECT * FROM tf_cadastros_iniciativas", conn)
    conn.close()
    return df

def app():
    st.title("Visualização de Detalhamentos")

    df = load_data_from_db()

    # Filtragem conforme perfil do usuário
    if st.session_state["perfil"] == "admin":
        df_filtrado = df
    else:
        df_filtrado = df[df["DEMANDANTE"] == st.session_state["setor"]]

    # Filtro pelo nome do demandante
    demandantes = df_filtrado["DEMANDANTE"].unique()
    demanda_selecionada = st.selectbox("Escolha um demandante", demandantes)
    df_filtrado = df_filtrado[df_filtrado["DEMANDANTE"] == demanda_selecionada]

    # Ajuste de tamanho da fonte
    font_size = st.slider("Tamanho da fonte (px)", min_value=10, max_value=24, value=14)

    # Ajuste de largura do card
    width_options = {"Pequeno": "400px", "Médio": "600px", "Grande": "800px", "Auto": "100%"}
    width_choice = st.selectbox("Largura do card", list(width_options.keys()))
    card_width = width_options[width_choice]

    st.subheader("Lista de Iniciativas")

    # CSS customizado para lista/card
    list_css = f"""
    <style>
    .card-container {{
        margin-top: 20px;
    }}
    .card {{
        background-color: #2c2f33; /* fundo escuro */
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        color: #ffffff;
        font-size: {font_size}px;
        max-width: {card_width};
    }}
    .card h3 {{
        margin: 0 0 10px 0;
        font-size: {font_size + 4}px; 
        font-weight: bold;
    }}
    .card p {{
        margin: 0 0 5px 0;
    }}
    .card strong {{
        color: #09d3ac; /* cor de destaque */
    }}
    </style>
    """

    st.markdown(list_css, unsafe_allow_html=True)

    # Exibe cada registro como um "card"
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    for idx, row in df_filtrado.iterrows():
        # Constrói o conteúdo de cada card (todas as colunas)
        card_content = ""
        for col in df_filtrado.columns:
            valor = row[col] if not pd.isna(row[col]) else ""
            card_content += f"<p><strong>{col}:</strong> {valor}</p>"

        card_html = f"""
        <div class="card">
            <h3>Registro {idx}</h3>
            {card_content}
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Exibe dados da sessão
    st.write("Dados da sessão:", st.session_state)

app()

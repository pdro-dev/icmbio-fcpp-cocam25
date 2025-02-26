import streamlit as st
import sqlite3
import pandas as pd
import json

# Verifica se o usuário está logado
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

st.title("Visualização de Regras de Negócio")

def load_rules_by_setor(setor: str) -> pd.DataFrame:
    """
    Retorna os registros de regras de negócio em que o usuário (coluna 'usuario')
    está em um setor correspondente ao 'setor_demandante' de tf_usuarios.
    """
    conn = sqlite3.connect("database/app_data.db")
    
    # Consulta com JOIN entre tf_cadastro_regras_negocio e tf_usuarios
    # para filtrar apenas registros cujo usuario = cpf na tf_usuarios,
    # e setor_demandante = setor fornecido.
    query = """
    SELECT r.*
    FROM tf_cadastro_regras_negocio r
    JOIN tf_usuarios u ON r.usuario = u.cpf
    WHERE u.setor_demandante = ?
    ORDER BY r.data_hora DESC
    """
    df = pd.read_sql_query(query, conn, params=[setor])
    conn.close()
    return df

# Carrega apenas os registros do setor do usuário
df_rules = load_rules_by_setor(st.session_state["setor"])

# CSS para estilizar os cards (agora maiores)
card_css = """
<style>
.card-container {
    display: flex;
    flex-wrap: wrap;
    gap: 30px;
    margin-top: 20px;
    justify-content: center; /* centraliza as linhas */
}
.card {
    background: linear-gradient(135deg, #1a1c20, #2c2f33);
    border-radius: 12px;
    padding: 30px;
    color: #f0f0f0;
    flex: 1 1 600px; /* base maior */
    max-width: 800px; /* limite maior */
    box-shadow: 0 6px 10px rgba(0,0,0,0.4);
    transition: transform 0.2s ease-in-out;
    margin: 0 auto;
}
.card:hover {
    transform: scale(1.02);
}
.card h3 {
    margin-top: 0;
    font-size: 1.6em;
    color: #00d1b2;
}
.card p {
    margin: 8px 0;
    font-size: 1.05em;
    line-height: 1.4;
}
.badge {
    background-color: #00d1b2;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 0.85em;
}
</style>
"""

st.markdown(card_css, unsafe_allow_html=True)
st.subheader(f"Regras de Negócio do Setor: {st.session_state['setor']}")

if df_rules.empty:
    st.info("Nenhuma regra de negócio encontrada para o seu setor.")
else:
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    for idx, row in df_rules.iterrows():
        # Tenta converter os campos que foram salvos em JSON
        try:
            objetivos = json.loads(row["objetivos_especificos"])
        except Exception:
            objetivos = row["objetivos_especificos"]
        try:
            eixos = json.loads(row["eixos_tematicos"])
        except Exception:
            eixos = row["eixos_tematicos"]
        try:
            demais = json.loads(row["demais_informacoes"])
        except Exception:
            demais = row["demais_informacoes"]

        # Data/hora bruta do banco
        data_str = str(row["data_hora"])

        # Monta HTML do card
        card_html = f"""
        <div class="card">
            <h3>Regra {idx + 1}</h3>
            <p><strong>Objetivo Geral:</strong> {row['objetivo_geral']}</p>
            <p><strong>Objetivos Específicos:</strong> {objetivos}</p>
            <p><strong>Introdução:</strong> {row['introducao']}</p>
            <p><strong>Justificativa:</strong> {row['justificativa']}</p>
            <p><strong>Metodologia:</strong> {row['metodologia']}</p>
            <p><strong>Eixos Temáticos:</strong> {eixos}</p>
            <p><strong>Demais Informações:</strong> {demais}</p>
            <p><strong>Usuário (CPF):</strong> <span class="badge">{row['usuario']}</span></p>
            <p><strong>Data:</strong> {data_str}</p>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Se quiser exibir dados da sessão para debug, descomente:
# st.write("Dados da sessão:", st.session_state)

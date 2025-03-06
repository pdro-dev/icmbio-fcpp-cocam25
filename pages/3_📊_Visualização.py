import streamlit as st
import sqlite3
import pandas as pd
import json
from fpdf import FPDF
from io import BytesIO
from datetime import datetime
import html

# Verifica login
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

st.title("📊 Visualização de Iniciativas - Versão Mais Recente")

# --- Funções para carregar dados e mapeamentos ---

def load_iniciativas_by_setor(setor: str) -> pd.DataFrame:
    conn = sqlite3.connect("database/app_data.db")
    query = """
    SELECT r.*, i.nome_iniciativa
    FROM tf_cadastro_regras_negocio r
    JOIN td_iniciativas i ON r.id_iniciativa = i.id_iniciativa
    JOIN tf_usuarios u ON r.usuario = u.cpf
    JOIN (
        SELECT id_iniciativa, MAX(data_hora) AS max_data
        FROM tf_cadastro_regras_negocio
        GROUP BY id_iniciativa
    ) sub ON sub.id_iniciativa = r.id_iniciativa
         AND sub.max_data = r.data_hora
    WHERE u.setor_demandante = ?
    ORDER BY r.data_hora DESC
    """
    df = pd.read_sql_query(query, conn, params=[setor])
    conn.close()
    return df

def load_acoes_map():
    conn = sqlite3.connect("database/app_data.db")
    df_acoes = pd.read_sql_query("SELECT id_acao, nome_acao FROM td_acoes_aplicacao", conn)
    conn.close()
    return {str(row['id_acao']): row['nome_acao'] for _, row in df_acoes.iterrows()}

def load_insumos_map():
    conn = sqlite3.connect("database/app_data.db")
    df_insumos = pd.read_sql_query("SELECT id, descricao_insumo FROM td_insumos", conn)
    conn.close()
    return {str(row['id']): row['descricao_insumo'] for _, row in df_insumos.iterrows()}

acoes_map = load_acoes_map()
insumos_map = load_insumos_map()

# --- CSS para layout na interface ---
card_css = """
<style>
.card-container {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(650px, 1fr));
    gap: 25px;
    padding: 20px;
}
.card {
    background: #ffffff;
    border-radius: 15px;
    padding: 25px;
    color: #333;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    border-left: 5px solid #00d1b2;
    position: relative;
}
.card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 16px rgba(0,0,0,0.2);
}
.card h3 {
    margin-top: 0;
    font-size: 1.8rem;
    color: #00d1b2;
}
.card-section {
    margin-bottom: 15px;
    padding: 12px;
    background: #f9f9f9;
    border-radius: 8px;
}
.card-section-title {
    font-weight: 600;
    color: #00d1b2;
    margin-bottom: 8px;
    font-size: 1.1rem;
}
.badge {
    background: #00d1b233;
    color: #00d1b2;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.9rem;
    margin-right: 10px;
}
</style>
"""
st.markdown(card_css, unsafe_allow_html=True)

# --- Seleção da Iniciativa (mais recente) ---
df_iniciativas = load_iniciativas_by_setor(st.session_state["setor"])


if df_iniciativas.empty:
    st.info("ℹ️ Nenhuma iniciativa encontrada para o seu setor.")
    st.stop()

iniciativas_list = df_iniciativas['nome_iniciativa'].unique()
selected_iniciativa = st.selectbox("Selecione a iniciativa mais recente", iniciativas_list)
df_filtered = df_iniciativas[df_iniciativas['nome_iniciativa'] == selected_iniciativa]

# --- Exibição dos cards na interface ---
st.markdown("<div class='card-container'>", unsafe_allow_html=True)

for idx, row in df_filtered.iterrows():
    objetivo_geral = html.escape(row['objetivo_geral']).replace("\n", "<br>")
    objetivos_especificos = html.escape(json.dumps(row['objetivos_especificos'], ensure_ascii=False)).replace("\n", "<br>")
    introducao = html.escape(row['introducao']).replace("\n", "<br>")
    justificativa = html.escape(row['justificativa']).replace("\n", "<br>")
    metodologia = html.escape(row['metodologia']).replace("\n", "<br>")
    eixos_tematicos = html.escape(json.dumps(row.get('eixos_tematicos', ''), ensure_ascii=False)).replace("\n", "<br>")
    insumos = html.escape(json.dumps(row.get('insumos', ''), ensure_ascii=False)).replace("\n", "<br>")
    distribuicao_ucs = html.escape(json.dumps(row.get('distribuicao_ucs', ''), ensure_ascii=False)).replace("\n", "<br>")
    formas_contratacao = html.escape(json.dumps(row.get('formas_contratacao', ''), ensure_ascii=False)).replace("\n", "<br>")
    demais_informacoes = html.escape(json.dumps(row.get('demais_informacoes', ''), ensure_ascii=False)).replace("\n", "<br>")

    data_formatada = datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')

    card_html = f"""
        <div class="card">
            <h3>Iniciativa: {html.escape(row['nome_iniciativa'])}</h3>
            <div class="card-section">
                <div class="card-section-title">Objetivo Geral</div>
                {objetivo_geral}
            </div>
            <div class="card-section">
                <div class="card-section-title">Objetivos Específicos</div>
                {objetivos_especificos}
            </div>
            <div class="card-section">
                <div class="card-section-title">Introdução</div>
                {introducao}
            </div>
            <div class="card-section">
                <div class="card-section-title">Justificativa</div>
                {justificativa}
            </div>
            <div class="card-section">
                <div class="card-section-title">Metodologia</div>
                {metodologia}
            </div>
            <div class="card-section">
                <div class="card-section-title">Eixos Temáticos</div>
                {eixos_tematicos}
            </div>
            <div class="card-section">
                <div class="card-section-title">Insumos</div>
                {insumos}
            </div>
            <div class="card-section">
                <div class="card-section-title">Distribuição por Unidade</div>
                {distribuicao_ucs}
            </div>
            <div class="card-section">
                <div class="card-section-title">Formas de Contratação</div>
                {formas_contratacao}
            </div>
            <div class="card-section">
                <div class="card-section-title">Demais Informações</div>
                {demais_informacoes}
            </div>
            <div style="margin-top: 15px;">
                <span class="badge">Responsável: {html.escape(row['usuario'])}</span>
                <span class="badge">Data/Hora: {data_formatada}</span>
            </div>
        </div>
    """

    st.markdown(card_html, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

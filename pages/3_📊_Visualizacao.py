import streamlit as st
import sqlite3
import pandas as pd
import json
from fpdf import FPDF
from io import BytesIO
from datetime import datetime

# Verifica login
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

st.title("📊 Visualização de Regras de Negócio")

# Função para carregar dados
def load_rules_by_setor(setor: str) -> pd.DataFrame:
    conn = sqlite3.connect("database/app_data.db")
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

# CSS aprimorado para layout e consistência visual
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
}
.card:hover {
    transform: translateY(-5px);
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

# Carrega os dados do setor e define a variável df_rules antes de utilizá-la em outras partes
df_rules = load_rules_by_setor(st.session_state["setor"])

# Função para criar PDF com layout em tabela
def create_pdf(df: pd.DataFrame):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Cabeçalho do PDF
    pdf.cell(0, 10, f"Relatório de Regras de Negócio - {st.session_state['setor']}", 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_font("Arial", size=10)
    line_height = 8

    # Para cada regra, exibe os dados em formato de tabela
    for idx, row in df.iterrows():
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f"Regra {idx+1}", 0, 1)
        pdf.set_font('Arial', 'B', 10)
        
        # Cria cabeçalho da tabela
        headers = ["Campo", "Descrição"]
        col_width = pdf.w / 2 - 20
        
        for header in headers:
            pdf.cell(col_width, line_height, header, border=1, align='C')
        pdf.ln(line_height)
        
        pdf.set_font('Arial', '', 10)
        
        # Função auxiliar para tratar campos JSON
        def process_field(field):
            try:
                data = json.loads(field)
                if isinstance(data, list):
                    return "\n• " + "\n• ".join(data)
                return str(data)
            except Exception:
                return str(field)
        
        # Lista de campos a serem exibidos
        conteudo = [
            ("Objetivo Geral", row['objetivo_geral']),
            ("Objetivos Específicos", process_field(row['objetivos_especificos'])),
            ("Introdução", row['introducao']),
            ("Justificativa", row['justificativa']),
            ("Metodologia", row['metodologia']),
            ("Eixos Temáticos", process_field(row['eixos_tematicos'])),
            ("Demais Informações", process_field(row['demais_informacoes'])),
            ("Responsável", f"{row['usuario']} - {datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}")
        ]
        
        # Adiciona cada linha da tabela
        for campo, descricao in conteudo:
            pdf.cell(col_width, line_height, campo, border=1)
            x_current = pdf.get_x()
            y_current = pdf.get_y()
            pdf.multi_cell(col_width, line_height, descricao.encode('latin-1', 'replace').decode('latin-1'), border=1)
            pdf.set_xy(x_current - col_width, pdf.get_y())
            pdf.ln(line_height)
        
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
        pdf.ln(8)
    
    return pdf

# Botão para gerar PDF
if st.button("📄 Gerar Relatório em PDF"):
    with st.spinner("Gerando PDF..."):
        pdf = create_pdf(df_rules)
        pdf_bytes = pdf.output(dest="S").encode("latin-1")
        st.download_button(
            label="⬇️ Download do Relatório",
            data=pdf_bytes,
            file_name=f"relatorio_regras_{st.session_state['setor']}.pdf",
            mime="application/pdf"
        )

# Exibição dos cards com as regras
st.subheader(f"📂 Regras do Setor: {st.session_state['setor']}")

if df_rules.empty:
    st.info("ℹ️ Nenhuma regra de negócio encontrada para o seu setor.")
else:
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    for idx, row in df_rules.iterrows():
        # Função para tratar campos JSON
        def process_field(field):
            try:
                data = json.loads(field)
                if isinstance(data, list):
                    return "• " + "<br>• ".join(data)
                return str(data)
            except Exception:
                return str(field)
        
        card_html = f"""
        <div class="card">
            <h3>Regra {idx + 1}</h3>
            <div class="card-section">
                <div class="card-section-title">🎯 Objetivo Geral</div>
                {row['objetivo_geral']}
            </div>
            <div class="card-section">
                <div class="card-section-title">📌 Objetivos Específicos</div>
                {process_field(row['objetivos_especificos'])}
            </div>
            <div class="card-section">
                <div class="card-section-title">📖 Introdução</div>
                {row['introducao']}
            </div>
            <div class="card-section">
                <div class="card-section-title">📈 Justificativa</div>
                {row['justificativa']}
            </div>
            <div class="card-section">
                <div class="card-section-title">🔧 Metodologia</div>
                {row['metodologia']}
            </div>
            <div class="card-section">
                <div class="card-section-title">🗂️ Eixos Temáticos</div>
                {process_field(row['eixos_tematicos'])}
            </div>
            <div class="card-section">
                <div class="card-section-title">ℹ️ Demais Informações</div>
                {process_field(row['demais_informacoes'])}
            </div>
            <div style="margin-top: 15px;">
                <span class="badge">👤 Responsável: {row['usuario']}</span>
                <span class="badge">📅 {datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}</span>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

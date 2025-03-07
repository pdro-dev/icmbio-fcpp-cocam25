import streamlit as st
import sqlite3
import pandas as pd
import json
from fpdf import FPDF
from io import BytesIO
from datetime import datetime
import textwrap
import html
import re
import tempfile
from streamlit_pdf_viewer import pdf_viewer  # pip install streamlit-pdf-viewer

# Verifica login
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

# Configurações da página
st.set_page_config(
    page_title="Visualização de Iniciativas",
    page_icon=":chart_with_upwards_trend:",
    layout="wide"
)

st.subheader("📊 Visualização de Iniciativas - Versão Mais Recente")

# --- Funções para carregar dados e mapeamentos ---

def load_iniciativas_by_setor(setor: str) -> pd.DataFrame:
    """
    Retorna apenas a VERSÃO MAIS RECENTE (maior data_hora) de cada iniciativa
    para o setor informado.
    """
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

# --- Funções de formatação para exibição em tela ---

def format_objetivos_especificos(json_str):
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return "<br>".join(data)
        elif isinstance(data, dict):
            return "<br>".join([f"{k}: {v}" for k, v in data.items()])
        else:
            return str(data)
    except Exception:
        return json_str

def format_eixos_tematicos(json_str):
    try:
        data = json.loads(json_str)
        if not data:
            return "Nenhum eixo temático cadastrado."
        output = ""
        for eixo in data:
            eixo_nome = eixo.get("nome_eixo", "Sem nome")
            output += f"Eixo Temático: {eixo_nome}<br>"
            acoes = eixo.get("acoes_manejo", {})
            if acoes:
                output += "  Ações de Manejo:<br>"
                for acao_id, detalhes in acoes.items():
                    acao_nome = acoes_map.get(str(acao_id), f"Ação {acao_id}")
                    insumos = detalhes.get("insumos", [])
                    if insumos:
                        insumos_names = [insumos_map.get(str(insumo), str(insumo)) for insumo in insumos]
                        output += f"    · {acao_nome} - Insumos: {', '.join(insumos_names)}<br>"
                    else:
                        output += f"    · {acao_nome} - Sem insumos cadastrados<br>"
            else:
                output += "  Nenhuma ação de manejo cadastrada.<br>"
            output += "<br>"
        return output.strip()
    except Exception as e:
        return f"Erro ao processar dados: {str(e)}"

def format_formas_contratacao(json_str):
    try:
        data = json.loads(json_str)
        if not data:
            return "Nenhuma forma de contratação cadastrada."
        output = ""
        tabela_formas = data.get("tabela_formas", [])
        detalhes = data.get("detalhes", {})
        if tabela_formas:
            output += "Formas de Contratação Disponíveis:<br>"
            for item in tabela_formas:
                forma = item.get("Forma de Contratação", "Sem descrição")
                selecionado = item.get("Selecionado", False)
                status = "Selecionado" if selecionado else "Não selecionado"
                output += f"· {forma} ({status})<br>"
        else:
            output += "Nenhuma forma de contratação listada.<br>"
        if detalhes:
            output += "<br>Detalhes:<br>"
            for chave, valor in detalhes.items():
                if isinstance(valor, list):
                    valor_str = ", ".join(map(str, valor))
                else:
                    valor_str = str(valor) if valor != "" else "Não informado"
                output += f"{chave}: {valor_str}<br>"
        return output.strip()
    except Exception as e:
        return f"Erro ao processar dados: {str(e)}"

def format_insumos(json_str):
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            result = []
            for insumo in data:
                insumo_str = str(insumo)
                insumo_nome = insumos_map.get(insumo_str, insumo_str)
                result.append(insumo_nome)
            return "- " + "<br>- ".join(result)
        elif isinstance(data, dict):
            text = ""
            for key, value in data.items():
                text += f"{key}: {value}<br>"
            return text
        else:
            return str(data)
    except Exception:
        return str(json_str)

def process_generic_json(field):
    try:
        data = json.loads(field)
        if isinstance(data, list):
            return "- " + "<br>- ".join(map(str, data))
        elif isinstance(data, dict):
            return "<br>".join([f"{k}: {v}" for k, v in data.items()])
        else:
            return str(data)
    except Exception:
        return str(field)

def format_distribuicao_ucs(json_str):
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            table_html = "<table>"
            table_html += "<tr><th>Unidade</th><th>Ação</th><th>Valor Alocado</th></tr>"
            for item in data:
                unidade = item.get("Unidade", "")
                acao = item.get("Acao", "")
                valor = item.get("Valor Alocado", "")
                table_html += f"<tr><td>{unidade}</td><td>{acao}</td><td>{valor}</td></tr>"
            table_html += "</table>"
            return table_html
        else:
            return str(data)
    except Exception as e:
        return str(json_str)

# --- Funções auxiliares para o PDF ---

def remove_html_for_pdf(text: str) -> str:
    """
    Remove tags HTML e converte <br> em quebras de linha,
    além de fazer unescape de entidades HTML.
    """
    # Substitui <br> por \n
    text = text.replace("<br>", "\n")
    # Remove quaisquer tags HTML remanescentes
    text = re.sub(r"<.*?>", "", text)
    # Decodifica entidades HTML (&amp;, &gt;, etc.)
    text = html.unescape(text)
    return text

def get_wrapped_text(text, width, pdf):
    """
    Retorna (texto_em_linhas, numero_de_linhas) para permitir
    a impressão correta em multicell.
    """
    font_size = pdf.font_size_pt
    approx_chars_per_line = int(width / (font_size * 0.35))
    import textwrap
    wrapped = textwrap.wrap(text, width=approx_chars_per_line)
    if not wrapped:
        wrapped = [""]
    return "\n".join(wrapped), len(wrapped)

# --- Função principal para gerar o PDF ---
def create_pdf(df: pd.DataFrame):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Título do PDF
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Extrato de Iniciativas - Setor: " + st.session_state["setor"], ln=True, align="C")
    pdf.ln(5)
    
    for idx, row in df.iterrows():
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Iniciativa: {row['nome_iniciativa']}", ln=True)
        pdf.ln(2)
        
        # Cabeçalho da tabela
        headers = ["Campo", "Descrição"]
        effective_width = pdf.w - 2 * pdf.l_margin
        col_widths = [effective_width * 0.3, effective_width * 0.7]
        line_height = 8
        
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(220, 220, 220)  # Fundo cinza claro
        # Imprime cabeçalho com fill=True
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], line_height, header, border=1, align="C", fill=True)
        pdf.ln(line_height)
        
        # Conteúdo da tabela
        pdf.set_font("Arial", "", 10)
        pdf.set_fill_color(255, 255, 255)  # Volta para fundo branco
        
        # Monta os dados
        table_data = [
            ("Objetivo Geral", row['objetivo_geral']),
            ("Objetivos Específicos", row['objetivos_especificos']),
            ("Introdução", row['introducao']),
            ("Justificativa", row['justificativa']),
            ("Metodologia", row['metodologia']),
            ("Eixos Temáticos", row.get('eixos_tematicos', '')),
            ("Insumos", row.get('insumos', '')),
            ("Distribuição por Unidade", row.get('distribuicao_ucs', '')),
            ("Formas de Contratação", row.get('formas_contratacao', '')),
            ("Demais Informações", row.get('demais_informacoes', '')),
            ("Responsável", f"{row['usuario']} - {datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}")
        ]
        
        # Para cada linha, removemos HTML e depois quebramos em múltiplas linhas
        for campo, valor in table_data:
            # Remove tags HTML do valor
            valor_limpo = remove_html_for_pdf(str(valor))
            
            # Quebra em múltiplas linhas
            wrapped_campo, lines_campo = get_wrapped_text(campo, col_widths[0], pdf)
            wrapped_valor, lines_valor = get_wrapped_text(valor_limpo, col_widths[1], pdf)
            max_lines = max(lines_campo, lines_valor)
            row_height = max_lines * line_height
            
            x_initial = pdf.get_x()
            y_initial = pdf.get_y()
            
            # Imprime o "Campo"
            pdf.multi_cell(col_widths[0], line_height, wrapped_campo, border=1)
            y_after = pdf.get_y()
            cell1_height = y_after - y_initial
            
            # Imprime a "Descrição"
            pdf.set_xy(x_initial + col_widths[0], y_initial)
            pdf.multi_cell(col_widths[1], line_height, wrapped_valor, border=1)
            y_after2 = pdf.get_y()
            cell2_height = y_after2 - y_initial
            
            # Ajusta se houver diferença de altura entre as duas células
            final_height = max(cell1_height, cell2_height)
            if cell1_height < final_height:
                pdf.set_xy(x_initial, y_initial + cell1_height)
                pdf.cell(col_widths[0], final_height - cell1_height, "", border=1)
            if cell2_height < final_height:
                pdf.set_xy(x_initial + col_widths[0], y_initial + cell2_height)
                pdf.cell(col_widths[1], final_height - cell2_height, "", border=1)
            pdf.set_xy(x_initial, y_initial + final_height)
        
        # Linha de separação entre iniciativas
        pdf.ln(10)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.l_margin, pdf.get_y())
        pdf.ln(10)
    
    return pdf

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
table {
    width: 100%;
    border-collapse: collapse;
}
table, th, td {
    border: 1px solid #ddd;
    padding: 8px;
}
th {
    background-color: #00d1b2;
    color: white;
}
</style>
"""
st.markdown(card_css, unsafe_allow_html=True)

# --- Carrega todas as iniciativas do setor do usuário ---
df_iniciativas = load_iniciativas_by_setor(st.session_state["setor"])
if df_iniciativas.empty:
    st.info("ℹ️ Nenhuma iniciativa encontrada para o seu setor.")
    st.stop()

# Exibição dos cards para visualização na interface
st.markdown("<div class='card-container'>", unsafe_allow_html=True)
for idx, row in df_iniciativas.iterrows():
    objetivo_geral = html.escape(row['objetivo_geral']).replace("\n", "<br>")
    objetivos_especificos = format_objetivos_especificos(row['objetivos_especificos'])
    introducao = html.escape(row['introducao']).replace("\n", "<br>")
    justificativa = html.escape(row['justificativa']).replace("\n", "<br>")
    metodologia = html.escape(row['metodologia']).replace("\n", "<br>")
    eixos_tematicos = format_eixos_tematicos(row.get('eixos_tematicos', ''))
    insumos = format_insumos(row.get('insumos', ''))
    distribuicao_ucs = format_distribuicao_ucs(row.get('distribuicao_ucs', ''))
    formas_contratacao = format_formas_contratacao(row.get('formas_contratacao', ''))
    demais_informacoes = process_generic_json(row.get('demais_informacoes', '')).replace("\n", "<br>")
    data_formatada = datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
    
    card_html = f"""
        <div class="card">
            <div class="card-section">
                <h3>{html.escape(row['nome_iniciativa'])}</h3>
            </div>
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

# --- Botão para gerar o PDF com extrato completo ---
if st.button("📄 Gerar Extrato Completo em PDF", type='secondary'):
    with st.spinner("Gerando Extrato em PDF..."):
        pdf = create_pdf(df_iniciativas)
        # Gera a string do PDF, substitui "•" por "·" (compatível com latin-1)
        pdf_str = pdf.output(dest="S")
        pdf_str = pdf_str.replace("•", "·")
        pdf_bytes = pdf_str.encode("latin-1", errors="ignore")  # "ignore" remove chars inválidos
        # Salva o PDF em arquivo temporário para exibição
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        st.download_button(
            label="⬇️ Download do Extrato (PDF)",
            data=pdf_bytes,
            file_name=f"extrato_iniciativas_{st.session_state['setor']}.pdf",
            mime="application/pdf"
        )
        
        pdf_viewer(tmp_path)

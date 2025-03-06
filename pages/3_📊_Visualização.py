import streamlit as st
import sqlite3
import pandas as pd
import json
from fpdf import FPDF
from io import BytesIO
from datetime import datetime
import textwrap

# Verifica login
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

st.title("📊 Visualização de Iniciativas - Versão Mais Recente")

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
        -- Seleciona a data mais recente de cada iniciativa
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

# Se não existir nenhum registro, exibir aviso
if df_iniciativas.empty:
    st.info("ℹ️ Nenhuma iniciativa encontrada para o seu setor.")
    st.stop()

iniciativas_list = df_iniciativas['nome_iniciativa'].unique()
selected_iniciativa = st.selectbox("Selecione a iniciativa mais recente", iniciativas_list)
df_filtered = df_iniciativas[df_iniciativas['nome_iniciativa'] == selected_iniciativa]

# --- Funções para formatação dos campos JSON ---
def format_eixos_tematicos(json_str):
    """
    Exibe o nome do eixo e as ações com insumos.
    Substitui caracteres "•" por "-" para evitar problemas de encoding no PDF.
    """
    try:
        data = json.loads(json_str)
        text = ""
        for eixo in data:
            eixo_nome = eixo.get('nome_eixo', '')
            text += f"{eixo_nome}\n"
            acoes = eixo.get("acoes_manejo", {})
            if acoes:
                for acao_id, detalhes in acoes.items():
                    acao_nome = acoes_map.get(str(acao_id), f"Ação {acao_id}")
                    insumos = detalhes.get("insumos", [])
                    insumos_names = []
                    for insumo in insumos:
                        insumo_str = str(insumo)
                        insumo_nome = insumos_map.get(insumo_str, insumo_str)
                        insumos_names.append(insumo_nome)
                    text += f"  - {acao_nome}: Insumos - {', '.join(insumos_names)}\n"
            else:
                text += "  Nenhuma ação cadastrada.\n"
        return text
    except Exception:
        return str(json_str)

def format_insumos(json_str):
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            result = []
            for insumo in data:
                insumo_str = str(insumo)
                insumo_nome = insumos_map.get(insumo_str, insumo_str)
                result.append(insumo_nome)
            return "- " + "\n- ".join(result)
        elif isinstance(data, dict):
            text = ""
            for key, value in data.items():
                text += f"{key}: {value}\n"
            return text
        else:
            return str(data)
    except Exception:
        return str(json_str)

def process_generic_json(field):
    try:
        data = json.loads(field)
        if isinstance(data, list):
            return "- " + "\n- ".join(map(str, data))
        elif isinstance(data, dict):
            return "\n".join([f"{k}: {v}" for k, v in data.items()])
        else:
            return str(data)
    except Exception:
        return str(field)

def format_distribuicao_ucs(json_str):
    """
    Exibe os valores distribuídos por unidade, se houver.
    """
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            # Exemplo: { "UC1": 50000, "UC2": 75000, ... }
            lines = []
            for uc, valor in data.items():
                lines.append(f"{uc}: {valor}")
            return "\n".join(lines)
        elif isinstance(data, list):
            # Caso seja uma lista de objetos
            lines = []
            for item in data:
                lines.append(str(item))
            return "- " + "\n- ".join(lines)
        else:
            return str(data)
    except:
        return str(json_str)

def format_formas_contratacao(json_str):
    """
    Exibe as formas de contratação.
    """
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return "- " + "\n- ".join(map(str, data))
        elif isinstance(data, dict):
            return "\n".join([f"{k}: {v}" for k, v in data.items()])
        else:
            return str(data)
    except:
        return str(json_str)

# --- Função auxiliar para calcular número de linhas (para estimar altura) ---
def get_wrapped_text(text, width, pdf):
    font_size = pdf.font_size_pt
    approx_chars_per_line = int(width / (font_size * 0.35))
    import textwrap
    wrapped = textwrap.wrap(text, width=approx_chars_per_line)
    if not wrapped:
        wrapped = [""]
    return "\n".join(wrapped), len(wrapped)

# --- Função para criar o PDF com tabela organizada ---
def create_pdf(df: pd.DataFrame):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Título do PDF
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Relatório de Iniciativas - (Versão Mais Recente)", ln=True, align="C")
    pdf.ln(5)
    
    for idx, row in df.iterrows():
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Iniciativa: {row['nome_iniciativa']}", ln=True)
        pdf.ln(2)
        
        headers = ["Campo", "Descrição"]
        effective_width = pdf.w - 2 * pdf.l_margin
        col_widths = [effective_width * 0.3, effective_width * 0.7]
        line_height = 8
        
        pdf.set_font("Arial", "B", 10)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], line_height, header, border=1, align="C")
        pdf.ln(line_height)
        
        pdf.set_font("Arial", "", 10)
        
        def process_field(field):
            try:
                data = json.loads(field)
                if isinstance(data, list):
                    return "\n- " + "\n- ".join(map(str, data))
                elif isinstance(data, dict):
                    return "\n".join([f"{k}: {v}" for k, v in data.items()])
                return str(data)
            except:
                return str(field)
        
        # Montamos os campos que serão exibidos na tabela
        table_data = [
            ("Objetivo Geral", row['objetivo_geral']),
            ("Objetivos Específicos", process_field(row['objetivos_especificos'])),
            ("Introdução", row['introducao']),
            ("Justificativa", row['justificativa']),
            ("Metodologia", row['metodologia']),
            ("Eixos Temáticos", format_eixos_tematicos(row.get('eixos_tematicos', ''))),
            ("Insumos", format_insumos(row.get('insumos', ''))),
            ("Distribuição por Unidade", format_distribuicao_ucs(row.get('distribuicao_ucs', ''))),
            ("Formas de Contratação", format_formas_contratacao(row.get('formas_contratacao', ''))),
            ("Demais Informações", process_generic_json(row.get('demais_informacoes', ''))),
            ("Adicionar um item", "Exemplo de item adicional..."),
            ("Responsável", f"{row['usuario']} - {datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}")
        ]
        
        # Desenha cada linha da tabela com altura dinâmica
        for campo, descricao in table_data:
            wrapped_campo, lines_campo = get_wrapped_text(campo, col_widths[0], pdf)
            wrapped_descricao, lines_descricao = get_wrapped_text(descricao, col_widths[1], pdf)
            max_lines = max(lines_campo, lines_descricao)
            row_height = max_lines * line_height
            
            x_initial = pdf.get_x()
            y_initial = pdf.get_y()
            
            pdf.multi_cell(col_widths[0], line_height, wrapped_campo, border=1)
            y_after = pdf.get_y()
            cell1_height = y_after - y_initial
            
            pdf.set_xy(x_initial + col_widths[0], y_initial)
            pdf.multi_cell(col_widths[1], line_height, wrapped_descricao, border=1)
            y_after2 = pdf.get_y()
            cell2_height = y_after2 - y_initial
            
            final_height = max(cell1_height, cell2_height)
            if cell1_height < final_height:
                pdf.set_xy(x_initial, y_initial + cell1_height)
                pdf.cell(col_widths[0], final_height - cell1_height, "", border=1)
            if cell2_height < final_height:
                pdf.set_xy(x_initial + col_widths[0], y_initial + cell2_height)
                pdf.cell(col_widths[1], final_height - cell2_height, "", border=1)
            pdf.set_xy(x_initial, y_initial + final_height)
        
        pdf.ln(10)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.l_margin, pdf.get_y())
        pdf.ln(10)
    
    return pdf

# --- Botão para gerar PDF ---
st.markdown("---")
st.write("#### Gerar Relatório")
if st.button("📄 Gerar Relatório em PDF"):
    with st.spinner("Gerando PDF..."):
        pdf = create_pdf(df_filtered)
        pdf_bytes = pdf.output(dest="S").encode("latin-1")  # todos caracteres compatíveis
        st.download_button(
            label="⬇️ Download do Relatório (PDF)",
            data=pdf_bytes,
            file_name=f"relatorio_iniciativas_{selected_iniciativa}.pdf",
            mime="application/pdf"
        )

# --- Exibição dos cards na interface ---
st.markdown("---")
st.subheader(f"Versão mais recente da iniciativa: {selected_iniciativa}")

st.markdown("<div class='card-container'>", unsafe_allow_html=True)
for idx, row in df_filtered.iterrows():
    card_html = f"""
    <div class="card">
        <h3>Iniciativa: {row['nome_iniciativa']}</h3>
        <div class="card-section">
            <div class="card-section-title">Objetivo Geral</div>
            {row['objetivo_geral']}
        </div>
        <div class="card-section">
            <div class="card-section-title">Objetivos Específicos</div>
            {process_generic_json(row['objetivos_especificos']).replace("\\n", "<br>").replace("-", "–")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Introdução</div>
            {row['introducao']}
        </div>
        <div class="card-section">
            <div class="card-section-title">Justificativa</div>
            {row['justificativa']}
        </div>
        <div class="card-section">
            <div class="card-section-title">Metodologia</div>
            {row['metodologia']}
        </div>
        <div class="card-section">
            <div class="card-section-title">Eixos Temáticos</div>
            {format_eixos_tematicos(row.get('eixos_tematicos','')).replace("\\n","<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Insumos</div>
            {format_insumos(row.get('insumos','')).replace("\\n","<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Distribuição por Unidade</div>
            {format_distribuicao_ucs(row.get('distribuicao_ucs','')).replace("\\n","<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Formas de Contratação</div>
            {format_formas_contratacao(row.get('formas_contratacao','')).replace("\\n","<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Demais Informações</div>
            {process_generic_json(row.get('demais_informacoes','')).replace("\\n","<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Adicionar um item</div>
            Exemplo de item adicional...
        </div>
        <div style="margin-top: 15px;">
            <span class="badge">Responsável: {row['usuario']}</span>
            <span class="badge">Data/Hora: {datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}</span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

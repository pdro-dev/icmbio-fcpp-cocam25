import streamlit as st
import sqlite3
import pandas as pd
import json
from fpdf import FPDF
from datetime import datetime
import textwrap
import html
import re
import tempfile
from streamlit_pdf_viewer import pdf_viewer  # pip install streamlit-pdf-viewer

########################################
# Verificação de Login e Configuração  #
########################################

if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login na página principal para acessar esta seção.")
    st.stop()

st.set_page_config(
    page_title="Visualização de Iniciativas",
    page_icon=":chart_with_upwards_trend:",
    layout="wide"
)
st.subheader("📊 Visualização de Iniciativas - Versão Mais Recente")

########################################
# Funções de Carregamento de Dados     #
########################################

def load_iniciativas(setor: str) -> pd.DataFrame:
    """Retorna a versão mais recente de cada iniciativa para o setor informado."""
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
    df = pd.read_sql_query("SELECT id_acao, nome_acao FROM td_acoes_aplicacao", conn)
    conn.close()
    return {str(row['id_acao']): row['nome_acao'] for _, row in df.iterrows()}

def load_insumos_map():
    conn = sqlite3.connect("database/app_data.db")
    df = pd.read_sql_query("SELECT id, descricao_insumo FROM td_insumos", conn)
    conn.close()
    return {str(row['id']): row['descricao_insumo'] for _, row in df.iterrows()}

# Carregamento de mapeamentos
acoes_map = load_acoes_map()
insumos_map = load_insumos_map()

########################################
# Funções de Formatação de Conteúdo    #
########################################

def format_objetivos_especificos(json_str):
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return "<br>".join(data)
        elif isinstance(data, dict):
            return "<br>".join([f"{k}: {v}" for k, v in data.items()])
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
            output += f"<strong>Eixo Temático:</strong> {eixo_nome}<br>"
            acoes = eixo.get("acoes_manejo", {})
            if acoes:
                output += "&nbsp;&nbsp;Ações de Manejo:<br>"
                for acao_id, detalhes in acoes.items():
                    acao_nome = acoes_map.get(str(acao_id), f"Ação {acao_id}")
                    insumos = detalhes.get("insumos", [])
                    if insumos:
                        insumos_names = [insumos_map.get(str(insumo), str(insumo)) for insumo in insumos]
                        output += f"&nbsp;&nbsp;&nbsp;&nbsp;· {acao_nome} - Insumos: {', '.join(insumos_names)}<br>"
                    else:
                        output += f"&nbsp;&nbsp;&nbsp;&nbsp;· {acao_nome} - Sem insumos cadastrados<br>"
            else:
                output += "Nenhuma ação de manejo cadastrada.<br>"
            output += "<br>"
        return output.strip()
    except Exception as e:
        return f"Erro: {str(e)}"

def format_formas_contratacao(json_str):
    try:
        data = json.loads(json_str)
        if not data:
            return "Nenhuma forma de contratação cadastrada."
        output = ""
        tabela_formas = data.get("tabela_formas", [])
        detalhes = data.get("detalhes", {})
        if tabela_formas:
            output += "<strong>Formas de Contratação Disponíveis:</strong><br>"
            for item in tabela_formas:
                forma = item.get("Forma de Contratação", "Sem descrição")
                selecionado = item.get("Selecionado", False)
                status = "Selecionado" if selecionado else "Não selecionado"
                output += f"· {forma} ({status})<br>"
        else:
            output += "Nenhuma forma de contratação listada.<br>"
        if detalhes:
            output += "<br><strong>Detalhes:</strong><br>"
            for chave, valor in detalhes.items():
                if isinstance(valor, list):
                    valor_str = ", ".join(map(str, valor)) if valor else "Não informado"
                else:
                    valor_str = str(valor) if valor != "" else "Não informado"
                output += f"{chave}: {valor_str}<br>"
        return output.strip()
    except Exception as e:
        return f"Erro: {str(e)}"

def format_insumos(json_str):
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            result = [insumos_map.get(str(insumo), str(insumo)) for insumo in data]
            return "- " + "<br>- ".join(result)
        elif isinstance(data, dict):
            return "<br>".join([f"{k}: {v}" for k, v in data.items()])
        return str(data)
    except Exception:
        return str(json_str)

def process_generic_json(field):
    """Converte um JSON simples em uma listagem ou string legível."""
    try:
        data = json.loads(field)
        if isinstance(data, list):
            return "- " + "<br>- ".join(map(str, data))
        elif isinstance(data, dict):
            lines = []
            for k, v in data.items():
                if v is None or v == "":
                    v = "Não informado"
                lines.append(f"{k}: {v}")
            return "<br>".join(lines)
        return str(data)
    except Exception:
        return str(field)

def format_distribuicao_ucs(json_str):
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            table_html = "<table border='1' cellpadding='4'>"
            table_html += "<tr><th>Unidade</th><th>Ação</th><th>Valor Alocado</th></tr>"
            for item in data:
                unidade = item.get("Unidade", "")
                acao = item.get("Acao", "")
                valor = item.get("Valor Alocado", "")
                table_html += f"<tr><td>{unidade}</td><td>{acao}</td><td>{valor}</td></tr>"
            table_html += "</table>"
            return table_html
        return str(data)
    except Exception:
        return str(json_str)

########################################
# Funções Auxiliares para o PDF        #
########################################

def remove_html_for_pdf(text: str) -> str:
    """Remove tags HTML e converte <br> para quebras de linha."""
    text = text.replace("<br>", "\n")
    text = re.sub(r"<.*?>", "", text)
    return html.unescape(text)

def sanitize_text(text: str) -> str:
    """Converte o texto para Latin-1, substituindo caracteres problemáticos."""
    return text.encode("latin1", errors="replace").decode("latin1")

class PDF(FPDF):
    def header(self):
        # Título no topo de cada página
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, sanitize_text("Relatório de Iniciativas"), 0, 1, "C")
        self.ln(5)

    def footer(self):
        # Rodapé com número da página
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        page_num = f"Página {self.page_no()}"
        self.cell(0, 10, page_num, 0, 0, "C")

def draw_section_title(pdf: PDF, title: str):
    """Desenha um título de seção em negrito."""
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(0, 0, 0)  # preto
    pdf.cell(0, 8, sanitize_text(title), 0, 1)
    pdf.ln(2)

def draw_simple_paragraph(pdf: PDF, text: str):
    """Escreve um parágrafo simples, respeitando a largura."""
    pdf.set_font("Arial", "", 10)
    lines = text.split("\n")
    for line in lines:
        pdf.multi_cell(0, 5, sanitize_text(line), 0, 1)
    pdf.ln(3)

def draw_key_value_table(pdf: PDF, data: dict, col_widths=None):
    """
    Gera uma pequena tabela de chave e valor.
    data deve ser um dicionário: {chave: valor, ...}.
    """
    if not data:
        return

    if col_widths is None:
        # Calcular automaticamente
        page_width = pdf.w - 2*pdf.l_margin
        col_widths = [page_width * 0.3, page_width * 0.7]

    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(220, 220, 220)  # fundo cinza para cabeçalho
    # Cabeçalho
    pdf.cell(col_widths[0], 6, sanitize_text("Campo"), 1, 0, "C", fill=True)
    pdf.cell(col_widths[1], 6, sanitize_text("Valor"), 1, 1, "C", fill=True)

    # Conteúdo
    pdf.set_font("Arial", "", 10)
    pdf.set_fill_color(255, 255, 255)
    for k, v in data.items():
        k_sanit = sanitize_text(k)
        v_sanit = sanitize_text(v)
        pdf.cell(col_widths[0], 6, k_sanit, 1, 0, "L", fill=False)
        pdf.cell(col_widths[1], 6, v_sanit, 1, 1, "L", fill=False)
    pdf.ln(5)

def draw_table(pdf: PDF, table_data: list, headers: list):
    """
    Desenha uma tabela com cabeçalho. 
    table_data é uma lista de dicionários ou de listas, 
    headers é a lista dos nomes das colunas.
    """
    if not table_data or not headers:
        return

    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(220, 220, 220)
    page_width = pdf.w - 2*pdf.l_margin

    col_width = page_width / len(headers)
    # Cabeçalho
    for h in headers:
        pdf.cell(col_width, 6, sanitize_text(h), 1, 0, "C", fill=True)
    pdf.ln(6)

    # Linhas
    pdf.set_font("Arial", "", 10)
    pdf.set_fill_color(255, 255, 255)

    for row in table_data:
        # Se for dicionário, extrair na ordem exata de headers
        # Se for lista/tupla, usar por índice
        if isinstance(row, dict):
            for h in headers:
                cell_text = sanitize_text(str(row.get(h, "")))
                pdf.cell(col_width, 6, cell_text, 1, 0, "C", fill=False)
        elif isinstance(row, (list, tuple)):
            for i, val in enumerate(row):
                cell_text = sanitize_text(str(val))
                pdf.cell(col_width, 6, cell_text, 1, 0, "C", fill=False)
        pdf.ln(6)
    pdf.ln(3)

########################################
# Nova Função de Criação do PDF        #
########################################

def create_pdf(df: pd.DataFrame) -> PDF:
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for _, row in df.iterrows():
        pdf.add_page()

        # Cabeçalho da iniciativa
        pdf.set_font("Arial", "B", 14)
        iniciativa_title = f"Iniciativa: {row['nome_iniciativa']}"
        pdf.cell(0, 10, sanitize_text(iniciativa_title), 0, 1, "L")
        pdf.ln(5)

        # Seção: Objetivo Geral
        draw_section_title(pdf, "Objetivo Geral")
        objetivo_geral = remove_html_for_pdf(str(row['objetivo_geral']))
        draw_simple_paragraph(pdf, objetivo_geral)

        # Seção: Objetivos Específicos
        draw_section_title(pdf, "Objetivos Específicos")
        obj_espec = remove_html_for_pdf(format_objetivos_especificos(row['objetivos_especificos']))
        draw_simple_paragraph(pdf, obj_espec)

        # Seção: Introdução
        draw_section_title(pdf, "Introdução")
        intro = remove_html_for_pdf(row['introducao'])
        draw_simple_paragraph(pdf, intro)

        # Seção: Justificativa
        draw_section_title(pdf, "Justificativa")
        justif = remove_html_for_pdf(row['justificativa'])
        draw_simple_paragraph(pdf, justif)

        # Seção: Metodologia
        draw_section_title(pdf, "Metodologia")
        met = remove_html_for_pdf(row['metodologia'])
        draw_simple_paragraph(pdf, met)

        # Seção: Eixos Temáticos
        draw_section_title(pdf, "Eixos Temáticos")
        eixos_text = remove_html_for_pdf(format_eixos_tematicos(row.get('eixos_tematicos', '')))
        draw_simple_paragraph(pdf, eixos_text)

        # Seção: Insumos (simples)
        draw_section_title(pdf, "Insumos")
        insumos_text = remove_html_for_pdf(format_insumos(row.get('insumos', '')))
        draw_simple_paragraph(pdf, insumos_text)

        # Seção: Distribuição por Unidade (virando tabela)
        draw_section_title(pdf, "Distribuição por Unidade")
        distr_str = row.get('distribuicao_ucs', '')
        try:
            distr_data = json.loads(distr_str) if distr_str else []
        except:
            distr_data = []
        if isinstance(distr_data, list) and len(distr_data) > 0:
            # Vamos montar a tabela
            headers = ["Unidade", "Acao", "Valor Alocado"]
            draw_table(pdf, distr_data, headers)
        else:
            draw_simple_paragraph(pdf, "Nenhuma informação sobre distribuição de unidades.")

        # Seção: Formas de Contratação
        draw_section_title(pdf, "Formas de Contratação")
        formas_str = row.get('formas_contratacao', '')
        try:
            formas_json = json.loads(formas_str) if formas_str else {}
        except:
            formas_json = {}

        tabela_formas = formas_json.get("tabela_formas", [])
        detalhes_formas = formas_json.get("detalhes", {})

        if tabela_formas:
            # Montar tabela para as formas de contratação
            data_table = []
            for item in tabela_formas:
                forma = item.get("Forma de Contratação", "Sem descrição")
                selecionado = "Selecionado" if item.get("Selecionado", False) else "Não Selecionado"
                data_table.append([forma, selecionado])
            headers_formas = ["Forma de Contratação", "Status"]
            draw_table(pdf, data_table, headers_formas)
        else:
            draw_simple_paragraph(pdf, "Não há formas de contratação listadas.")

        if detalhes_formas:
            # Mostrar detalhes em tabela key-value
            # Convertendo tudo para string
            detalhes_dic = {}
            for k, v in detalhes_formas.items():
                if isinstance(v, list):
                    v = ", ".join(map(str, v)) if v else "Não informado"
                elif not v:
                    v = "Não informado"
                detalhes_dic[k] = str(v)
            draw_section_title(pdf, "Detalhes das Formas de Contratação")
            draw_key_value_table(pdf, detalhes_dic)

        # Seção: Demais Informações
        draw_section_title(pdf, "Demais Informações")
        demais_info = remove_html_for_pdf(process_generic_json(row.get('demais_informacoes', '')))
        draw_simple_paragraph(pdf, demais_info)

        # Responsável e Data/Hora
        pdf.set_font("Arial", "I", 10)
        usuario_resp = f"Responsável: {row['usuario']}"
        data_reg = datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
        pdf.cell(0, 8, sanitize_text(f"{usuario_resp} | Data/Hora: {data_reg}"), 0, 1, "L")

        # Linha divisória
        pdf.ln(3)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(5)

    return pdf

########################################
# CSS para Layout na Interface         #
########################################

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

########################################
# Seleção de Iniciativa e Exibição     #
########################################

# O setor é obtido da sessão do usuário
setor_selecionado = st.session_state.get("setor", "Não informado")

# Carrega as iniciativas do setor do usuário
df_iniciativas = load_iniciativas(setor_selecionado)
if df_iniciativas.empty:
    st.info("ℹ️ Nenhuma iniciativa encontrada para o seu setor.")
    st.stop()

# O usuário seleciona a iniciativa desejada
nomes_iniciativas = df_iniciativas['nome_iniciativa'].unique().tolist()
iniciativa_selecionada = st.selectbox("Selecione a iniciativa", nomes_iniciativas)
df_filtrado = df_iniciativas[df_iniciativas['nome_iniciativa'] == iniciativa_selecionada]

# Exibe os detalhes da iniciativa na interface (em cards)
st.markdown("<div class='card-container'>", unsafe_allow_html=True)
for idx, row in df_filtrado.iterrows():
    card_html = f"""
    <div class="card">
        <div class="card-section">
            <h3>{html.escape(row['nome_iniciativa'])}</h3>
        </div>
        <div class="card-section">
            <div class="card-section-title">Objetivo Geral</div>
            {html.escape(row['objetivo_geral']).replace("\n", "<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Objetivos Específicos</div>
            {format_objetivos_especificos(row['objetivos_especificos'])}
        </div>
        <div class="card-section">
            <div class="card-section-title">Introdução</div>
            {html.escape(row['introducao']).replace("\n", "<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Justificativa</div>
            {html.escape(row['justificativa']).replace("\n", "<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Metodologia</div>
            {html.escape(row['metodologia']).replace("\n", "<br>")}
        </div>
        <div class="card-section">
            <div class="card-section-title">Eixos Temáticos</div>
            {format_eixos_tematicos(row.get('eixos_tematicos', ''))}
        </div>
        <div class="card-section">
            <div class="card-section-title">Insumos</div>
            {format_insumos(row.get('insumos', ''))}
        </div>
        <div class="card-section">
            <div class="card-section-title">Distribuição por Unidade</div>
            {format_distribuicao_ucs(row.get('distribuicao_ucs', ''))}
        </div>
        <div class="card-section">
            <div class="card-section-title">Formas de Contratação</div>
            {format_formas_contratacao(row.get('formas_contratacao', ''))}
        </div>
        <div class="card-section">
            <div class="card-section-title">Demais Informações</div>
            {process_generic_json(row.get('demais_informacoes', '')).replace("\n", "<br>")}
        </div>
        <div style="margin-top: 15px;">
            <span class="badge">Responsável: {html.escape(row['usuario'])}</span>
            <span class="badge">Data/Hora: {datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')}</span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

########################################
# Geração do PDF                       #
########################################

if st.button("📄 Gerar Extrato Completo em PDF", type='secondary'):
    with st.spinner("Gerando Extrato em PDF..."):
        pdf = create_pdf(df_filtrado)
        # Gera os bytes do PDF (texto já sanitizado)
        pdf_bytes = pdf.output(dest="S").encode("latin1", errors="replace")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        st.download_button(
            label="⬇️ Download do Extrato (PDF)",
            data=pdf_bytes,
            file_name=f"extrato_iniciativa_{iniciativa_selecionada}.pdf",
            mime="application/pdf"
        )
        pdf_viewer(tmp_path)

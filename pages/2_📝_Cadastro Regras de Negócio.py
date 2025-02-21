###############################################################################
#                          IMPORTS E CONFIGURAÇÕES
###############################################################################

import streamlit as st
import json
import pandas as pd
import time as time
import psycopg2
from sqlalchemy import create_engine

# Cria o engine SQLAlchemy para evitar os avisos do pandas
engine = create_engine("postgresql+psycopg2://postgres:asd@10.197.42.64/teste")

# -----------------------------------------------------------------------------
#                     Função para conexão com o PostgreSQL
# -----------------------------------------------------------------------------
def get_connection():
    return psycopg2.connect(
        host="10.197.42.64",
        database="teste",
        user="postgres",
        password="asd"
    )

# -----------------------------------------------------------------------------
#                     Verificação de Login e Configurações de Página
# -----------------------------------------------------------------------------
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login.")
    st.stop()

st.set_page_config(
    page_title="Cadastro de Regras de Negócio",
    page_icon=":infinity:",
    layout="wide"
)

# CSS Customizado para modais
st.markdown("""
    <style>
        div[data-modal-container='true'] {
            z-index: 1002 !important;
        }
        .stDataEditor div[data-testid="stVerticalBlock"] {
            gap: 0.2rem;
        }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
#                          FUNÇÕES AUXILIARES / CACHED
# -----------------------------------------------------------------------------
@st.cache_data
def get_iniciativas_usuario(perfil: str, setor: str) -> pd.DataFrame:
    """
    Retorna as iniciativas disponíveis para o usuário,
    filtradas por perfil e setor, se não for 'admin'.
    """
    query = "SELECT id_iniciativa, nome_iniciativa FROM td_iniciativas"
    if perfil != "admin":
        query += """
            WHERE id_iniciativa IN (
               SELECT id_iniciativa 
               FROM tf_cadastros_iniciativas 
               WHERE id_demandante = (
                  SELECT id_demandante FROM td_demandantes WHERE nome_demandante = %s
               )
            )
        """
        iniciativas = pd.read_sql_query(query, engine, params=(setor,))
    else:
        iniciativas = pd.read_sql_query(query, engine)
    return iniciativas


@st.cache_data
def carregar_dados_iniciativa(id_iniciativa: int) -> dict | None:
    """
    Carrega a última linha de tf_cadastro_regras_negocio para a iniciativa dada.
    Retorna um dicionário com as colunas esperadas ou None se não existir.
    """
    query = """
        SELECT *
        FROM tf_cadastro_regras_negocio
        WHERE id_iniciativa = %s
        ORDER BY data_hora DESC
        LIMIT 1
    """
    df = pd.read_sql_query(query, engine, params=(id_iniciativa,))
    if df.empty:
        return None
    row = df.iloc[0]
    try:
        eixos_tematicos = json.loads(row["eixos_tematicos"]) if row["eixos_tematicos"] else []
    except:
        eixos_tematicos = []
    info_json = row.get("demais_informacoes", "") or ""
    try:
        info_dict = json.loads(info_json) if info_json else {}
    except:
        info_dict = {}
    return {
        "objetivo_geral":         row["objetivo_geral"],
        "objetivos_especificso":  row["objetivos_especificos"],
        "eixos_tematicos":        row["eixos_tematicos"],
        "introducao":             row.get("introducao", ""),
        "justificativa":          row.get("justificativa", ""),
        "metodologia":            row.get("metodologia", ""),
        "demais_informacoes":     info_dict
    }


@st.cache_data
def carregar_resumo_iniciativa(setor: str) -> pd.DataFrame | None:
    """
    Carrega o resumo a partir de td_dados_resumos_sei, filtrando por 'demandante' = setor.
    Retorna um DataFrame ou None se vazio.
    """
    query = "SELECT * FROM td_dados_resumos_sei WHERE demandante = %s"
    df = pd.read_sql_query(query, engine, params=(setor,))
    if df.empty:
        return None
    return df


def salvar_dados_iniciativa(
    id_iniciativa: int,
    usuario: str,
    objetivo_geral: str,
    objetivos_especificos: list[str],
    eixos_tematicos: list[dict],
    introducao: str,
    justificativa: str,
    metodologia: str,
    demais_informacoes: dict
):
    """
    Salva registro na tf_cadastro_regras_negocio, mantendo histórico máximo de 3 registros.
    Também atualiza as colunas "acoes_manejo" e "insumos" com base nos eixos.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM tf_cadastro_regras_negocio
        WHERE id_iniciativa = %s
    """, (id_iniciativa,))
    total_reg = cursor.fetchone()[0]
    if total_reg >= 3:
        cursor.execute("""
            DELETE FROM tf_cadastro_regras_negocio
            WHERE id IN (
                SELECT id
                FROM tf_cadastro_regras_negocio
                WHERE id_iniciativa = %s
                ORDER BY data_hora ASC
                LIMIT 1
            )
        """, (id_iniciativa,))

    objetivos_json = json.dumps(objetivos_especificos or [])
    eixos_json     = json.dumps(eixos_tematicos or [])

    acoes_set   = set()
    insumos_set = set()
    for eixo in eixos_tematicos:
        for ac_id, ac_data in eixo.get("acoes_manejo", {}).items():
            acoes_set.add(ac_id)
            for ins_id in ac_data.get("insumos", []):
                insumos_set.add(ins_id)
    acoes_json  = json.dumps(list(acoes_set))
    insumos_json = json.dumps(list(insumos_set))

    final_rule = {
        "objetivo_geral": objetivo_geral,
        "objetivos_especificos": objetivos_especificos,
        "eixos_tematicos": eixos_tematicos,
        "acoes": list(acoes_set),
        "insumos": list(insumos_set)
    }
    regra_json = json.dumps(final_rule)
    demais_info_json = json.dumps(demais_informacoes) if demais_informacoes else "{}"

    if "df_uc_editado" in st.session_state and not st.session_state["df_uc_editado"].empty:
        distribuicao_ucs_json = st.session_state["df_uc_editado"].to_json(orient="records", force_ascii=False)
    else:
        distribuicao_ucs_json = "[]"

    if "formas_contratacao_detalhes" in st.session_state:
        formas_completo_json = json.dumps(st.session_state["formas_contratacao_detalhes"], ensure_ascii=False)
    else:
        formas_completo_json = "{}"

    cursor.execute("""
        INSERT INTO tf_cadastro_regras_negocio (
            id_iniciativa,
            usuario,
            objetivo_geral,
            objetivos_especificos,
            eixos_tematicos,
            acoes_manejo,
            insumos,
            regra,
            introducao,
            justificativa,
            metodologia,
            demais_informacoes,
            distribuicao_ucs,
            formas_contratacao
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        id_iniciativa,
        usuario,
        objetivo_geral,
        objetivos_json,
        eixos_json,
        acoes_json,
        insumos_json,
        regra_json,
        introducao,
        justificativa,
        metodologia,
        demais_info_json,
        distribuicao_ucs_json,
        formas_completo_json
    ))

    conn.commit()
    cursor.close()
    conn.close()


@st.cache_data
def get_options_from_table(
    table_name: str,
    id_col: str,
    name_col: str,
    filter_col: str | None = None,
    filter_val: str | None = None
) -> dict[str, str]:
    """
    Lê da tabela `table_name` as colunas `id_col` e `name_col`.
    Opcionalmente filtra por `filter_col = filter_val`.
    Retorna um dict { id_val: name_val }.
    """
    query = f"SELECT {id_col}, {name_col} FROM {table_name}"
    params = ()
    if filter_col and filter_val is not None:
        query += f" WHERE {filter_col} = %s"
        params = (str(filter_val),)
    df = pd.read_sql_query(query, engine, params=params)
    return {str(row[id_col]): row[name_col] for _, row in df.iterrows()}


# -----------------------------------------------------------------------------
#            Inicialização para evitar KeyError no session_state
# -----------------------------------------------------------------------------

for key in ["introducao", "justificativa", "metodologia", "objetivo_geral"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "demais_informacoes" not in st.session_state:
    st.session_state["demais_informacoes"] = {}

if "objetivos_especificos" not in st.session_state:
    st.session_state["objetivos_especificos"] = []

if "eixos_tematicos" not in st.session_state:
    st.session_state["eixos_tematicos"] = []

if "df_uc_editado" not in st.session_state:
    st.session_state["df_uc_editado"] = pd.DataFrame()

if "insumos" not in st.session_state:
    st.session_state["insumos"] = {}

# -----------------------------------------------------------------------------
#          Função para exibir informações complementares na barra lateral
# -----------------------------------------------------------------------------
def exibir_info_lateral(id_iniciativa: int):
    """Exibe no sidebar informações complementares da iniciativa."""
    conn = get_connection()
    cursor = conn.cursor()

    st.sidebar.write("### Informações da Iniciativa")

    query_inic = """
    SELECT ci.id_demandante,
           COUNT(DISTINCT ci.cnuc) AS num_unidades,
           d.nome_demandante
    FROM tf_cadastros_iniciativas ci
    JOIN td_demandantes d ON ci.id_demandante = d.id_demandante
    WHERE ci.id_iniciativa = %s
    GROUP BY ci.id_demandante
    """
    cursor.execute(query_inic, (id_iniciativa,))
    row_inic = cursor.fetchone()
    if row_inic:
        _, num_unidades, nome_demandante = row_inic
        st.sidebar.write(f"**Demandante:** {nome_demandante}")
        st.sidebar.write(f"**Número de Unidades:** {num_unidades}")
    else:
        st.sidebar.info("Iniciativa não encontrada em tf_cadastros_iniciativas.")

    cursor.execute("""
        SELECT diretoria, coordenação_geral, coordenação
        FROM td_dados_resumos_sei
        WHERE id_resumo = %s
        LIMIT 1
    """, (id_iniciativa,))
    row_resumo = cursor.fetchone()
    if row_resumo:
        dir_, coord_geral, coord_ = row_resumo
        st.sidebar.write(f"**Diretoria:** {dir_ if dir_ else 'sem informação'}")
        st.sidebar.write(f"**Coord. Geral:** {coord_geral if coord_geral else 'sem informação'}")
        st.sidebar.write(f"**Coordenação:** {coord_ if coord_ else 'sem informação'}")
    else:
        st.sidebar.info("Sem resumo SEI cadastrado para esta iniciativa.")

    cursor.execute("""
        SELECT eixos_tematicos
        FROM tf_cadastro_regras_negocio
        WHERE id_iniciativa = %s
        ORDER BY data_hora DESC
        LIMIT 1
    """, (id_iniciativa,))
    row_eixos = cursor.fetchone()
    cursor.close()
    conn.close()

    if row_eixos:
        eixos_tematicos_json = row_eixos[0]
        if eixos_tematicos_json:
            eixos_list = json.loads(eixos_tematicos_json)
            nomes = [e.get("nome_eixo", "Eixo Sem Nome") for e in eixos_list]
            st.sidebar.pills(
                "Eixos Temáticos gravados:",
                options=nomes,
                default=None,
                disabled=True
            )
        else:
            st.sidebar.info("Nenhum eixo temático cadastrado no momento.")
    else:
        st.sidebar.info("Nenhum eixo temático cadastrado.")


# -----------------------------------------------------------------------------
#                           Início da Página
# -----------------------------------------------------------------------------
st.subheader("📝 Cadastro de Regras de Negócio")

perfil      = st.session_state["perfil"]
setor       = st.session_state["setor"]
cpf_usuario = st.session_state["cpf"]

iniciativas = get_iniciativas_usuario(perfil, setor)
if iniciativas.empty:
    st.warning("🚫 Nenhuma iniciativa disponível para você.")
    st.stop()

nova_iniciativa = st.selectbox(
    "Selecione a Iniciativa:",
    options=iniciativas["id_iniciativa"],
    format_func=lambda x: iniciativas.set_index("id_iniciativa").loc[x, "nome_iniciativa"],
    key="sel_iniciativa"
)

st.caption("ℹ️ Informações Originais do Resumo Executivo de Iniciativas disponíveis no final da página", help="ref.: documentos SEI")

if "carregou_iniciativa" not in st.session_state or st.session_state["carregou_iniciativa"] != nova_iniciativa:
    df_dados = pd.read_sql_query("""
        SELECT objetivo_geral, objetivos_especificos, eixos_tematicos,
               introducao, justificativa, metodologia, demais_informacoes
        FROM tf_cadastro_regras_negocio
        WHERE id_iniciativa = %s
        ORDER BY data_hora DESC
        LIMIT 1
    """, engine, params=(nova_iniciativa,))
    
    if not df_dados.empty:
        row = df_dados.iloc[0]
        try:
            objetivos_especificos = json.loads(row["objetivos_especificos"]) if row["objetivos_especificos"] else []
        except:
            objetivos_especificos = []
        st.session_state["objetivo_geral"] = row["objetivo_geral"]
        st.session_state["objetivos_especificos"] = objetivos_especificos
        try:
            st.session_state["eixos_tematicos"] = json.loads(row["eixos_tematicos"]) if row["eixos_tematicos"] else []
        except:
            st.session_state["eixos_tematicos"] = []
        st.session_state["introducao"] = row["introducao"]
        st.session_state["justificativa"] = row["justificativa"]
        st.session_state["metodologia"] = row["metodologia"]
        try:
            st.session_state["demais_informacoes"] = json.loads(row["demais_informacoes"]) if row["demais_informacoes"] else {}
        except:
            st.session_state["demais_informacoes"] = {}
    else:
        st.session_state["objetivo_geral"] = ""
        st.session_state["objetivos_especificos"] = []
        st.session_state["eixos_tematicos"] = []
        st.session_state["introducao"] = ""
        st.session_state["justificativa"] = ""
        st.session_state["metodologia"] = ""
        st.session_state["demais_informacoes"] = {}
        if not st.session_state["objetivo_geral"]:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT objetivo_geral FROM td_dados_resumos_sei
                WHERE id_resumo = %s LIMIT 1
            """, (nova_iniciativa,))
            row_fallback = cursor.fetchone()
            cursor.close()
            conn.close()
            if row_fallback:
                obj_geral_sei = row_fallback[0] or ""
                if obj_geral_sei:
                    st.session_state["objetivo_geral"] = obj_geral_sei
        if not st.session_state["introducao"] or not st.session_state["justificativa"] or not st.session_state["metodologia"]:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT introdução, justificativa, metodologia
                FROM td_dados_resumos_sei
                WHERE id_resumo = %s
                LIMIT 1
            """, (nova_iniciativa,))
            row_resumo_2 = cursor.fetchone()
            cursor.close()
            conn.close()
            if row_resumo_2:
                intro_sei, justif_sei, metod_sei = row_resumo_2
                if not st.session_state["introducao"] and intro_sei:
                    st.session_state["introducao"] = intro_sei
                if not st.session_state["justificativa"] and justif_sei:
                    st.session_state["justificativa"] = justif_sei
                if not st.session_state["metodologia"] and metod_sei:
                    st.session_state["metodologia"] = metod_sei
    st.session_state["carregou_iniciativa"] = nova_iniciativa

if st.sidebar.checkbox("Exibir informações da iniciativa", value=True):
    exibir_info_lateral(nova_iniciativa)

st.divider()
st.write(f"**Iniciativa Selecionada:** {iniciativas.set_index('id_iniciativa').loc[nova_iniciativa, 'nome_iniciativa']}")

tab_intro, tab_obj, tab_justif, tab_metod, tab_demandante, tab_eixos, tab_insumos, tab_uc, tab_forma_contratacao = st.tabs([
    "Introdução",
    "Objetivos",
    "Justificativa",
    "Metodologia",
    "Demandante",
    "Eixos Temáticos",
    "Insumos",
    "Unidades de Conservação",
    "Formas de Contratação"
])

with st.form("form_textos_resumo"):
    with tab_obj:
        st.subheader("Objetivo Geral")
        st.session_state["objetivo_geral"] = st.text_area(
            "Descreva o Objetivo Geral:",
            value=st.session_state["objetivo_geral"],
            height=140
        )
        st.subheader("Objetivos Específicos")
        if "objetivos_especificos" not in st.session_state:
            st.session_state["objetivos_especificos"] = []
        def adicionar_objetivo_callback():
            texto_novo = st.session_state.txt_novo_objetivo.strip()
            if texto_novo:
                st.session_state["objetivos_especificos"].append(texto_novo)
                st.session_state.txt_novo_objetivo = ""
            else:
                st.warning("O texto do objetivo está vazio. Por favor, digite algo antes de adicionar.")
        st.text_area(
            label="Digite o texto do objetivo específico a ser adicionado e clique no botão:",
            key="txt_novo_objetivo",
            height=80
        )
        st.button(
            label="Adicionar Objetivo",
            on_click=adicionar_objetivo_callback
        )
        st.write("---")
        st.write("*Objetivos adicionados:*")
        col1, col2, col3 = st.columns([1, 8, 3])
        col1.write("**#**")
        col2.write("**Objetivo**")
        col3.write("*Edição e Exclusão*")
        for i, objetivo in enumerate(st.session_state["objetivos_especificos"]):
            c1, c2, c3 = st.columns([1, 6, 3])
            c1.write(f"{i + 1}")
            c2.write(objetivo)
            with c3:
                col_edit, col_remove = st.columns([1, 1])
                with col_edit:
                    with st.popover(label=f"✏️"):
                        st.subheader(f"Editar Objetivo {i+1}")
                        novo_texto = st.text_area("Texto do objetivo:", objetivo, key=f"edit_obj_{i}")
                        if st.button("Salvar Edição", key=f"btn_save_edit_{i}"):
                            st.session_state["objetivos_especificos"][i] = novo_texto
                            st.rerun()
                with col_remove:
                    if st.button("🗑️", key=f"btn_remove_{i}"):
                        del st.session_state["objetivos_especificos"][i]
                        st.rerun()
    with tab_intro:
        st.subheader("Introdução")
        st.session_state["introducao"] = st.text_area(
            "Texto de Introdução:",
            value=st.session_state["introducao"],
            height=300
        )
    with tab_justif:
        st.subheader("Justificativa")
        st.session_state["justificativa"] = st.text_area(
            "Texto de Justificativa:",
            value=st.session_state["justificativa"],
            height=300
        )
    with tab_metod:
        st.subheader("Metodologia")
        st.session_state["metodologia"] = st.text_area(
            "Texto de Metodologia:",
            value=st.session_state["metodologia"],
            height=300
        )
    with tab_demandante:
        st.subheader("Demais Informações")
        st.caption("Edição de Informações do Setor Demandante.")
        if not st.session_state.get("demais_informacoes"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT diretoria, coordenação_geral, coordenação, demandante
                FROM td_dados_resumos_sei
                WHERE id_resumo = %s
                LIMIT 1
            """, (nova_iniciativa,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                st.session_state["demais_informacoes"] = {
                    "diretoria": row[0] or "",
                    "coordenacao_geral": row[1] or "",
                    "coordenacao": row[2] or "",
                    "demandante": row[3] or ""
                }
            else:
                st.session_state["demais_informacoes"] = {
                    "diretoria": "",
                    "coordenacao_geral": "",
                    "coordenacao": "",
                    "demandante": ""
                }
        if not isinstance(st.session_state["demais_informacoes"], dict):
            try:
                st.session_state["demais_informacoes"] = json.loads(st.session_state["demais_informacoes"])
            except:
                st.session_state["demais_informacoes"] = {}
        di = st.session_state["demais_informacoes"].get("diretoria", "")
        cg = st.session_state["demais_informacoes"].get("coordenacao_geral", "")
        co = st.session_state["demais_informacoes"].get("coordenação", "")
        dm = st.session_state["demais_informacoes"].get("demandante", "")
        st.caption("Preencha os campos abaixo conforme necessário:")
        diretoria_novo    = st.text_input("Diretoria:", value=di)
        coord_geral_novo  = st.text_input("Coordenação Geral:", value=cg)
        coord_novo        = st.text_input("Coordenação:", value=co)
        demandante_novo   = st.text_input("Demandante (Sigla):", value=dm, disabled=True)
    with tab_eixos:
        st.subheader("Eixos Temáticos")
        eixos_opcoes = get_options_from_table("td_samge_processos", "id_p", "nome")
        novo_eixo_id = st.selectbox(
            "Escolha um Eixo (Processo SAMGe) para adicionar:",
            options=[None] + sorted(eixos_opcoes.keys(), key=lambda x: eixos_opcoes[x]),
            format_func=lambda x: eixos_opcoes.get(x, "Selecione..."),
            key="sel_novo_eixo"
        )
        if st.button("➕ Adicionar Eixo Temático", key="btn_add_eixo"):
            if novo_eixo_id is None:
                st.warning("Selecione um eixo válido antes de adicionar.")
            else:
                eixo_id_int = int(novo_eixo_id)
                ids_existentes = [int(e["id_eixo"]) for e in st.session_state["eixos_tematicos"]]
                if eixo_id_int not in ids_existentes:
                    novo_eixo = {
                        "id_eixo": eixo_id_int,
                        "nome_eixo": eixos_opcoes.get(str(novo_eixo_id), "Novo Eixo"),
                        "acoes_manejo": {}
                    }
                    st.session_state["eixos_tematicos"].append(novo_eixo)
                    st.session_state["insumos"] = {}
                    st.rerun()
                else:
                    st.info("Este eixo já está na lista.")
        for i, eixo in enumerate(st.session_state["eixos_tematicos"]):
            with st.expander(f"📌 {eixo['nome_eixo']}", expanded=False):
                acoes_dict = get_options_from_table(
                    "td_samge_acoes_manejo", "id_ac", "nome",
                    filter_col="processo_id", filter_val=eixo["id_eixo"]
                )
                acoes_df = pd.DataFrame([
                    {"ID": ac_id, "Ação": nome, "Selecionado": ac_id in eixo.get("acoes_manejo", {})}
                    for ac_id, nome in acoes_dict.items()
                ])
                if "Selecionado" not in acoes_df.columns:
                    acoes_df["Selecionado"] = False
                with st.form(f"form_acoes_{i}"):
                    edited_acoes = st.data_editor(
                        acoes_df,
                        column_config={
                            "ID": st.column_config.TextColumn(disabled=True),
                            "Ação": st.column_config.TextColumn(disabled=True),
                            "Selecionado": st.column_config.CheckboxColumn("Selecionar")
                        },
                        hide_index=True,
                        use_container_width=True,
                        key=f"editor_acoes_{i}"
                    )
                    if st.form_submit_button("Salvar Ações"):
                        selecionadas = edited_acoes.loc[edited_acoes["Selecionado"], "ID"].tolist()
                        eixo["acoes_manejo"] = {ac_id: {"insumos": []} for ac_id in selecionadas}
                        st.session_state["eixos_tematicos"][i] = eixo
                        st.success("Ações atualizadas!")
                if st.button("🗑️ Excluir Eixo", key=f"btn_del_{i}"):
                    del st.session_state["eixos_tematicos"][i]
                    st.rerun()
    with tab_insumos:
        st.subheader("Insumos por Ação")
        df_insumos_all = pd.read_sql_query(
            "SELECT id, elemento_despesa, especificacao_padrao, descricao_insumo FROM td_insumos",
            engine
        )
        if "insumos_selecionados" not in st.session_state:
            st.session_state["insumos_selecionados"] = {}
        for i, eixo in enumerate(st.session_state["eixos_tematicos"]):
            with st.expander(f"📌 {eixo['nome_eixo']}", expanded=False):
                for ac_id, ac_data in eixo["acoes_manejo"].items():
                    st.markdown(
                        f"### Ação: {get_options_from_table('td_samge_acoes_manejo', 'id_ac', 'nome').get(ac_id, 'Ação Desconhecida')}"
                    )
                    if ac_id not in st.session_state["insumos_selecionados"]:
                        st.session_state["insumos_selecionados"][ac_id] = set(ac_data.get("insumos", []))
                    col_filtro_elemento, col_filtro_espec = st.columns([5, 5])
                    elementos_unicos = ["Todos"] + sorted(df_insumos_all["elemento_despesa"].dropna().unique())
                    with col_filtro_elemento:
                        elemento_selecionado = st.selectbox(
                            "Selecione o Elemento de Despesa",
                            elementos_unicos,
                            key=f"elemento_{i}_{ac_id}"
                        )
                    df_filtrado = (df_insumos_all if elemento_selecionado == "Todos"
                                   else df_insumos_all[df_insumos_all["elemento_despesa"] == elemento_selecionado])
                    especificacoes_unicas = ["Todos"] + sorted(df_filtrado["especificacao_padrao"].dropna().unique())
                    with col_filtro_espec:
                        especificacao_selecionada = st.selectbox(
                            "Selecione a Especificação Padrão",
                            especificacoes_unicas,
                            key=f"especificacao_{i}_{ac_id}"
                        )
                    if especificacao_selecionada != "Todos":
                        df_filtrado = df_filtrado[df_filtrado["especificacao_padrao"] == especificacao_selecionada]
                    df_combo = df_filtrado.rename(
                        columns={
                            "id": "ID",
                            "descricao_insumo": "Insumo"
                        }
                    )
                    sel_ids = st.session_state["insumos_selecionados"][ac_id]
                    df_combo["Selecionado"] = df_combo["ID"].apply(lambda x: x in sel_ids)
                    with st.form(f"form_insumos_{i}_{ac_id}"):
                        edited_ins = st.data_editor(
                            df_combo[["ID", "Insumo", "Selecionado"]],
                            column_config={
                                "ID": st.column_config.TextColumn("Cód. Insumo", disabled=True),
                                "Insumo": st.column_config.TextColumn("Descrição do Insumo", disabled=True),
                                "Selecionado": st.column_config.CheckboxColumn("Selecionar")
                            },
                            hide_index=True,
                            use_container_width=True,
                            key=f"editor_ins_{i}_{ac_id}"
                        )
                        if st.form_submit_button("Salvar Insumos"):
                            selecionados_agora = set(edited_ins.loc[edited_ins["Selecionado"], "ID"])
                            for item_id in df_combo["ID"]:
                                if item_id in selecionados_agora:
                                    sel_ids.add(item_id)
                                else:
                                    if item_id in sel_ids:
                                        sel_ids.remove(item_id)
                            st.session_state["insumos_selecionados"][ac_id] = sel_ids
                            ac_data["insumos"] = list(sel_ids)
                            st.success("Seleção atualizada (sem perder itens já escolhidos em outros filtros)!")
                    if st.button("Limpar Lista de Insumos", key=f"limpar_{i}_{ac_id}"):
                        st.session_state["insumos_selecionados"][ac_id] = set()
                        ac_data["insumos"] = []
                        st.success("Todos os insumos foram removidos para esta ação!")
                    st.write("---")
    with tab_uc:
        st.subheader("Distribuição de Recursos por Eixo")
        query = """
            SELECT 
                "Unidade de Conservação" AS Unidade,
                "AÇÃO DE APLICAÇÃO" AS Acao,
                "VALOR TOTAL ALOCADO" AS "Valor Alocado"
            FROM tf_cadastros_iniciativas
            WHERE id_iniciativa = %s
            AND "VALOR TOTAL ALOCADO" > 0
        """
        df_unidades_raw = pd.read_sql_query(query, engine, params=(nova_iniciativa,))
        if df_unidades_raw.empty:
            st.warning("Nenhuma unidade de conservação encontrada para esta iniciativa.")
        else:
            if "df_uc_editado" not in st.session_state:
                st.session_state["df_uc_editado"] = df_unidades_raw.copy()
            else:
                if st.session_state["df_uc_editado"].empty:
                    st.session_state["df_uc_editado"] = df_unidades_raw.copy()
            def recalcular_saldo():
                data_dict = st.session_state["editor_uc"]
                df_master = st.session_state["df_uc_editado"].copy()
                edited_rows = data_dict.get("edited_rows", {})
                for row_idx_str, changed_cols in edited_rows.items():
                    row_idx = int(row_idx_str)
                    for col_name, new_value in changed_cols.items():
                        df_master.loc[row_idx, col_name] = new_value
                df_master["Valor Alocado"] = pd.to_numeric(df_master["Valor Alocado"], errors="coerce").fillna(0)
                for eixo_nome in colunas_eixos:
                    if eixo_nome not in df_master.columns:
                        df_master[eixo_nome] = 0
                    df_master[eixo_nome] = pd.to_numeric(df_master[eixo_nome], errors="coerce").fillna(0)
                df_master["Distribuir"] = df_master["Valor Alocado"] - df_master[colunas_eixos].sum(axis=1)
                st.session_state["df_uc_editado"] = df_master
            df_editavel = st.session_state["df_uc_editado"].copy()
            colunas_fixas = ["Unidade", "Acao", "Valor Alocado"]
            for col in colunas_fixas:
                if col not in df_editavel.columns:
                    df_editavel[col] = 0
            colunas_eixos = [eixo["nome_eixo"] for eixo in st.session_state["eixos_tematicos"]]
            for eixo_nome in colunas_eixos:
                if eixo_nome not in df_editavel.columns:
                    df_editavel[eixo_nome] = 0
            df_editavel["Valor Alocado"] = pd.to_numeric(df_editavel["Valor Alocado"], errors="coerce").fillna(0)
            for eixo_nome in colunas_eixos:
                df_editavel[eixo_nome] = pd.to_numeric(df_editavel[eixo_nome], errors="coerce").fillna(0)
            df_editavel["Distribuir"] = df_editavel["Valor Alocado"] - df_editavel[colunas_eixos].sum(axis=1)
            colunas_ordenadas = colunas_fixas + ["Distribuir"] + colunas_eixos
            df_editavel = df_editavel[colunas_ordenadas]
            edited_df = st.data_editor(
                df_editavel,
                column_config={
                    "Unidade": st.column_config.TextColumn("Unidade de Conservação", disabled=True),
                    "Acao": st.column_config.TextColumn("Ação de Aplicação", disabled=True),
                    "Valor Alocado": st.column_config.NumberColumn("Valor Alocado", disabled=True),
                    "Distribuir": st.column_config.NumberColumn("Distribuir", disabled=True)
                },
                use_container_width=True,
                key="editor_uc",
                on_change=recalcular_saldo,
                hide_index=True
            )
            if st.button("Salvar Distribuição"):
                df_final = st.session_state["df_uc_editado"]
                st.success("Distribuição de recursos salva com sucesso!")
                # Aqui você pode realizar o update no banco
    with tab_forma_contratacao:
        st.title("Formas de Contratação")
        if "df_formas_contratacao" not in st.session_state:
            data = {
                "Forma de Contratação": [
                    "Contrato Caixa",
                    "Contrato ICMBio",
                    "Fundação de Apoio credenciada pelo ICMBio",
                    "Fundação de Amparo à pesquisa"
                ],
                "Selecionado": [False, False, False, False]
            }
            st.session_state["df_formas_contratacao"] = pd.DataFrame(data)
        with st.form("form_formas_contratacao"):
            df_editor = st.data_editor(
                st.session_state["df_formas_contratacao"],
                column_config={
                    "Forma de Contratação": st.column_config.TextColumn(disabled=True),
                    "Selecionado": st.column_config.CheckboxColumn("Selecionar")
                },
                hide_index=True,
                key="formas_editor"
            )
            st.session_state["df_formas_contratacao"] = df_editor.copy()
            selected_forms = df_editor.loc[df_editor["Selecionado"], "Forma de Contratação"].tolist()
            if st.form_submit_button("Salvar Formas Selecionadas"):
                st.success("Seleção registrada com sucesso!")
        st.divider()
        if "Contrato Caixa" in selected_forms:
            with st.expander("📌 Contrato Caixa", expanded=False):
                st.session_state["observacoes_caixa"] = st.text_area(
                    "Observações",
                    value=st.session_state.get("observacoes_caixa", ""),
                    help="Inclua aqui quaisquer observações relativas ao contrato CAIXA."
                )
        if "Contrato ICMBio" in selected_forms:
            with st.expander("📌 Contrato ICMBio", expanded=False):
                contratos_disponiveis = ["Contrato ICMBio 1", "Contrato ICMBio 2"]
                st.session_state["contrato_icmbio_escolhido"] = st.selectbox(
                    "Quais contratos do ICMBio possuem os insumos e serviços previstos?",
                    options=contratos_disponiveis,
                    index=contratos_disponiveis.index(
                        st.session_state.get("contrato_icmbio_escolhido", contratos_disponiveis[0])
                    ) if "contrato_icmbio_escolhido" in st.session_state else 0
                )
                st.session_state["coord_geral_gestora"] = st.radio(
                    "A coordenação geral é gestora de algum desses contratos?",
                    options=["Sim", "Não"],
                    index=["Sim", "Não"].index(
                        st.session_state.get("coord_geral_gestora", "Não")
                    ) if "coord_geral_gestora" in st.session_state else 0
                )
                st.session_state["justificativa_icmbio"] = st.text_area(
                    "Qual a justificativa para utilização desses contratos em detrimento dos contratos realizados pela CAIXA?",
                    value=st.session_state.get("justificativa_icmbio", "")
                )
        if "Fundação de Apoio credenciada pelo ICMBio" in selected_forms:
            with st.expander("📌 Fundação de Apoio credenciada pelo ICMBio", expanded=False):
                st.session_state["existe_projeto_cppar"] = st.radio(
                    "Já existe projeto aprovado pela CPPar relacionado ao tema proposto?",
                    options=["Sim", "Não"],
                    index=["Sim", "Não"].index(
                        st.session_state.get("existe_projeto_cppar", "Não")
                    ) if "existe_projeto_cppar" in st.session_state else 0
                )
                if st.session_state["existe_projeto_cppar"] == "Sim":
                    st.session_state["sei_projeto"] = st.text_input(
                        "Informe o número SEI correspondente ao projeto",
                        value=st.session_state.get("sei_projeto", "")
                    )
                    st.session_state["sei_ata"] = st.text_input(
                        "Número SEI da Ata/Decisão de aprovação do projeto na CPPar",
                        value=st.session_state.get("sei_ata", "")
                    )
                st.session_state["in_concorda"] = st.radio(
                    "A iniciativa estruturante está de acordo com as IN nº 18/2018 e nº 12/2024?",
                    options=["Sim", "Não"],
                    index=["Sim", "Não"].index(
                        st.session_state.get("in_concorda", "Não")
                    ) if "in_concorda" in st.session_state else 0
                )
                st.session_state["justificativa_fundacao"] = st.text_area(
                    "Justificativa para uso de Fundação de Apoio:",
                    value=st.session_state.get("justificativa_fundacao", "")
                )
        if "Fundação de Amparo à pesquisa" in selected_forms:
            with st.expander("📌 Fundação de Amparo à Pesquisa", expanded=False):
                st.session_state["in_amparo"] = st.radio(
                    "A iniciativa estruturante está de acordo com as normas que amparam a fundação de amparo?",
                    options=["Sim", "Não"],
                    index=["Sim", "Não"].index(
                        st.session_state.get("in_amparo", "Não")
                    ) if "in_amparo" in st.session_state else 0
                )
                fundacoes_disponiveis = ["FAPESP", "FAPERJ", "FAPEMIG", "Outra..."]
                selecao_anterior = st.session_state.get("f_aparceria", [])
                st.session_state["f_aparceria"] = st.multiselect(
                    "Quais Fundações de Amparo se pretende realizar a parceria?",
                    options=fundacoes_disponiveis,
                    default=selecao_anterior,
                    help="Selecione uma ou mais fundações, caso existam."
                )
                st.session_state["parcerias_info"] = st.text_area(
                    "Há parcerias em andamento ou contato prévio com a fundação? Descreva.",
                    value=st.session_state.get("parcerias_info", "")
                )
        formas_df_dict = st.session_state["df_formas_contratacao"].to_dict(orient="records")
        contratacao_extra = {
            "observacoes_caixa": st.session_state.get("observacoes_caixa", ""),
            "contrato_icmbio_escolhido": st.session_state.get("contrato_icmbio_escolhido", ""),
            "coord_geral_gestora": st.session_state.get("coord_geral_gestora", ""),
            "justificativa_icmbio": st.session_state.get("justificativa_icmbio", ""),
            "existe_projeto_cppar": st.session_state.get("existe_projeto_cppar", ""),
            "sei_projeto": st.session_state.get("sei_projeto", ""),
            "sei_ata": st.session_state.get("sei_ata", ""),
            "in_concorda": st.session_state.get("in_concorda", ""),
            "justificativa_fundacao": st.session_state.get("justificativa_fundacao", ""),
            "in_amparo": st.session_state.get("in_amparo", ""),
            "f_aparceria": st.session_state.get("f_aparceria", []),
            "parcerias_info": st.session_state.get("parcerias_info", "")
        }
        formas_dict = {
            "tabela_formas": formas_df_dict,
            "detalhes": contratacao_extra
        }
        st.session_state["formas_contratacao_detalhes"] = formas_dict
    if st.form_submit_button("Salvar Alterações"):
        if not st.session_state["objetivo_geral"]:
            st.error("O campo 'Objetivo Geral' não pode estar vazio.")
        elif not st.session_state["objetivos_especificos"]:
            st.error("A lista de 'Objetivos Específicos' não pode estar vazia.")
        elif not st.session_state["introducao"]:
            st.error("O campo 'Introdução' não pode estar vazio.")
        elif not st.session_state["justificativa"]:
            st.error("O campo 'Justificativa' não pode estar vazio.")
        elif not st.session_state["metodologia"]:
            st.error("O campo 'Metodologia' não pode estar vazio.")
        else:
            st.session_state["objetivo_geral"] = st.session_state["objetivo_geral"]
            st.session_state["introducao"] = st.session_state["introducao"]
            st.session_state["justificativa"] = st.session_state["justificativa"]
            st.session_state["metodologia"] = st.session_state["metodologia"]
            st.session_state["demais_informacoes"] = {
                "diretoria": diretoria_novo,
                "coordenacao_geral": coord_geral_novo,
                "coordenacao": coord_novo,
                "demandante": demandante_novo
            }
            st.session_state["eixos_tematicos"] = st.session_state["eixos_tematicos"]
            if "insumos" not in st.session_state:
                st.session_state["insumos"] = {}
            else:
                st.session_state["insumos"] = st.session_state["insumos"]
            st.session_state["df_uc_editado"] = st.session_state["df_uc_editado"]
            st.success("Alterações salvas com sucesso!")
st.divider()
col1, col2, col3 = st.columns(3)
with col2:
    if st.button("📝 Finalizar Cadastro", key="btn_salvar_geral"):
        salvar_dados_iniciativa(
            id_iniciativa=nova_iniciativa,
            usuario=cpf_usuario,
            objetivo_geral=st.session_state["objetivo_geral"],
            objetivos_especificos=st.session_state["objetivos_especificos"],
            eixos_tematicos=st.session_state["eixos_tematicos"],
            introducao=st.session_state["introducao"],
            justificativa=st.session_state["justificativa"],
            metodologia=st.session_state["metodologia"],
            demais_informacoes=st.session_state["demais_informacoes"]
        )
        st.success("✅ Cadastro atualizado com sucesso!")
st.divider()
st.caption("ℹ️ Informações Originais do Resumo Executivo de Iniciativas", help="ref.: documentos SEI")
def tratar_valor(valor):
    if pd.isna(valor) or valor is None or str(valor).strip().lower() == "null":
        return "(sem informação)"
    return str(valor).strip()
resumos = carregar_resumo_iniciativa(setor)
if resumos is not None:
    for _, r in resumos.iterrows():
        nome_inic = tratar_valor(r.get("iniciativa", "Iniciativa Desconhecida"))
        with st.expander(f"📖 {nome_inic}", expanded=False):
            st.divider()
            st.write(f"**🎯 Objetivo Geral:** {tratar_valor(r.get('objetivo_geral'))}")
            st.divider()
            st.write(f"**🏢 Diretoria:** {tratar_valor(r.get('diretoria'))}")
            st.write(f"**📌 Coordenação Geral:** {tratar_valor(r.get('coordenação_geral'))}")
            st.write(f"**🗂 Coordenação:** {tratar_valor(r.get('coordenação'))}")
            st.write(f"**📍 Demandante:** {tratar_valor(r.get('demandante'))}")
            st.divider()
            st.write(f"**📝 Introdução:** {tratar_valor(r.get('introdução'))}")
            st.divider()
            st.write(f"**💡 Justificativa:** {tratar_valor(r.get('justificativa'))}")
            st.divider()
            st.write(f"**🏞 Unidades de Conservação / Benefícios:** {tratar_valor(r.get('unidades_de_conservação_beneficiadas'))}")
            st.divider()
            st.write(f"**🔬 Metodologia:** {tratar_valor(r.get('metodologia'))}")
st.divider()

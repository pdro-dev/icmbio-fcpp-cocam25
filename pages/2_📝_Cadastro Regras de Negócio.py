###############################################################################
#                          IMPORTS E CONFIGURAÇÕES
###############################################################################

import streamlit as st
import sqlite3
import json
import pandas as pd
import time as time

import streamlit as st
import sqlite3
import json
import pandas as pd
import time as time

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

# Caminho do banco de dados
DB_PATH = "database/app_data.db"


# -----------------------------------------------------------------------------
#                          FUNÇÕES AUXILIARES / CACHED
# -----------------------------------------------------------------------------
@st.cache_data
def get_iniciativas_usuario(perfil: str, setor: str) -> pd.DataFrame:
    """
    Retorna as iniciativas disponíveis para o usuário,
    filtradas por perfil e setor, se não for 'admin'.
    """
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT id_iniciativa, nome_iniciativa FROM td_iniciativas"
    if perfil != "admin":
        query += """
            WHERE id_iniciativa IN (
               SELECT id_iniciativa 
               FROM tf_cadastros_iniciativas 
               WHERE id_demandante = (
                  SELECT id_demandante FROM td_demandantes WHERE nome_demandante = ?
               )
            )
        """
        iniciativas = pd.read_sql_query(query, conn, params=[setor])
    else:
        iniciativas = pd.read_sql_query(query, conn)
    conn.close()
    return iniciativas


@st.cache_data
def carregar_dados_iniciativa(id_iniciativa: int) -> dict | None:
    """
    Carrega a última linha de tf_cadastro_regras_negocio para a iniciativa dada.
    Retorna um dicionário com as colunas esperadas ou None se não existir.
    """
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT *
        FROM tf_cadastro_regras_negocio
        WHERE id_iniciativa = ?
        ORDER BY data_hora DESC
        LIMIT 1
    """
    df = pd.read_sql_query(query, conn, params=[id_iniciativa])
    conn.close()

    if df.empty:
        return None

    row = df.iloc[0]

    # Eixos temáticos salvos em JSON
    try:
        eixos_tematicos = json.loads(row["eixos_tematicos"]) if row["eixos_tematicos"] else []
    except:
        eixos_tematicos = []

    # Demais informações salvas em JSON
    info_json = row.get("demais_informacoes", "") or ""
    try:
        info_dict = json.loads(info_json) if info_json else {}
    except:
        info_dict = {}

    return {
        "objetivo_geral":      row["objetivo_geral"],
        "objetivos_especificso": row["objetivos_especificos"],
        "eixos_tematicos":     row["eixos_tematicos"],
        "introducao":          row.get("introducao", ""),
        "justificativa":       row.get("justificativa", ""),
        "metodologia":         row.get("metodologia", ""),
        "demais_informacoes":  info_dict
    }


@st.cache_data
def carregar_resumo_iniciativa(setor: str) -> pd.DataFrame | None:
    """
    Carrega o resumo a partir de td_dados_resumos_sei, filtrando por 'demandante' = setor.
    Retorna um DataFrame ou None se vazio.
    """
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM td_dados_resumos_sei WHERE demandante = ?"
    df = pd.read_sql_query(query, conn, params=[setor])
    conn.close()
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

    - objetivos_especificos: lista de strings
    - eixos_tematicos: lista de dicts
    - demais_informacoes: dict de informações complementares

    Também atualiza as colunas "acoes_manejo" e "insumos" com base nos eixos.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Limite de 3 históricos por iniciativa
    cursor.execute("""
        SELECT COUNT(*)
        FROM tf_cadastro_regras_negocio
        WHERE id_iniciativa = ?
    """, (id_iniciativa,))
    total_reg = cursor.fetchone()[0]
    if total_reg >= 3:
        cursor.execute("""
            DELETE FROM tf_cadastro_regras_negocio
            WHERE id IN (
                SELECT id
                FROM tf_cadastro_regras_negocio
                WHERE id_iniciativa = ?
                ORDER BY data_hora ASC
                LIMIT 1
            )
        """, (id_iniciativa,))

    # Converte listas/dicts para JSON
    objetivos_json = json.dumps(objetivos_especificos or [])
    eixos_json     = json.dumps(eixos_tematicos or [])

    # Extrai lista de ações e insumos a partir de eixos
    acoes_set   = set()
    insumos_set = set()
    for eixo in eixos_tematicos:
        for ac_id, ac_data in eixo.get("acoes_manejo", {}).items():
            acoes_set.add(ac_id)
            for ins_id in ac_data.get("insumos", []):
                insumos_set.add(ins_id)

    acoes_json   = json.dumps(list(acoes_set))
    insumos_json = json.dumps(list(insumos_set))

    # Regra consolidada
    final_rule = {
        "objetivo_geral": objetivo_geral,
        "objetivos_especificos": objetivos_especificos,
        "eixos_tematicos": eixos_tematicos,
        "acoes": list(acoes_set),
        "insumos": list(insumos_set)
    }
    regra_json = json.dumps(final_rule)

    # Converte o dicionário 'demais_informacoes' em JSON
    demais_info_json = json.dumps(demais_informacoes) if demais_informacoes else "{}"

    # 1) Distribuição UC (df_uc_editado)
    if "df_uc_editado" in st.session_state and not st.session_state["df_uc_editado"].empty:
        distribuicao_ucs_json = st.session_state["df_uc_editado"].to_json(orient="records", force_ascii=False)
    else:
        distribuicao_ucs_json = "[]"

    # 2) Formas de Contratação (formas_contratacao_detalhes)
    if "formas_contratacao_detalhes" in st.session_state:
        formas_contratacao_json = json.dumps(st.session_state["formas_contratacao_detalhes"], ensure_ascii=False)
    else:
        formas_contratacao_json = "{}"

    # Insere no banco
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        formas_contratacao_json   # Alterado aqui
    ))

    conn.commit()
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
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT {id_col}, {name_col} FROM {table_name}"
    params = ()
    if filter_col and filter_val is not None:
        query += f" WHERE {filter_col} = ?"
        params = (str(filter_val),)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    st.sidebar.write("### Informações da Iniciativa")

    # 1) tf_cadastros_iniciativas + demandante
    query_inic = """
    SELECT ci.id_demandante,
           COUNT(DISTINCT ci.cnuc) AS num_unidades,
           d.nome_demandante
    FROM tf_cadastros_iniciativas ci
    JOIN td_demandantes d ON ci.id_demandante = d.id_demandante
    WHERE ci.id_iniciativa = ?
    GROUP BY ci.id_demandante
    """
    row_inic = cursor.execute(query_inic, (id_iniciativa,)).fetchone()
    if row_inic:
        _, num_unidades, nome_demandante = row_inic
        st.sidebar.write(f"**Demandante:** {nome_demandante}")
        st.sidebar.write(f"**Número de Unidades:** {num_unidades}")
    else:
        st.sidebar.info("Iniciativa não encontrada em tf_cadastros_iniciativas.")

    # 2) td_dados_resumos_sei
    row_resumo = cursor.execute("""
        SELECT diretoria, coordenação_geral, coordenação
        FROM td_dados_resumos_sei
        WHERE id_resumo = ?
        LIMIT 1
    """, (id_iniciativa,)).fetchone()
    if row_resumo:
        dir_, coord_geral, coord_ = row_resumo
        st.sidebar.write(f"**Diretoria:** {dir_ if dir_ else 'sem informação'}")
        st.sidebar.write(f"**Coord. Geral:** {coord_geral if coord_geral else 'sem informação'}")
        st.sidebar.write(f"**Coordenação:** {coord_ if coord_ else 'sem informação'}")
    else:
        st.sidebar.info("Sem resumo SEI cadastrado para esta iniciativa.")

    # 3) Eixos existentes (último registro)
    row_eixos = cursor.execute("""
        SELECT eixos_tematicos
        FROM tf_cadastro_regras_negocio
        WHERE id_iniciativa = ?
        ORDER BY data_hora DESC
        LIMIT 1
    """, (id_iniciativa,)).fetchone()

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

# 1) Seleciona Iniciativa do usuário
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

# 2) Carregamento inicial da iniciativa se mudou
if "carregou_iniciativa" not in st.session_state or st.session_state["carregou_iniciativa"] != nova_iniciativa:
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # 1️⃣ BUSCA DADOS NA TABELA PRINCIPAL PRIMEIRO (tf_cadastro_regras_negocio)
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT objetivo_geral, objetivos_especificos, eixos_tematicos,
               introducao, justificativa, metodologia, demais_informacoes
        FROM tf_cadastro_regras_negocio
        WHERE id_iniciativa = ?
        ORDER BY data_hora DESC
        LIMIT 1
    """
    dados_iniciativa = pd.read_sql_query(query, conn, params=[nova_iniciativa])
    conn.close()

    if not dados_iniciativa.empty:
        row = dados_iniciativa.iloc[0]

        # Objetivos Específicos: Sempre carrega do banco primeiro
        try:
            objetivos_especificos = json.loads(row["objetivos_especificos"]) if row["objetivos_especificos"] else []
        except:
            objetivos_especificos = []

        st.session_state["objetivo_geral"] = row["objetivo_geral"]
        st.session_state["objetivos_especificos"] = objetivos_especificos

        # Eixos Temáticos
        try:
            st.session_state["eixos_tematicos"] = json.loads(row["eixos_tematicos"]) if row["eixos_tematicos"] else []
        except:
            st.session_state["eixos_tematicos"] = []

        # Textos
        st.session_state["introducao"] = row["introducao"]
        st.session_state["justificativa"] = row["justificativa"]
        st.session_state["metodologia"] = row["metodologia"]

        # Demais informações
        try:
            st.session_state["demais_informacoes"] = json.loads(row["demais_informacoes"]) if row["demais_informacoes"] else {}
        except:
            st.session_state["demais_informacoes"] = {}

    else:
        # Se não houver dados em `tf_cadastro_regras_negocio`, inicia com valores vazios
        st.session_state["objetivo_geral"] = ""
        st.session_state["objetivos_especificos"] = []
        st.session_state["eixos_tematicos"] = []
        st.session_state["introducao"] = ""
        st.session_state["justificativa"] = ""
        st.session_state["metodologia"] = ""
        st.session_state["demais_informacoes"] = {}

        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        # 2️⃣ FALLBACK: BUSCA DADOS NO RESUMO (td_dados_resumos_sei) APENAS SE O PRINCIPAL ESTIVER VAZIO
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        if not st.session_state["objetivo_geral"]:
            conn = sqlite3.connect(DB_PATH)
            row_fallback = conn.execute("""
                SELECT objetivo_geral FROM td_dados_resumos_sei
                WHERE id_resumo = ? LIMIT 1
            """, (nova_iniciativa,)).fetchone()
            conn.close()

            if row_fallback:
                obj_geral_sei = row_fallback[0] or ""
                if obj_geral_sei:
                    st.session_state["objetivo_geral"] = obj_geral_sei

        if not st.session_state["introducao"] or not st.session_state["justificativa"] or not st.session_state["metodologia"]:
            conn = sqlite3.connect(DB_PATH)
            row_resumo_2 = conn.execute("""
                SELECT introdução, justificativa, metodologia
                FROM td_dados_resumos_sei
                WHERE id_resumo = ?
                LIMIT 1
            """, (nova_iniciativa,)).fetchone()
            conn.close()

            if row_resumo_2:
                intro_sei, justif_sei, metod_sei = row_resumo_2

                if not st.session_state["introducao"] and intro_sei:
                    st.session_state["introducao"] = intro_sei
                if not st.session_state["justificativa"] and justif_sei:
                    st.session_state["justificativa"] = justif_sei
                if not st.session_state["metodologia"] and metod_sei:
                    st.session_state["metodologia"] = metod_sei

    # 3️⃣ Finaliza o carregamento
    st.session_state["carregou_iniciativa"] = nova_iniciativa



# Exibe na barra lateral (checkbox)
if st.sidebar.checkbox("Exibir informações da iniciativa", value=True):
    exibir_info_lateral(nova_iniciativa)

st.divider()

st.write(f"**Iniciativa Selecionada:** {iniciativas.set_index('id_iniciativa').loc[nova_iniciativa, 'nome_iniciativa']}")



# ---------------------------------------------------------
#  TABS: Introdução / Objetivos / Justificativa / Metodologia
#        e a aba para Demais Informações
# ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 1) OBJETIVOS
    # (aba separada, pois tem seu próprio form para atualizar
    #  objetivos específicos)
    # ---------------------------------------------------------
    with tab_obj:
        st.subheader("Objetivo Geral")
        st.session_state["objetivo_geral"] = st.text_area(
            "Descreva o Objetivo Geral:",
            value=st.session_state["objetivo_geral"],
            height=140
        )

        st.subheader("Objetivos Específicos")

        # Se não existir, inicializa a lista de objetivos em session_state
        if "objetivos_especificos" not in st.session_state:
            st.session_state["objetivos_especificos"] = []

        # 1) Campo e botão para adicionar NOVO objetivo (acima da lista)
        def adicionar_objetivo_callback():
            texto_novo = st.session_state.txt_novo_objetivo.strip()
            if texto_novo:
                st.session_state["objetivos_especificos"].append(texto_novo)
                st.session_state.txt_novo_objetivo = ""  # limpa a caixa após adicionar
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

        # 2) Agora exibimos a lista (simulando uma tabela) com Editar/Remover
        st.write("*Objetivos adicionados:*")

        # Cabeçalho tipo tabela
        col1, col2, col3 = st.columns([1, 8, 3])
        col1.write("**#**")
        col2.write("**Objetivo**")
        col3.write("*Edição e Exclusão*")

        # Loop para cada objetivo adicionado
        for i, objetivo in enumerate(st.session_state["objetivos_especificos"]):
            # Criamos uma nova linha em colunas
            c1, c2, c3 = st.columns([1, 6, 3])
            c1.write(f"{i + 1}")
            c2.write(objetivo)  # exibe o texto do objetivo

            # Na terceira coluna, colocamos botões: Editar (via popover) e Remover
            with c3:
                col_edit, col_remove = st.columns([1, 1])
                with col_edit:
                    # 2.1) Botão/Popover de Edição
                    with st.popover(label=f"✏️"):
                        st.subheader(f"Editar Objetivo {i+1}")
                        novo_texto = st.text_area("Texto do objetivo:", objetivo, key=f"edit_obj_{i}")
                        if st.button("Salvar Edição", key=f"btn_save_edit_{i}"):
                            st.session_state["objetivos_especificos"][i] = novo_texto
                            st.rerun()
                with col_remove:
                    # 2.2) Botão de Remoção
                    if st.button("🗑️", key=f"btn_remove_{i}"):
                        del st.session_state["objetivos_especificos"][i]
                        st.rerun()



    # ---------------------------------------------------------
    # 2) INTRODUÇÃO, JUSTIFICATIVA, METODOLOGIA e
    #    DEMAIS INFORMAÇÕES
    # ---------------------------------------------------------
    # Aba de Introdução
    with tab_intro:
        st.subheader("Introdução")
        st.session_state["introducao"] = st.text_area(
            "Texto de Introdução:",
            value=st.session_state["introducao"],
            height=300
        )

    # Aba de Justificativa
    with tab_justif:
        st.subheader("Justificativa")
        st.session_state["justificativa"] = st.text_area(
            "Texto de Justificativa:",
            value=st.session_state["justificativa"],
            height=300
        )

    # Aba de Metodologia
    with tab_metod:
        st.subheader("Metodologia")
        st.session_state["metodologia"] = st.text_area(
            "Texto de Metodologia:",
            value=st.session_state["metodologia"],
            height=300
        )

    # Aba de Demais Informações
    with tab_demandante:
        st.subheader("Demais Informações")
        st.caption("Edição de Informações do Setor Demandante.")

        # Verifica se os dados existem no session_state, senão busca no banco
        if not st.session_state.get("demais_informacoes"):
            conn = sqlite3.connect(DB_PATH)
            query = """
                SELECT diretoria, coordenação_geral, coordenação, demandante
                FROM td_dados_resumos_sei
                WHERE id_resumo = ?
                LIMIT 1
            """
            row = conn.execute(query, (nova_iniciativa,)).fetchone()
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

        # Garante que "demais_informacoes" é um dicionário válido
        if not isinstance(st.session_state["demais_informacoes"], dict):
            try:
                st.session_state["demais_informacoes"] = json.loads(st.session_state["demais_informacoes"])
            except:
                st.session_state["demais_informacoes"] = {}

        # Lê os valores do session_state (garantindo que não sejam None)
        di = st.session_state["demais_informacoes"].get("diretoria", "")
        cg = st.session_state["demais_informacoes"].get("coordenacao_geral", "")
        co = st.session_state["demais_informacoes"].get("coordenacao", "")
        dm = st.session_state["demais_informacoes"].get("demandante", "")

        st.caption("Preencha os campos abaixo conforme necessário:")
        diretoria_novo    = st.text_input("Diretoria:", value=di)
        coord_geral_novo  = st.text_input("Coordenação Geral:", value=cg)
        coord_novo        = st.text_input("Coordenação:", value=co)
        demandante_novo   = st.text_input("Demandante (Sigla):", value=dm, disabled=True)

        # # Atualiza session_state quando os valores forem alterados
        # if st.button("Salvar Informações do Demandante"):
        #     st.session_state["demais_informacoes"] = {
        #         "diretoria": diretoria_novo,
        #         "coordenacao_geral": coord_geral_novo,
        #         "coordenacao": coord_novo,
        #         "demandante": demandante_novo
        #     }
        #     st.success("Informações do demandante atualizadas com sucesso!")



    with tab_eixos:
        # -------------------------------------------
        # 4) EIXOS TEMÁTICOS - Seleção de Ações
        # -------------------------------------------
        st.subheader("Eixos Temáticos")

        eixos_opcoes = get_options_from_table("td_samge_processos", "id_p", "nome")

        # Novo eixo para adicionar
        novo_eixo_id = st.selectbox(
            "Escolha um Eixo (Processo SAMGe) para adicionar:",
            options=[None] + sorted(eixos_opcoes.keys(), key=lambda x: eixos_opcoes[x]),
            format_func=lambda x: eixos_opcoes.get(x, "Selecione..."),
            key="sel_novo_eixo"
        )

       # Adicionar um novo eixo
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

                    # ✅ Força atualização dos insumos ao adicionar novo eixo
                    st.session_state["insumos"] = {}  # Reseta os insumos para recalcular

                    st.rerun()
                else:
                    st.info("Este eixo já está na lista.")



        # Exibir expanders para cada eixo adicionado
        for i, eixo in enumerate(st.session_state["eixos_tematicos"]):
            with st.expander(f"📌 {eixo['nome_eixo']}", expanded=False):
                # Carregar ações disponíveis
                acoes_dict = get_options_from_table(
                    "td_samge_acoes_manejo", "id_ac", "nome",
                    filter_col="processo_id", filter_val=eixo["id_eixo"]
                )

                # Criar DataFrame para edição
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
                        # Atualiza as ações selecionadas no eixo
                        selecionadas = edited_acoes.loc[edited_acoes["Selecionado"], "ID"].tolist()
                        eixo["acoes_manejo"] = {ac_id: {"insumos": []} for ac_id in selecionadas}
                        st.session_state["eixos_tematicos"][i] = eixo
                        st.success("Ações atualizadas!")

                # Botão para excluir eixo
                if st.button("🗑️ Excluir Eixo", key=f"btn_del_{i}"):
                    del st.session_state["eixos_tematicos"][i]
                    st.rerun()

    # -------------------------------------------
    # 5) INSUMOS - Seleção de Insumos por Ação
    # -------------------------------------------
    with tab_insumos:
        st.subheader("Insumos por Ação")

        # Conectar ao banco para carregar a tabela de insumos
        conn = sqlite3.connect(DB_PATH)
        df_insumos_all = pd.read_sql_query(
            "SELECT id, elemento_despesa, especificacao_padrao, descricao_insumo FROM td_insumos",
            conn
        )
        conn.close()

        # Inicializar estado para armazenar insumos selecionados, se ainda não existir
        if "insumos_selecionados" not in st.session_state:
            st.session_state["insumos_selecionados"] = {}

        for i, eixo in enumerate(st.session_state["eixos_tematicos"]):
            with st.expander(f"📌 {eixo['nome_eixo']}", expanded=False):
                # Percorremos as ações daquele eixo
                for ac_id, ac_data in eixo["acoes_manejo"].items():
                    st.markdown(
                        f"### Ação: {get_options_from_table('td_samge_acoes_manejo', 'id_ac', 'nome').get(ac_id, 'Ação Desconhecida')}"
                    )

                    # Inicializa a lista de insumos selecionados para essa ação, se ainda não existir
                    if ac_id not in st.session_state["insumos_selecionados"]:
                        st.session_state["insumos_selecionados"][ac_id] = set(ac_data.get("insumos", []))

                    # Criar colunas para os filtros
                    col_filtro_elemento, col_filtro_espec = st.columns([5, 5])

                    # Filtro de Elemento de Despesa
                    elementos_unicos = ["Todos"] + sorted(df_insumos_all["elemento_despesa"].dropna().unique())
                    with col_filtro_elemento:
                        elemento_selecionado = st.selectbox(
                            "Selecione o Elemento de Despesa",
                            elementos_unicos,
                            key=f"elemento_{i}_{ac_id}"
                        )

                    # Filtrando os insumos conforme o elemento de despesa selecionado
                    df_filtrado = (
                        df_insumos_all
                        if elemento_selecionado == "Todos"
                        else df_insumos_all[df_insumos_all["elemento_despesa"] == elemento_selecionado]
                    )

                    # Filtro de Especificação Padrão
                    especificacoes_unicas = ["Todos"] + sorted(df_filtrado["especificacao_padrao"].dropna().unique())
                    with col_filtro_espec:
                        especificacao_selecionada = st.selectbox(
                            "Selecione a Especificação Padrão",
                            especificacoes_unicas,
                            key=f"especificacao_{i}_{ac_id}"
                        )

                    # Aplicando o segundo filtro caso o usuário selecione uma especificação
                    if especificacao_selecionada != "Todos":
                        df_filtrado = df_filtrado[df_filtrado["especificacao_padrao"] == especificacao_selecionada]

                    # Renomeando colunas para melhor compatibilidade com data_editor
                    df_combo = df_filtrado.rename(
                        columns={
                            "id": "ID",
                            "descricao_insumo": "Insumo"
                        }
                    )

                    # Recupera o "master" de insumos já selecionados do estado para essa ação
                    sel_ids = st.session_state["insumos_selecionados"][ac_id]

                    # Marcamos a coluna "Selecionado" com True/False se estiver no "master"
                    df_combo["Selecionado"] = df_combo["ID"].apply(lambda x: x in sel_ids)

                    # Exibir Data Editor dentro de um formulário
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

                        # Botão para salvar as seleções sem perder insumos anteriores
                        # O clique desse botão só controla o subset atual (df_filtrado)
                        if st.form_submit_button("Salvar Insumos"):
                            # "edited_ins" contém apenas o subset filtrado
                            # Precisamos mesclar com o "master" (sel_ids)

                            # 1) Obtemos o conjunto marcado agora:
                            selecionados_agora = set(edited_ins.loc[edited_ins["Selecionado"], "ID"])

                            # 2) Vamos atualizar o master:
                            #    - adiciona os que foram marcados
                            #    - remove os que foram desmarcados e que estão presentes no df_filtrado
                            # (itens fora do df_filtrado ficam inalterados)
                            for item_id in df_combo["ID"]:
                                if item_id in selecionados_agora:
                                    sel_ids.add(item_id)     # marcado => adiciona ao master
                                else:
                                    # se está no master e está no subset filtrado, remove
                                    if item_id in sel_ids:
                                        sel_ids.remove(item_id)

                            # salva de volta no session_state
                            st.session_state["insumos_selecionados"][ac_id] = sel_ids
                            # atualiza o dicionário da ação
                            ac_data["insumos"] = list(sel_ids)

                            st.success("Seleção atualizada (sem perder itens já escolhidos em outros filtros)!")

                    # # Botão para limpar todas as seleções de insumos dessa ação
                    # if st.button("Limpar Lista de Insumos", key=f"limpar_{i}_{ac_id}"):
                    #     st.session_state["insumos_selecionados"][ac_id] = set()
                    #     ac_data["insumos"] = []
                    #     st.success("Todos os insumos foram removidos para esta ação!")

                    st.write("---")




    # -------------------------------------------
    # 6) UNIDADES DE CONSERVAÇÃO - Distribuição de Recursos
    # -------------------------------------------

    with tab_uc:
        st.subheader("Distribuição de Recursos por Eixo")

        conn = sqlite3.connect(DB_PATH)
        row_dist = conn.execute("""
            SELECT distribuicao_ucs
            FROM tf_cadastro_regras_negocio
            WHERE id_iniciativa = ?
            ORDER BY data_hora DESC
            LIMIT 1
        """, (nova_iniciativa,)).fetchone()

        query_fallback = """
            SELECT 
                "Unidade de Conservação" AS Unidade,
                "AÇÃO DE APLICAÇÃO"      AS Acao,
                "VALOR TOTAL ALOCADO"    AS "Valor Alocado"
            FROM tf_cadastros_iniciativas
            WHERE id_iniciativa = ?
            AND "VALOR TOTAL ALOCADO" > 0
        """
        df_unidades_raw = pd.read_sql_query(query_fallback, conn, params=[nova_iniciativa])
        conn.close()

        df_db = pd.DataFrame()
        if row_dist and row_dist[0]:
            try:
                dist_list = json.loads(row_dist[0])
                df_db = pd.DataFrame(dist_list)
            except:
                df_db = pd.DataFrame()

        if "ultima_iniciativa" not in st.session_state or st.session_state["ultima_iniciativa"] != nova_iniciativa:
            st.session_state["ultima_iniciativa"] = nova_iniciativa
            if not df_db.empty:
                st.session_state["df_uc_editado"] = df_db.copy()
            else:
                st.session_state["df_uc_editado"] = df_unidades_raw.copy()

        if df_unidades_raw.empty and df_db.empty:
            st.warning("Nenhuma unidade de conservação encontrada para esta iniciativa.")
            st.stop()

        def recalcular_saldo():
            data_dict = st.session_state["editor_uc"]
            df_master = st.session_state["df_uc_editado"].copy()

            edited_rows = data_dict.get("edited_rows", {})
            for row_idx_str, changed_cols in edited_rows.items():
                row_idx = int(row_idx_str)
                for col_name, new_value in changed_cols.items():
                    df_master.loc[row_idx, col_name] = new_value

            df_master["Valor Alocado"] = pd.to_numeric(df_master.get("Valor Alocado", 0), errors="coerce").fillna(0)
            colunas_eixos = [eixo["nome_eixo"] for eixo in st.session_state["eixos_tematicos"]]

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

        # 🚀 **AGREGAR OS DADOS POR UNIDADE + AÇÃO**
        df_editavel = df_editavel.groupby(["Unidade", "Acao"], as_index=False).sum()

        colunas_ordenadas = colunas_fixas + ["Distribuir"] + colunas_eixos
        df_editavel = df_editavel[colunas_ordenadas]

        # Exibir data_editor
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


        # # Exemplo: Botão p/ persistir no banco (ou pode ser salvo lá no "Salvar Alterações")
        # if st.button("Salvar Distribuição"):
        #     # Basta avisar. O 'salvar_dados_iniciativa' usará "st.session_state['df_uc_editado']"
        #     st.success("Distribuição de recursos atualizada!")




    # -------------------------------------------
    # 7) FORMAS DE CONTRATAÇÃO
    # -------------------------------------------

    with tab_forma_contratacao:
        st.title("Formas de Contratação")

        # ----------------------------------------------------------------
        # 1) Carrega, se ainda não carregamos para esta iniciativa
        #    (Assim, a cada troca de iniciativa, recarrega do banco)
        # ----------------------------------------------------------------
        if ("formas_carregou_iniciativa" not in st.session_state 
            or st.session_state["formas_carregou_iniciativa"] != nova_iniciativa):
            
            st.session_state["formas_carregou_iniciativa"] = nova_iniciativa

            # 1.1) Consulta a coluna 'formas_contratacao' no banco
            conn = sqlite3.connect(DB_PATH)
            row_formas = conn.execute("""
                SELECT formas_contratacao
                FROM tf_cadastro_regras_negocio
                WHERE id_iniciativa = ?
                ORDER BY data_hora DESC
                LIMIT 1
            """, (nova_iniciativa,)).fetchone()
            conn.close()

            # 1.2) Se existir JSON no banco, parseamos
            if row_formas and row_formas[0]:
                try:
                    stored_formas = json.loads(row_formas[0])
                except:
                    stored_formas = {}
            else:
                stored_formas = {}

            # 1.3) Monta DF default (4 formas) caso não tenha nada
            df_default = pd.DataFrame({
                "Forma de Contratação": [
                    "Contrato Caixa",
                    "Contrato ICMBio",
                    "Fundação de Apoio credenciada pelo ICMBio",
                    "Fundação de Amparo à pesquisa"
                ],
                "Selecionado": [False, False, False, False]
            })

            # 1.4) Se temos 'tabela_formas' no banco, converte em DF;
            #      caso contrário, use df_default
            tabela_formas_banco = stored_formas.get("tabela_formas", [])
            if tabela_formas_banco:
                st.session_state["df_formas_contratacao"] = pd.DataFrame(tabela_formas_banco)
            else:
                st.session_state["df_formas_contratacao"] = df_default.copy()

            # 1.5) Carrega “detalhes_por_forma” do banco e joga no session_state
            detalhes = stored_formas.get("detalhes_por_forma", {})
            # Exemplo: "Contrato Caixa" => {"Observações": "..."}
            if "Contrato Caixa" in detalhes:
                st.session_state["observacoes_caixa"] = detalhes["Contrato Caixa"].get("Observações", "")

            if "Contrato ICMBio" in detalhes:
                icmbio_data = detalhes["Contrato ICMBio"]
                st.session_state["contrato_icmbio_escolhido"] = icmbio_data.get("Contratos Escolhidos", [])
                st.session_state["coord_geral_gestora"]       = icmbio_data.get("Coordenação Geral Gestora", "Não")
                st.session_state["justificativa_icmbio"]       = icmbio_data.get("Justificativa Uso ICMBio", "")

            if "Fundação de Apoio credenciada pelo ICMBio" in detalhes:
                fa_data = detalhes["Fundação de Apoio credenciada pelo ICMBio"]
                st.session_state["existe_projeto_cppar"] = fa_data.get("Já existe projeto CPPar?", "Não")
                st.session_state["sei_projeto"]          = fa_data.get("SEI do Projeto", "")
                st.session_state["sei_ata"]              = fa_data.get("SEI da Ata/Decisão CPPar", "")
                st.session_state["in_concorda"]          = fa_data.get("Concorda com IN 18/2018 e 12/2024?", "Não")
                st.session_state["justificativa_fundacao"] = fa_data.get("Justificativa Fundação de Apoio", "")

            if "Fundação de Amparo à pesquisa" in detalhes:
                amparo_data = detalhes["Fundação de Amparo à pesquisa"]
                st.session_state["in_amparo"] = amparo_data.get("IN de Amparo?", "Não")
                # Fundações Selecionadas é string, ex.: "FAPESP, FAPEMIG"
                f_str = amparo_data.get("Fundações Selecionadas", "")
                if f_str:
                    st.session_state["f_aparceria"] = [x.strip() for x in f_str.split(",") if x.strip()]
                else:
                    st.session_state["f_aparceria"] = []
                st.session_state["parcerias_info"] = amparo_data.get("Informações de Parceria", "")

        # ----------------------------------------------------------------
        # 2) Agora exibir a UI, com os DF e expansions
        # ----------------------------------------------------------------
        with st.form("form_formas_contratacao"):
            # (a) Data Editor do DF
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

        # (b) Exibe os expanders conforme selected_forms
        if "Contrato Caixa" in selected_forms:
            with st.expander("📌 Contrato Caixa", expanded=False):
                st.session_state["observacoes_caixa"] = st.text_area(
                    "Observações",
                    value=st.session_state.get("observacoes_caixa", ""),
                    help="Inclua aqui quaisquer observações relativas ao contrato CAIXA."
                )

        if "Contrato ICMBio" in selected_forms:
            with st.expander("📌 Contrato ICMBio", expanded=False):
                contratos_disponiveis = ["Contrato ICMBio 1", "Contrato ICMBio 2", "Contrato ICMBio 3"]
                sel_anterior = st.session_state.get("contrato_icmbio_escolhido", [])
                st.session_state["contrato_icmbio_escolhido"] = st.multiselect(
                    "Quais contratos do ICMBio ...",
                    options=contratos_disponiveis,
                    default=sel_anterior
                )
                st.session_state["coord_geral_gestora"] = st.radio(
                    "A coordenação geral é gestora ...?",
                    options=["Sim", "Não"],
                    index=["Sim", "Não"].index(st.session_state.get("coord_geral_gestora", "Não"))
                )
                st.session_state["justificativa_icmbio"] = st.text_area(
                    "Justificativa ...",
                    value=st.session_state.get("justificativa_icmbio", "")
                )

        if "Fundação de Apoio credenciada pelo ICMBio" in selected_forms:
            with st.expander("📌 Fundação de Apoio credenciada pelo ICMBio", expanded=False):
                st.session_state["existe_projeto_cppar"] = st.radio(
                    "Já existe projeto aprovado pela CPPar ...?",
                    options=["Sim", "Não"],
                    index=["Sim", "Não"].index(st.session_state.get("existe_projeto_cppar", "Não"))
                )
                if st.session_state["existe_projeto_cppar"] == "Sim":
                    st.session_state["sei_projeto"] = st.text_input(
                        "Informe o número SEI ...",
                        value=st.session_state.get("sei_projeto", "")
                    )
                    st.session_state["sei_ata"] = st.text_input(
                        "Número SEI da Ata ...",
                        value=st.session_state.get("sei_ata", "")
                    )
                st.session_state["in_concorda"] = st.radio(
                    "A iniciativa está de acordo com IN 18/2018 ...?",
                    options=["Sim", "Não"],
                    index=["Sim", "Não"].index(st.session_state.get("in_concorda", "Não"))
                )
                st.session_state["justificativa_fundacao"] = st.text_area(
                    "Justificativa para uso ...",
                    value=st.session_state.get("justificativa_fundacao", "")
                )

        if "Fundação de Amparo à pesquisa" in selected_forms:
            with st.expander("📌 Fundação de Amparo à Pesquisa", expanded=False):
                st.session_state["in_amparo"] = st.radio(
                    "A iniciativa ...?",
                    options=["Sim", "Não"],
                    index=["Sim", "Não"].index(st.session_state.get("in_amparo", "Não"))
                )
                fundacoes_disponiveis = ["FAPESP", "FAPERJ", "FAPEMIG", "Outra..."]
                selecao_ant = st.session_state.get("f_aparceria", [])
                st.session_state["f_aparceria"] = st.multiselect(
                    "Quais Fundações de Amparo ...",
                    options=fundacoes_disponiveis,
                    default=selecao_ant
                )
                st.session_state["parcerias_info"] = st.text_area(
                    "Há parcerias ...?",
                    value=st.session_state.get("parcerias_info", "")
                )

        detalhes_por_forma = {}

        # 1) Sempre salvar "tabela_formas"
        formas_df_dict = st.session_state["df_formas_contratacao"].to_dict(orient="records")

        # 2) Verificar quais formas foram selecionadas
        selected_forms = [row["Forma de Contratação"] for row in formas_df_dict if row["Selecionado"]]


        def not_informed_if_empty(value):
            """
            Se 'value' for uma string vazia ou só espaços, retorna "não informado".
            Se for uma lista vazia, também retorna "não informado".
            Caso contrário, retorna 'value' sem alterações.
            """
            if value is None:
                return "não informado"

            if isinstance(value, str):
                if value.strip() == "":
                    return "não informado"
                return value

            if isinstance(value, list):
                if len(value) == 0:
                    return "não informado"
                return value

            # Se for algum outro tipo (dict, bool, etc.), deixamos como está:
            return value


        # 3) Se "Contrato Caixa" estiver em selected_forms, montar dict
        if "Contrato Caixa" in selected_forms:
            detalhes_por_forma["Contrato Caixa"] = {
                "Observações": not_informed_if_empty( st.session_state.get("observacoes_caixa", "") )
            }

        if "Contrato ICMBio" in selected_forms:
            detalhes_por_forma["Contrato ICMBio"] = {
                "Contratos Escolhidos": not_informed_if_empty( st.session_state.get("contrato_icmbio_escolhido", []) ),
                "Coordenação Geral Gestora": not_informed_if_empty( st.session_state.get("coord_geral_gestora", "") ),
                "Justificativa Uso ICMBio": not_informed_if_empty( st.session_state.get("justificativa_icmbio", "") )
            }

        if "Fundação de Apoio credenciada pelo ICMBio" in selected_forms:
            existe_proj = not_informed_if_empty( st.session_state.get("existe_projeto_cppar", "") )
            fundacao_dict = {
                "Já existe projeto CPPar?": existe_proj
            }
            if existe_proj == "Sim":  # Se for "não informado" não entraria, mas a critério seu
                fundacao_dict["SEI do Projeto"] = not_informed_if_empty( st.session_state.get("sei_projeto", "") )
                fundacao_dict["SEI da Ata/Decisão CPPar"] = not_informed_if_empty( st.session_state.get("sei_ata", "") )

            fundacao_dict["Concorda com IN 18/2018 e 12/2024?"] = not_informed_if_empty( st.session_state.get("in_concorda", "") )
            fundacao_dict["Justificativa Fundação de Apoio"] = not_informed_if_empty( st.session_state.get("justificativa_fundacao", "") )

            detalhes_por_forma["Fundação de Apoio credenciada pelo ICMBio"] = fundacao_dict

        if "Fundação de Amparo à pesquisa" in selected_forms:
            amparo_dict = {
                "IN de Amparo?": not_informed_if_empty( st.session_state.get("in_amparo", "") ),
                # Se a lista de fundações estiver vazia, vira "não informado"
                "Fundações Selecionadas": not_informed_if_empty( st.session_state.get("f_aparceria", []) ),
                "Informações de Parceria": not_informed_if_empty( st.session_state.get("parcerias_info", "") )
            }
            detalhes_por_forma["Fundação de Amparo à pesquisa"] = amparo_dict


        # Agora unimos tudo em st.session_state
        formas_dict = {
            "tabela_formas": formas_df_dict,
            "detalhes_por_forma": detalhes_por_forma
        }

        st.session_state["formas_contratacao_detalhes"] = formas_dict





    # botão do form para salvar os dados editados na sessão
    if st.form_submit_button("Salvar Alterações"):


        # Verificação prévia antes de salvar
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
            # salvar objetivos geral e específicos
            st.session_state["objetivo_geral"] = st.session_state["objetivo_geral"]


            # salvar textos
            st.session_state["introducao"] = st.session_state["introducao"]
            st.session_state["justificativa"] = st.session_state["justificativa"]
            st.session_state["metodologia"] = st.session_state["metodologia"]

            # salvar demais informações
            st.session_state["demais_informacoes"] = {
            "diretoria": diretoria_novo,
            "coordenacao_geral": coord_geral_novo,
            "coordenacao": coord_novo,
            "demandante": demandante_novo
            }

            
            # salvar eixos temáticos
            st.session_state["eixos_tematicos"] = st.session_state["eixos_tematicos"]

            # salvar insumos
            if "insumos" not in st.session_state:
                st.session_state["insumos"] = {}
            else:
                st.session_state["insumos"] = st.session_state["insumos"]

            # salvar unidades de conservação
            st.session_state["df_uc_editado"] = st.session_state["df_uc_editado"]

            # st.success("Alterações salvas com sucesso!")

        st.success("Alterações salvas com sucesso!")


# -------------------------------------------
# BOTÃO FINAL PARA SALVAR CADASTRO
# -------------------------------------------
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

# 1) Exibe resumos do SETOR
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
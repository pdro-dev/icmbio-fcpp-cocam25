import streamlit as st
import sqlite3
import json
import pandas as pd
import time as time

# Verifica login
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

DB_PATH = "database/app_data.db"

# -----------------------------------------------------------------------------
#                          FUNÇÕES AUXILIARES / CACHED
# -----------------------------------------------------------------------------
@st.cache_data
def get_iniciativas_usuario(perfil, setor):
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
def carregar_dados_iniciativa(id_iniciativa):
    """Carrega a última linha de tf_cadastro_regras_negocio (caso exista)."""
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

    # Verifica eixos temáticos salvos
    try:
        eixos_tematicos = json.loads(row["eixos_tematicos"]) if row["eixos_tematicos"] else []
    except:
        eixos_tematicos = []

    # Tentar carregar 'demais_informacoes' como dicionário
    info_json = row.get("demais_informacoes", "") or ""
    try:
        info_dict = json.loads(info_json) if info_json else {}
    except:
        info_dict = {}

    return {
        "objetivo_geral":      row["objetivo_geral"],
        "objetivo_especifico": row["objetivo_especifico"],
        "eixos_tematicos":     row["eixos_tematicos"],
        "introducao":          row.get("introducao", ""),
        "justificativa":       row.get("justificativa", ""),
        "metodologia":         row.get("metodologia", ""),
        "demais_informacoes":  info_dict,  # dicionário com {diretoria, coord_geral, etc.}
    }

@st.cache_data
def carregar_resumo_iniciativa(setor):
    """Exemplo simples: carrega o resumo a partir de td_dados_resumos_sei, filtrando por demandante."""
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM td_dados_resumos_sei WHERE demandante = ?"
    df = pd.read_sql_query(query, conn, params=[setor])
    conn.close()
    if df.empty:
        return None
    return df

def salvar_dados_iniciativa(
    id_iniciativa,
    usuario,
    objetivo_geral,
    objetivos_especificos,
    eixos_tematicos,
    introducao,
    justificativa,
    metodologia,
    demais_informacoes
):
    """
    Salva registro na tf_cadastro_regras_negocio, mantendo histórico máximo de 3 registros.
    - objetivos_especificos: lista de strings
    - eixos_tematicos: lista de dicts
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Limite de 3 históricos
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

    acoes_set   = set()
    insumos_set = set()
    for eixo in eixos_tematicos:
        for ac_id, ac_data in eixo.get("acoes_manejo", {}).items():
            acoes_set.add(ac_id)
            for ins_id in ac_data.get("insumos", []):
                insumos_set.add(ins_id)

    acoes_json  = json.dumps(list(acoes_set))
    insumos_json = json.dumps(list(insumos_set))

    # Monta a 'regra' consolidada
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

    # Insere
    cursor.execute("""
        INSERT INTO tf_cadastro_regras_negocio (
            id_iniciativa,
            usuario,
            objetivo_geral,
            objetivo_especifico,
            eixos_tematicos,
            acoes_manejo,
            insumos,
            regra,
            introducao,
            justificativa,
            metodologia,
            demais_informacoes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        demais_info_json
    ))

    conn.commit()
    conn.close()

@st.cache_data
def get_options_from_table(table_name, id_col, name_col, filter_col=None, filter_val=None):
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT {id_col}, {name_col} FROM {table_name}"
    params = ()
    if filter_col and filter_val is not None:
        query += f" WHERE {filter_col} = ?"
        params = (str(filter_val),)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    # Retorna dict do tipo {"1": "Nome", "2": "Outro Nome", ...}
    return {str(row[id_col]): row[name_col] for _, row in df.iterrows()}

# -----------------------------------------------------------------------------
#                            Sessão e funções
# -----------------------------------------------------------------------------
def exibir_info_lateral(id_iniciativa: int):
    """Exibe no sidebar informações complementares."""
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

    # 3) Eixos existentes
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
#            Inicialização para evitar KeyError no session_state
# -----------------------------------------------------------------------------
for key in ["introducao", "justificativa", "metodologia"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "demais_informacoes" not in st.session_state:
    st.session_state["demais_informacoes"] = {}

# -----------------------------------------------------------------------------
#                           Início da Página
# -----------------------------------------------------------------------------
st.subheader("📝 Cadastro de Regras de Negócio")
# st.divider()

perfil      = st.session_state["perfil"]
setor       = st.session_state["setor"]
cpf_usuario = st.session_state["cpf"]

# 2) Seleciona Iniciativa
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


# Só recarrega se a iniciativa mudou
if "carregou_iniciativa" not in st.session_state or st.session_state["carregou_iniciativa"] != nova_iniciativa:
    dados_iniciativa = carregar_dados_iniciativa(nova_iniciativa)

    # Se houver dados no banco, carregamos os eixos
    if dados_iniciativa is not None:
        st.session_state["eixos_tematicos"] = json.loads(dados_iniciativa.get("eixos_tematicos", "[]"))
    else:
        st.session_state["eixos_tematicos"] = []  # Mantém a estrutura vazia apenas se não houver dados

    st.session_state["carregou_iniciativa"] = nova_iniciativa  # Atualiza a iniciativa carregada


    if dados_iniciativa is not None:
        # 2.1) Carregou do tf_cadastro_regras_negocio
        st.session_state["objetivo_geral"]        = dados_iniciativa["objetivo_geral"]
        st.session_state["objetivos_especificos"] = json.loads(dados_iniciativa["objetivo_especifico"] or "[]")
        # Eixos
        if "eixos_tematicos" not in st.session_state or not st.session_state["eixos_tematicos"]:
            st.session_state["eixos_tematicos"] = json.loads(dados_iniciativa["eixos_tematicos"] or "[]")

        st.session_state["introducao"]    = dados_iniciativa["introducao"]
        st.session_state["justificativa"] = dados_iniciativa["justificativa"]
        st.session_state["metodologia"]   = dados_iniciativa["metodologia"]

        # Se vier no dicionário
        st.session_state["demais_informacoes"] = dados_iniciativa.get("demais_informacoes", {})

    else:
        # 2.2) Não achou nada em tf_cadastro_regras_negocio => Inicializa session_state
        st.session_state["objetivo_geral"]        = ""
        st.session_state["objetivos_especificos"] = []
        if "eixos_tematicos" not in st.session_state or not st.session_state["eixos_tematicos"]:
            st.session_state["eixos_tematicos"] = []
        st.session_state["introducao"]    = ""
        st.session_state["justificativa"] = ""
        st.session_state["metodologia"]   = ""
        st.session_state["demais_informacoes"] = {}

    # 2.3) Fallback: Se objetivo_geral ainda estiver vazio, busca no SEI
    if not st.session_state["objetivo_geral"]:
        conn = sqlite3.connect(DB_PATH)
        row_fallback = conn.execute("""
            SELECT objetivo_geral
            FROM td_dados_resumos_sei
            WHERE id_resumo = ?
            LIMIT 1
        """, (nova_iniciativa,)).fetchone()
        conn.close()

        if row_fallback:
            obj_geral_sei = row_fallback[0] or ""
            if obj_geral_sei:
                st.session_state["objetivo_geral"] = obj_geral_sei

    # 2.4) Fallback para introducao, justificativa e metodologia, se ainda vazios
    if (not st.session_state["introducao"]) or (not st.session_state["justificativa"]) or (not st.session_state["metodologia"]):
        conn = sqlite3.connect(DB_PATH)
        row_resumo_2 = conn.execute("""
            SELECT introdução,
                   justificativa,
                   metodologia,
                   diretoria,
                   coordenação_geral,
                   coordenação,
                   demandante
            FROM td_dados_resumos_sei
            WHERE id_resumo = ?
            LIMIT 1
        """, (nova_iniciativa,)).fetchone()
        conn.close()

        if row_resumo_2:
            (intro_sei, justif_sei, metod_sei,
             dir_sei, coord_geral_sei, coord_sei, demand_sei) = row_resumo_2

            if not st.session_state["introducao"] and intro_sei:
                st.session_state["introducao"] = intro_sei
            if not st.session_state["justificativa"] and justif_sei:
                st.session_state["justificativa"] = justif_sei
            if not st.session_state["metodologia"] and metod_sei:
                st.session_state["metodologia"] = metod_sei

            # Se "demais_informacoes" estiver vazio, podemos puxar de lá:
            if not st.session_state["demais_informacoes"]:
                st.session_state["demais_informacoes"] = {
                    "diretoria":          dir_sei or "",
                    "coordenacao_geral":  coord_geral_sei or "",
                    "coordenacao":        coord_sei or "",
                    "demandante":         demand_sei or ""
                }

    # 2.5) Marca que carregou
    st.session_state["carregou_iniciativa"] = nova_iniciativa


# Barra lateral
if st.sidebar.checkbox("Exibir informações da iniciativa", value=True):
    exibir_info_lateral(nova_iniciativa)


st.divider()

st.write(f"**Iniciativa Selecionada:** {iniciativas.set_index('id_iniciativa').loc[nova_iniciativa, 'nome_iniciativa']}")

# -------------------------------------------------------------------
#      TABS: Objetivos / Introdução / Justificativa / Metodologia
#            e a aba para Demais Informações
# -------------------------------------------------------------------
tab_intro, tab_obj, tab_justif, tab_metod, tab_eixos, tab_infos = st.tabs([
    "Introdução", "Objetivos", "Justificativa", "Metodologia", "Eixos Temáticos", "Demais Informações"
])


# -------------------------------------------
# 1) OBJETIVOS
# -------------------------------------------
with tab_obj:
    st.subheader("Objetivo Geral")
    st.session_state["objetivo_geral"] = st.text_area(
        "Descreva o Objetivo Geral:",
        value=st.session_state["objetivo_geral"],
        height=140,
    )

    st.subheader("Objetivos Específicos")
    with st.form("form_objetivos_especificos"):
        with st.expander("Objetivos Específicos Listados", expanded=False):
            st.write("📝 Edite os objetivos específicos da iniciativa.")
            st.caption("ℹ️ Use a tabela para adicionar, editar ou remover objetivos específicos.")

            obj_df = pd.DataFrame({
                "Objetivo Específico": st.session_state["objetivos_especificos"]
            }, dtype=str)

            edited_df = st.data_editor(
                obj_df,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Objetivo Específico": st.column_config.TextColumn(
                        "Descrição do Objetivo",
                        help="Digite cada objetivo específico",
                        default="",
                        max_chars=500
                    )
                },
                key="data_editor_objetivos"
            )
            btn_obj = st.form_submit_button("Aplicar alterações")
            if btn_obj:
                st.session_state["objetivos_especificos"] = (
                    edited_df["Objetivo Específico"].dropna().tolist()
                )
                st.success("Objetivos específicos atualizados com sucesso!")

# -------------------------------------------
# 2) INTRODUÇÃO, JUSTIFICATIVA, METODOLOGIA
# -------------------------------------------
with st.form("form_textos_resumo"):
    with tab_intro:
        # exibir nome completo da iniciativa selecionada
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

    # -------------------------------------------
    # 3) DEMAIS INFORMAÇÕES
    # -------------------------------------------
    with tab_infos:
        st.subheader("Demais Informações")
        st.write("Edição de Informações do Setor Demandante.")

        # Garante que "demais_informacoes" é um dicionário
        if not isinstance(st.session_state["demais_informacoes"], dict):
            try:
                st.session_state["demais_informacoes"] = json.loads(st.session_state["demais_informacoes"])
            except:
                st.session_state["demais_informacoes"] = {}


        # Lê do session_state (dict)
        di = st.session_state["demais_informacoes"].get("diretoria", "")
        cg = st.session_state["demais_informacoes"].get("coordenacao_geral", "")
        co = st.session_state["demais_informacoes"].get("coordenacao", "")
        dm = st.session_state["demais_informacoes"].get("demandante", "")

        with st.form("form_demais_informacoes"):
            diretoria_novo    = st.text_input("Diretoria:", value=di)
            coord_geral_novo  = st.text_input("Coordenação Geral:", value=cg)
            coord_novo        = st.text_input("Coordenação:", value=co)
            demandante_novo   = st.text_input("Demandante (Sigla):", value=dm, disabled=True)

            btn_demais = st.form_submit_button("Aplicar alterações")
            if btn_demais:
                st.session_state["demais_informacoes"]["diretoria"]         = diretoria_novo
                st.session_state["demais_informacoes"]["coordenacao_geral"] = coord_geral_novo
                st.session_state["demais_informacoes"]["coordenacao"]       = coord_novo
                st.session_state["demais_informacoes"]["demandante"]        = demandante_novo
                st.success("Demais informações atualizadas no session_state!")

    btn_textos = st.form_submit_button("Salvar")
    if btn_textos:
        st.success("Informações atualizadas na sessão.")
        st.warning("Clique em 'Salvar Cadastro' no final da página para gravar no banco de dados.")
        time.sleep(2)
        st.rerun()

st.divider()

with tab_eixos:
# -------------------------------------------
# 4) EIXOS TEMÁTICOS
# -------------------------------------------
    # st.subheader("🗂️ Eixos Temáticos")
    st.subheader("Eixos Temáticos")

    eixos_opcoes = get_options_from_table("td_samge_processos", "id_p", "nome")

    @st.cache_data
    def calcular_estatisticas_eixo(eixo):
        total_acoes = len(eixo.get("acoes_manejo", {}))
        total_insumos = sum(len(x.get("insumos", [])) for x in eixo.get("acoes_manejo", {}).values())
        total_valor = sum(sum(u.values()) for x in eixo.get("acoes_manejo", {}).values() for u in x.get("valor_ucs", {}).values())
        return {"acoes": total_acoes, "insumos": total_insumos, "valor_total": total_valor}

    @st.cache_data
    def get_acoes_opcoes():
        return get_options_from_table("td_samge_acoes_manejo", "id_ac", "nome")

    acoes_opcoes = get_acoes_opcoes()

    @st.dialog("Edição do Eixo Temático", width="large")
    def editar_eixo_dialog(index_eixo):
        if not (0 <= index_eixo < len(st.session_state["eixos_tematicos"])):
            st.warning("Índice de Eixo Temático fora do intervalo.")
            return

        eixo = st.session_state["eixos_tematicos"][index_eixo]
        st.subheader(f"Editando: {eixo.get('nome_eixo', '(sem nome)')}")

        show_insumos_key = f"show_insumos_{index_eixo}"
        if show_insumos_key not in st.session_state:
            st.session_state[show_insumos_key] = False

        # 4.1) Passo 1: Selecionar Ações
        with st.form(f"form_acoes_{index_eixo}", clear_on_submit=False):
            st.write("**Selecione as ações de manejo associadas ao Eixo.**")
            acoes_dict = get_options_from_table(
                "td_samge_acoes_manejo", "id_ac", "nome",
                filter_col="processo_id", filter_val=eixo["id_eixo"]
            )

            acoes_df = pd.DataFrame([
                {
                    "ID": ac_id,
                    "Ação": nome,
                    "Selecionado": ac_id in eixo["acoes_manejo"]
                }
                for ac_id, nome in acoes_dict.items()
            ])
            if "Selecionado" not in acoes_df.columns:
                acoes_df["Selecionado"] = False

            edited_acoes = st.data_editor(
                acoes_df,
                column_config={
                    "ID": st.column_config.TextColumn(disabled=True),
                    "Ação": st.column_config.TextColumn(disabled=True),
                    "Selecionado": st.column_config.CheckboxColumn("Selecionar")
                },
                hide_index=True,
                use_container_width=True,
                key=f"editor_acoes_{index_eixo}"
            )

            btn_acoes = st.form_submit_button("Avançar")
            if btn_acoes:
                if "Selecionado" in edited_acoes.columns:
                    novas_acoes = edited_acoes.loc[edited_acoes["Selecionado"], "ID"].tolist()
                else:
                    novas_acoes = []

                st.session_state[f"acoes_selecionadas_{index_eixo}"] = novas_acoes

                # Remove as não selecionadas
                for ac_salvo in list(eixo["acoes_manejo"].keys()):
                    if ac_salvo not in novas_acoes:
                        del eixo["acoes_manejo"][ac_salvo]

                # Cria as novas
                for ac_id in novas_acoes:
                    if ac_id not in eixo["acoes_manejo"]:
                        eixo["acoes_manejo"][ac_id] = {"insumos": [], "valor_ucs": {}}

                st.session_state["eixos_tematicos"][index_eixo] = eixo
                st.session_state[show_insumos_key] = True
                st.rerun()

        # 4.2) Passo 2: Selecionar Insumos
        novas_acoes = st.session_state.get(f"acoes_selecionadas_{index_eixo}", [])
        if st.session_state[show_insumos_key] and novas_acoes:
            conn = sqlite3.connect(DB_PATH)
            df_insumos_all = pd.read_sql_query("SELECT id, descricao_insumo, elemento_despesa, especificacao_padrao FROM td_insumos", conn)
            conn.close()

            # Filtros no session
            elem_key = f"filtro_elem_{index_eixo}"
            spec_key = f"filtro_spec_{index_eixo}"
            if elem_key not in st.session_state:
                st.session_state[elem_key] = ""
            if spec_key not in st.session_state:
                st.session_state[spec_key] = ""

            elem_filter = st.session_state[elem_key]
            spec_filter = st.session_state[spec_key]

            # Cross-filter local
            df_elem = df_insumos_all
            if elem_filter:
                df_elem = df_elem[df_elem["elemento_despesa"] == elem_filter]
            espec_possiveis = sorted(df_elem["especificacao_padrao"].dropna().unique())
            if spec_filter and spec_filter not in espec_possiveis:
                spec_filter = ""
                st.session_state[spec_key] = ""

            df_spec = df_insumos_all
            if spec_filter:
                df_spec = df_spec[df_spec["especificacao_padrao"] == spec_filter]
            elem_possiveis = sorted(df_spec["elemento_despesa"].dropna().unique())
            if elem_filter and elem_filter not in elem_possiveis:
                elem_filter = ""
                st.session_state[elem_key] = ""

            with st.expander("🔍 Filtros de Insumos", expanded=True):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    novo_elem = st.selectbox(
                        "Filtrar por elemento de despesa:",
                        options=[""] + elem_possiveis,
                        index=([""] + elem_possiveis).index(elem_filter)
                    )
                with col_f2:
                    novo_spec = st.selectbox(
                        "Filtrar por especificação padrão:",
                        options=[""] + espec_possiveis,
                        index=([""] + espec_possiveis).index(spec_filter)
                    )

            # Se combos mudaram
            if (novo_elem != elem_filter) or (novo_spec != spec_filter):
                st.session_state[elem_key] = novo_elem
                st.session_state[spec_key] = novo_spec
                st.rerun()

            # Define subset final
            df_filter = df_insumos_all.copy()
            if st.session_state[elem_key]:
                df_filter = df_filter[df_filter["elemento_despesa"] == st.session_state[elem_key]]
            if st.session_state[spec_key]:
                df_filter = df_filter[df_filter["especificacao_padrao"] == st.session_state[spec_key]]

            with st.form(f"form_insumos_{index_eixo}", clear_on_submit=False):
                st.write("**Selecione os insumos para cada ação**")

                for ac_id in novas_acoes:
                    st.markdown(f"### Ação: {acoes_opcoes.get(ac_id, 'Ação Desconhecida')}")

                    ac_data = eixo["acoes_manejo"].get(ac_id, {"insumos": [], "valor_ucs": {}})

                    # Marcar insumos selecionados
                    sel_ids = set(ac_data["insumos"])
                    df_sel = df_insumos_all[df_insumos_all["id"].isin(sel_ids)]

                    df_combo = pd.concat([df_filter, df_sel]).drop_duplicates(subset=["id"])
                    df_combo["Selecionado"] = df_combo["id"].apply(lambda x: x in sel_ids)

                    # Remove colunas extras do editor
                    for c_rm in ["elemento_despesa", "especificacao_padrao"]:
                        if c_rm in df_combo.columns:
                            df_combo.drop(columns=[c_rm], inplace=True)

                    df_combo.rename(columns={
                        "id": "ID",
                        "descricao_insumo": "Insumo"
                    }, inplace=True)

                    edited_ins = st.data_editor(
                        df_combo,
                        column_config={
                            "ID": st.column_config.TextColumn(disabled=True),
                            "Insumo": st.column_config.TextColumn(disabled=True),
                            "Selecionado": st.column_config.CheckboxColumn("Selecionar")
                        },
                        hide_index=True,
                        use_container_width=True,
                        key=f"editor_ins_{ac_id}"
                    )

                    insumos_final = edited_ins.loc[edited_ins["Selecionado"], "ID"].tolist()
                    ac_data["insumos"] = insumos_final
                    eixo["acoes_manejo"][ac_id] = ac_data

                btn_insumos = st.form_submit_button("Salvar Insumos")
                if btn_insumos:
                    st.session_state["eixos_tematicos"][index_eixo] = eixo
                    st.success("Insumos atualizados com sucesso!")
                    st.toast("Insumos atualizados!", icon="✅")
                    time.sleep(1)
                    st.rerun()

        if st.button("Fechar e Voltar", key=f"btn_fechar_{index_eixo}"):
            st.session_state.modal_fechado = True
            st.rerun()

    # -----------------------------------------------------------------------------
    # Modal de Edição de Valores por Unidade
    # -----------------------------------------------------------------------------

    # Modal de Edição de Valores por Unidade
    @st.dialog("Editar Valores por Unidade", width="large")
    def editar_valores_unidade(index_eixo):
        if not (0 <= index_eixo < len(st.session_state["eixos_tematicos"])):
            st.warning("Índice de Eixo Temático fora do intervalo.")
            return

        eixo = st.session_state["eixos_tematicos"][index_eixo]
        st.subheader(f"Edição de Valores - {eixo.get('nome_eixo', '(Sem Nome)')}")

        id_iniciativa = st.session_state.get("sel_iniciativa")
        if not id_iniciativa:
            st.error("Nenhuma iniciativa selecionada.")
            return

        # Carregar unidades e valores alocados na iniciativa
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT "Unidade de Conservação", "VALOR TOTAL ALOCADO"
            FROM tf_cadastros_iniciativas
            WHERE id_iniciativa = ?
        """
        df_unidades = pd.read_sql_query(query, conn, params=[id_iniciativa])
        conn.close()

        if df_unidades.empty:
            st.info("Nenhuma unidade de conservação encontrada para esta iniciativa.")
            return

        df_unidades.rename(columns={"Unidade de Conservação": "Unidade", "VALOR TOTAL ALOCADO": "Valor Alocado"}, inplace=True)

        # Recuperar valores editados anteriormente
        valores_ucs = eixo.get("valor_ucs", {})

        # Criar coluna "Novo Valor Alocado", mantendo valores editados
        df_unidades["Novo Valor Alocado"] = df_unidades["Unidade"].apply(lambda x: valores_ucs.get(x, 0.0))

        # Criar coluna "Saldo" antes de exibir o editor
        df_unidades["Saldo"] = df_unidades["Valor Alocado"] - df_unidades["Novo Valor Alocado"]

        # Toggle para copiar os valores da coluna "Valor Alocado"
        copiar_valores = st.toggle("Copiar valores de 'Valor Alocado' para 'Novo Valor Alocado'", value=False)

        # Se ativado, copia os valores da coluna "Valor Alocado"
        if copiar_valores:
            df_unidades["Novo Valor Alocado"] = df_unidades["Valor Alocado"]
            df_unidades["Saldo"] = 0.0  

        # Criar data editor com a coluna "Saldo"
        edited_df = st.data_editor(
            df_unidades,
            column_config={
                "Unidade": st.column_config.TextColumn(disabled=True),
                "Valor Alocado": st.column_config.NumberColumn(disabled=True),
                "Novo Valor Alocado": st.column_config.NumberColumn("Novo Valor Alocado", min_value=0.0),
                "Saldo": st.column_config.NumberColumn("Saldo (Diferença)", disabled=True)
            },
            use_container_width=True,
            key=f"editor_valores_{index_eixo}"
        )

        # Atualizar saldo após edição
        edited_df["Saldo"] = edited_df["Valor Alocado"] - edited_df["Novo Valor Alocado"] # Calcula a diferença


        # Salvar mudanças e atualizar saldo antes
        if st.button("💾 Salvar Valores", key=f"btn_salvar_valores_{index_eixo}"):
            # Recalcula o saldo antes de salvar
            edited_df["Saldo"] = edited_df["Valor Alocado"] - edited_df["Novo Valor Alocado"]
            
            eixo["valor_ucs"] = {row["Unidade"]: row["Novo Valor Alocado"] for _, row in edited_df.iterrows() if row["Novo Valor Alocado"] > 0}

            st.session_state["eixos_tematicos"][index_eixo] = eixo
            st.success("Valores atualizados com sucesso!")
            st.toast("Valores salvos!", icon="✅")
            time.sleep(1)
            st.rerun()


        if st.button("❌ Fechar", key=f"btn_fechar_valores_{index_eixo}"):
            st.session_state.modal_fechado = True
            st.rerun()






    # -----------------------------------------------------------------------------
    # Adicionar Eixo Temático
    # -----------------------------------------------------------------------------
    novo_eixo_id = st.selectbox(
        "Escolha um Eixo (Processo SAMGe) para adicionar:",
        options=[None] + sorted(eixos_opcoes.keys(), key=lambda x: eixos_opcoes[x]),
        format_func=lambda x: eixos_opcoes.get(x, "Selecione..."),
        key="sel_novo_eixo"
    )

    if st.button("➕ Adicionar Eixo Temático", key="btn_add_eixo"):
        if novo_eixo_id is None:
            st.warning("Selecione um eixo válido antes de clicar em Adicionar Eixo Temático.")
        else:
            eixo_id_int = int(novo_eixo_id)
            ids_existentes = [int(e["id_eixo"]) for e in st.session_state["eixos_tematicos"]]
            if eixo_id_int not in ids_existentes:
                st.session_state["eixos_tematicos"].append({
                    "id_eixo": eixo_id_int,
                    "nome_eixo": eixos_opcoes.get(str(novo_eixo_id), "Novo Eixo"),
                    "acoes_manejo": {},
                    "valor_ucs": {}
                })
                st.rerun()
            else:
                st.info("Este eixo já existe na lista.")

    def calcular_valores_alocados(eixo):
        """Calcula a soma dos valores editados e a contagem de unidades que receberam valores."""
        if "valor_ucs" not in eixo or not eixo["valor_ucs"]:
            return 0, 0  # Retorna (soma, quantidade) como zero se não houver dados

        soma_valores = sum(eixo["valor_ucs"].values())
        qtd_unidades = len(eixo["valor_ucs"])
        return soma_valores, qtd_unidades

    # Lista de eixos criados
    for i, eixo in enumerate(st.session_state["eixos_tematicos"]):
        stats = calcular_estatisticas_eixo(eixo)
        valor_total_alocado, unidades_com_valor = calcular_valores_alocados(eixo)

        with st.expander(f"📌 Eixo: {eixo['nome_eixo']}", expanded=False):
            col1, col2, col3 = st.columns(3)
            col1.metric("Ações", stats["acoes"], border=True)
            col2.metric("Insumos", stats["insumos"], border=True)
            # col2.metric("Valor Total", f"R$ {stats['valor_total']:,.2f}", border=True)
            col1.metric("Total Alocado", f"R$ {valor_total_alocado:,.2f}", border=True)
            col2.metric("Unidades Beneficiadas", unidades_com_valor, border=True)


            with col3:
                # col_edit, col_del = st.columns(2)
                if st.button("▪️ Editar Ações e Insumos", key=f"btn_edit_{i}", use_container_width=True, type='secondary'):
                    st.session_state["modo_editar_eixo"] = i
                    st.session_state.modal_fechado = False
                    st.rerun()
                # botão para abrir o modal de edição de valores por uc
                if st.button("▪️ Editar Valores por Unidade", key=f"btn_edit_uc_{i}", use_container_width=True, type='secondary'):
                   st.session_state["modo_editar_uc"] = i
                   st.session_state.modal_fechado = False
                   st.rerun()

                if st.button("🗑️ Excluir Eixo", key=f"btn_del_{i}", use_container_width=True, type='tertiary'):
                    st.session_state["eixos_tematicos"].pop(i)
                    st.rerun()

    # Verifica qual modal precisa ser aberto e garante que o correto seja acionado
    modo_idx_valores = st.session_state.get("modo_editar_uc")
    modo_idx_eixo = st.session_state.get("modo_editar_eixo")

    if not st.session_state.get("modal_fechado", True):
        if modo_idx_valores is not None and 0 <= modo_idx_valores < len(st.session_state["eixos_tematicos"]):
            editar_valores_unidade(modo_idx_valores)
            st.session_state["modo_editar_uc"] = None  # Resetar após uso
            st.stop()
        elif modo_idx_eixo is not None and 0 <= modo_idx_eixo < len(st.session_state["eixos_tematicos"]):
            editar_eixo_dialog(modo_idx_eixo)
            st.session_state["modo_editar_eixo"] = None  # Resetar após uso
            st.stop()

    # Se nenhum modal for acionado, resetamos os estados
    st.session_state["modo_editar_eixo"] = None
    st.session_state["modo_editar_uc"] = None




col1, col2, col3 = st.columns(3)
with col2:
    if st.button("💾 Salvar Cadastro", key="btn_salvar_geral"):
        salvar_dados_iniciativa(
            id_iniciativa       = nova_iniciativa,
            usuario             = cpf_usuario,
            objetivo_geral      = st.session_state["objetivo_geral"],
            objetivos_especificos = st.session_state["objetivos_especificos"],
            eixos_tematicos     = st.session_state["eixos_tematicos"],
            introducao          = st.session_state["introducao"],
            justificativa       = st.session_state["justificativa"],
            metodologia         = st.session_state["metodologia"],
            demais_informacoes  = st.session_state["demais_informacoes"]
        )
        st.success("✅ Cadastro atualizado com sucesso!")
        st.toast("Cadastro atualizado com sucesso!")
        time.sleep(2)
        st.session_state["modo_editar_eixo"] = None
        st.rerun()



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
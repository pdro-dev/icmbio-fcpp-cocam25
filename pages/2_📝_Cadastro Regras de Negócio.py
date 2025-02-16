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
    """Retorna a última versão dos dados da iniciativa cadastrada em tf_cadastro_regras_negocio."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT * FROM tf_cadastro_regras_negocio 
        WHERE id_iniciativa = ? 
        ORDER BY data_hora DESC LIMIT 1
    """
    dados = pd.read_sql_query(query, conn, params=[id_iniciativa])
    conn.close()
    return dados.iloc[0] if not dados.empty else None

@st.cache_data
def carregar_resumo_iniciativa(setor):
    """Exemplo simples: carrega o resumo a partir de td_dados_resumos_sei, filtrando por demandante."""
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM td_dados_resumos_sei WHERE demandante = ?"
    dados = pd.read_sql_query(query, conn, params=[setor])
    conn.close()
    return dados if not dados.empty else None

def salvar_dados_iniciativa(
    id_iniciativa,
    usuario,
    objetivo_geral,
    objetivos_especificos,
    eixos_tematicos
):
    """
    Salva registro na tf_cadastro_regras_negocio, mantendo histórico máximo de 3 registros.
    - objetivos_especificos: lista de strings
    - eixos_tematicos: lista de dicts, cada dict pode ter {id_eixo, nome_eixo, acoes_manejo, ...}
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Remove o registro mais antigo se já tiver 3
    cursor.execute(
        "SELECT COUNT(*) FROM tf_cadastro_regras_negocio WHERE id_iniciativa = ?",
        (id_iniciativa,)
    )
    total_registros = cursor.fetchone()[0]

    if total_registros >= 3:
        cursor.execute("""
            DELETE FROM tf_cadastro_regras_negocio 
            WHERE id IN (
                SELECT id FROM tf_cadastro_regras_negocio 
                WHERE id_iniciativa = ? 
                ORDER BY data_hora ASC LIMIT 1
            )
        """, (id_iniciativa,))

    # 2. Converte listas/dicionários para JSON (para as colunas específicas)
    objetivos_json = json.dumps(objetivos_especificos)  # ex.: ["obj1", "obj2"]
    eixos_json = json.dumps(eixos_tematicos)            # ex.: [{"id_eixo":..., "acoes_manejo":...}, ...]

    # 3. Extrair lista geral de acoes e insumos, se quiser gravar em colunas específicas
    acoes_set = set()
    insumos_set = set()

    # eixos_tematicos: 
    #   [ 
    #     {
    #       "id_eixo": ...,
    #       "nome_eixo": "...",
    #       "acoes_manejo": {
    #          <id_acao>: {
    #             "insumos": [ ... ],
    #             "valor_ucs": { ... }
    #          },
    #          ...
    #       }
    #     },
    #     ...
    #   ]
    for eixo in eixos_tematicos:
        acoes_manejo_dict = eixo.get("acoes_manejo", {})
        for ac_id, ac_data in acoes_manejo_dict.items():
            acoes_set.add(ac_id)
            for ins_id in ac_data.get("insumos", []):
                insumos_set.add(ins_id)

    # Passa para lista, caso precise
    acoes_list = list(acoes_set)
    insumos_list = list(insumos_set)

    acoes_json = json.dumps(acoes_list)    # exemplo: ["ac_1", "ac_2"]
    insumos_json = json.dumps(insumos_list) # exemplo: ["ins_1", "ins_2"]

    # 4. Montar o dicionário final da “regra” (tudo que o usuário configurou)
    final_rule = {
        "objetivo_geral": objetivo_geral,
        "objetivos_especificos": objetivos_especificos,
        "eixos_tematicos": eixos_tematicos,
        "acoes": acoes_list,
        "insumos": insumos_list
    }
    regra_json = json.dumps(final_rule)

    # 5. Inserir no banco
    cursor.execute("""
        INSERT INTO tf_cadastro_regras_negocio 
        (
          id_iniciativa, 
          usuario, 
          objetivo_geral, 
          objetivo_especifico, 
          eixos_tematicos,
          acoes_manejo,
          insumos,
          regra
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id_iniciativa,                # id_iniciativa
        usuario,                      # usuario
        objetivo_geral,              # objetivo_geral
        objetivos_json,              # objetivo_especifico
        eixos_json,                  # eixos_tematicos
        acoes_json,                  # acoes_manejo
        insumos_json,                # insumos
        regra_json                   # regra (tudo consolidado)
    ))

    conn.commit()
    conn.close()

@st.cache_data
def get_options_from_table(table_name, id_col, name_col, filter_col=None, filter_val=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = f"SELECT {id_col}, {name_col} FROM {table_name}"
    params = ()
    if filter_col and filter_val is not None:
        query += f" WHERE {filter_col} = ?"
        params = (str(filter_val),)

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return {str(row[0]): row[1] for row in results}


def reload_iniciativa(id_iniciativa: int):
    """Recarrega do banco os dados da iniciativa e sobrescreve o st.session_state."""
    dados_iniciativa = carregar_dados_iniciativa(id_iniciativa)
    if dados_iniciativa is not None:
        st.session_state["objetivo_geral"] = dados_iniciativa["objetivo_geral"]
        st.session_state["objetivos_especificos"] = json.loads(dados_iniciativa["objetivo_especifico"])
        st.session_state["eixos_tematicos"] = json.loads(dados_iniciativa["eixos_tematicos"])
        st.success("Dados recarregados do banco com sucesso!")
    else:
        st.session_state["objetivo_geral"] = ""
        st.session_state["objetivos_especificos"] = []
        st.session_state["eixos_tematicos"] = []
        st.warning("Nenhum registro encontrado no banco para esta iniciativa.")


def exibir_info_lateral(id_iniciativa: int):
    """Exibe no sidebar as informações extra de diversas tabelas sobre a iniciativa selecionada."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    st.sidebar.write("### Informações da Iniciativa")

    # 1) Buscar dados de 'tf_cadastros_iniciativas' + demandante e contagem de unidades
    query_inic = """
    SELECT 
        ci.id_demandante, 
        COUNT(DISTINCT ci.cnuc) AS num_unidades, 
        d.nome_demandante
    FROM tf_cadastros_iniciativas ci
    JOIN td_demandantes d 
      ON ci.id_demandante = d.id_demandante
    WHERE ci.id_iniciativa = ?
    GROUP BY ci.id_demandante
    """
    row_inic = cursor.execute(query_inic, (id_iniciativa,)).fetchone()
    if row_inic:
        id_demandante, num_unidades, nome_demandante = row_inic

        st.sidebar.write(f"**Demandante:** {nome_demandante}")
        st.sidebar.write(f"**Número de Unidades:** {num_unidades}")
    else:
        st.sidebar.info("Iniciativa não encontrada em tf_cadastros_iniciativas.")

    # 2) Exibir dados de 'td_dados_resumos_sei' via id_resumo vinculado a id_iniciativa
    query_resumo = """
    SELECT diretoria, coordenação_geral, coordenação
    FROM td_dados_resumos_sei
    WHERE id_resumo = ?
    LIMIT 1
    """
    row_resumo = cursor.execute(query_resumo, (id_iniciativa,)).fetchone()
    if row_resumo:
        dir_, coord_geral, coord_ = row_resumo
        st.sidebar.write(f"**Diretoria:** {dir_ if dir_ else 'sem informação'}")
        st.sidebar.write(f"**Coord. Geral:** {coord_geral if coord_geral else 'sem informação'}")
        st.sidebar.write(f"**Coordenação:** {coord_ if coord_ else 'sem informação'}")
    else:
        st.sidebar.info("Sem resumo SEI cadastrado para esta iniciativa.")

    # 3) Buscar Eixos existentes em tf_cadastro_regras_negocio e exibir como "pills" desativadas
    query_eixos = """
    SELECT eixos_tematicos
    FROM tf_cadastro_regras_negocio
    WHERE id_iniciativa = ?
    ORDER BY data_hora DESC
    LIMIT 1
    """
    row_eixos = cursor.execute(query_eixos, (id_iniciativa,)).fetchone()
    conn.close()  # Já podemos fechar aqui

    if row_eixos:
        eixos_tematicos_json = row_eixos[0]  # Coluna eixos_tematicos
        if eixos_tematicos_json:
            # Decodifica JSON em lista de dicts, ex: [{"id_eixo":..., "nome_eixo":"...", ...}, ...]
            eixos_tematicos_list = json.loads(eixos_tematicos_json)
            # Gera a lista de nomes
            lista_nomes_eixos = [eixo.get("nome_eixo", "Eixo Sem Nome") for eixo in eixos_tematicos_list]
            # Exibe como 'pills' usando multiselect disabled=True
            st.sidebar.pills(
                "Eixos Temáticos gravados:",
                options=lista_nomes_eixos,
                default=None,
                disabled=False
            )
        else:
            st.sidebar.info("Nenhum eixo temático cadastrado no momento.")
    else:
        st.sidebar.info("Nenhum eixo temático cadastrado.")



    
    # st.divider()
    # if st.sidebar.button("🔄 Recarregar informações do banco de dados"):
    # # Pressionando este botão, você recarrega a iniciativa selecionada
    # # Necessita saber qual iniciativa está selecionada (nova_iniciativa)
    #     if "id_iniciativa_atual" in st.session_state:
    #         reload_iniciativa(st.session_state["id_iniciativa_atual"])
    #         st.rerun()
    #     else:
    #         st.sidebar.warning("Selecione uma iniciativa primeiro.")



# =============================================================================
#                               INÍCIO DA PÁGINA
# =============================================================================
st.header("📝 Cadastro de Regras de Negócio")

perfil = st.session_state["perfil"]
setor = st.session_state["setor"]
cpf_usuario = st.session_state["cpf"]

st.divider()
st.caption("Resumo Executivo de Iniciativas", help="ref.: documentos SEI")

# ---------- Exibe resumo da(s) iniciativa(s) do SETOR -------------
def tratar_valor(valor):
    if pd.isna(valor) or valor is None or str(valor).strip().lower() == "null":
        return "(sem informação)"
    return str(valor).strip()

resumos = carregar_resumo_iniciativa(setor)
if resumos is not None:
    for _, resumo in resumos.iterrows():
        nome_iniciativa = tratar_valor(resumo.get("iniciativa", "Iniciativa Desconhecida"))
        with st.expander(f"📖 {nome_iniciativa}", expanded=False):
            st.divider()
            st.write(f"**🎯 Objetivo Geral:** {tratar_valor(resumo.get('objetivo_geral'))}")
            st.divider()
            st.write(f"**🏢 Diretoria:** {tratar_valor(resumo.get('diretoria'))}")
            st.write(f"**📌 Coordenação Geral:** {tratar_valor(resumo.get('coordenação_geral'))}")
            st.write(f"**🗂 Coordenação:** {tratar_valor(resumo.get('coordenação'))}")
            st.write(f"**📍 Demandante:** {tratar_valor(resumo.get('demandante'))}")
            st.divider()
            st.write(f"**📝 Introdução:** {tratar_valor(resumo.get('introdução'))}")
            st.divider()
            st.write(f"**💡 Justificativa:** {tratar_valor(resumo.get('justificativa'))}")
            st.divider()
            st.write(f"**🏞 Unidades de Conservação / Benefícios:** {tratar_valor(resumo.get('unidades_de_conservação_beneficiadas'))}")
            st.divider()
            st.write(f"**🔬 Metodologia:** {tratar_valor(resumo.get('metodologia'))}")

st.divider()




# ---------- Seleciona Iniciativa que será detalhada -------------
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

# # escrever id_iniciativa_atual no session_state
# st.session_state["id_iniciativa_atual"] = nova_iniciativa
# # obter no núm. do id da iniciativa atual
# st.write(nova_iniciativa)

# Carregar dados do banco APENAS se o usuário ainda não tiver alterado algo no session_state
if "carregou_iniciativa" not in st.session_state or st.session_state["carregou_iniciativa"] != nova_iniciativa:
    dados_iniciativa = carregar_dados_iniciativa(nova_iniciativa)

    if dados_iniciativa is not None:
        st.session_state["objetivo_geral"] = dados_iniciativa["objetivo_geral"]
        st.session_state["objetivos_especificos"] = json.loads(dados_iniciativa["objetivo_especifico"])
        st.session_state["eixos_tematicos"] = json.loads(dados_iniciativa["eixos_tematicos"])
    else:
        # Se não há nada em tf_cadastro_regras_negocio, iniciamos vazio
        st.session_state["objetivo_geral"] = ""
        st.session_state["objetivos_especificos"] = []
        st.session_state["eixos_tematicos"] = []


    # Se mesmo após carregar do tf_cadastro_regras_negocio ainda estiver vazio,
    # tentamos buscar do td_dados_resumos_sei como "sugestão".
    if not st.session_state["objetivo_geral"]:
        conn = sqlite3.connect(DB_PATH)
        # Busca a linha em td_dados_resumos_sei correspondente a esta iniciativa
        row_resumo = conn.execute("""
        SELECT objetivo_geral
        FROM td_dados_resumos_sei
        WHERE id_resumo = ?
        LIMIT 1
    """, (nova_iniciativa,)).fetchone()
    conn.close()

    if row_resumo:
        # Como só selecionou 1 coluna, row_resumo é algo como ("texto do objetivo",)
        sei_obj_geral = row_resumo[0]  # aqui deve ser índice [0]
        if sei_obj_geral:
            st.session_state["objetivo_geral"] = sei_obj_geral

    # Marca que já carregou os dados desta iniciativa, para evitar sobrescrita
    st.session_state["carregou_iniciativa"] = nova_iniciativa

# Exibe o nome da iniciativa selecionada

# Menu lateral
if st.sidebar.checkbox("Exibir informações da iniciativa", value=False):
    exibir_info_lateral(nova_iniciativa)

# --------------- SEÇÃO: OBJETIVO GERAL  ---------------
st.subheader("🎯 Objetivo Geral")
st.session_state["objetivo_geral"] = st.text_area(
    "Descreva o Objetivo Geral:",
    value=st.session_state["objetivo_geral"],
    height=100,
    key="txt_objetivo_geral"
)



# --------------- SEÇÃO: OBJETIVOS ESPECÍFICOS  ---------------
st.subheader("🎯 Objetivos Específicos")

# Cria o formulário
with st.form("form_objetivos_especificos"):
    with st.expander("Objetivos Específicos Listados", expanded=False):
        st.write("📝 Edite os objetivos específicos da iniciativa.")
        st.write("ℹ️ Use a tabela para adicionar, editar ou remover objetivos específicos.")
        # Monta DataFrame inicial
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

        # Botão de submit do formulário
        submit_obj = st.form_submit_button("Aplicar alterações")

        # Só atualiza session_state se o usuário clicar no botão de submit
        if submit_obj:
            st.session_state["objetivos_especificos"] = (
                edited_df["Objetivo Específico"].dropna().tolist()
            )
            st.success("Objetivos específicos atualizados com sucesso!")

st.divider()

# --------------- SEÇÃO: EIXOS TEMÁTICOS ---------------
st.subheader("🗂️ Eixos Temáticos")

# Carrega opções do SAMGe
eixos_opcoes = get_options_from_table("td_samge_processos", "id_p", "nome")

@st.cache_data
def calcular_estatisticas_eixo(eixo):
    total_acoes = len(eixo.get("acoes_manejo", {}))
    total_insumos = sum(len(ac.get("insumos", [])) for ac in eixo.get("acoes_manejo", {}).values())
    total_valor = sum(sum(uc.values()) for uc in eixo.get("valor_ucs", {}).values())
    return {"acoes": total_acoes, "insumos": total_insumos, "valor_total": total_valor}



import time

@st.dialog("Edição do Eixo Temático", width="large")
def editar_eixo_dialog(index_eixo):
    if not (0 <= index_eixo < len(st.session_state["eixos_tematicos"])):
        st.warning("Índice de Eixo Temático fora do intervalo.")
        return

    eixo = st.session_state["eixos_tematicos"][index_eixo]
    st.subheader(f"Editando: {eixo.get('nome_eixo', '(sem nome)')}")

    # Para controlar se mostra ou não o passo de insumos
    show_insumos_key = f"show_insumos_{index_eixo}"
    if show_insumos_key not in st.session_state:
        st.session_state[show_insumos_key] = False

    #####################################################
    # Passo 1: Selecionar Ações
    #####################################################
    with st.form(f"form_acoes_{index_eixo}", clear_on_submit=False):
        st.write("**Selecione as ações de manejo associadas ao Eixo.**")

        # 1) Monta DataFrame de Ações
        acoes_opcoes = get_options_from_table(
            "td_samge_acoes_manejo",
            "id_ac",
            "nome",
            filter_col="processo_id",
            filter_val=eixo["id_eixo"]
        )
        acoes_df = pd.DataFrame([
            {
                "ID": ac_id,
                "Ação": nome,
                "Selecionado": ac_id in eixo["acoes_manejo"]  # já marcadas se existiam
            }
            for ac_id, nome in acoes_opcoes.items()
        ])

        if "Selecionado" not in acoes_df.columns:
            acoes_df["Selecionado"] = False

        # Editor para as ações
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

        # Botão "Avançar"
        submit_acoes = st.form_submit_button("Avançar")
        if submit_acoes:
            if "Selecionado" in edited_acoes.columns:
                novas_acoes = edited_acoes.loc[edited_acoes["Selecionado"], "ID"].tolist()
            else:
                novas_acoes = []

            st.session_state[f"acoes_selecionadas_{index_eixo}"] = novas_acoes

            # Remove ações que não foram selecionadas
            for ac_id_salvo in list(eixo["acoes_manejo"].keys()):
                if ac_id_salvo not in novas_acoes:
                    del eixo["acoes_manejo"][ac_id_salvo]

            # Cria as novas ações no dicionário
            for ac_id in novas_acoes:
                if ac_id not in eixo["acoes_manejo"]:
                    eixo["acoes_manejo"][ac_id] = {"insumos": [], "valor_ucs": {}}

            st.session_state["eixos_tematicos"][index_eixo] = eixo

            # Marca para mostrar o passo 2
            st.session_state[show_insumos_key] = True

    #####################################################
    # Passo 2: Selecionar Insumos com Cross-Filter
    #####################################################
    novas_acoes = st.session_state.get(f"acoes_selecionadas_{index_eixo}", [])

    if st.session_state[show_insumos_key] and novas_acoes:
        # Carrega TODOS os insumos
        conn = sqlite3.connect(DB_PATH)
        df_all_insumos = pd.read_sql_query("""
            SELECT
                id,
                descricao_insumo,
                elemento_despesa,
                especificacao_padrao
            FROM td_insumos
        """, conn)
        conn.close()

        # Chaves no session_state para combos
        elem_key = f"filtro_elemento_{index_eixo}"
        spec_key = f"filtro_especificacao_{index_eixo}"

        if elem_key not in st.session_state:
            st.session_state[elem_key] = ""
        if spec_key not in st.session_state:
            st.session_state[spec_key] = ""

        elemento_despesa = st.session_state[elem_key]
        especificacao = st.session_state[spec_key]

        # 1) Cross filtering combos
        # filtra localmente p/ descobrir espec. possíveis para o elemento atual
        df_elem_filtered = df_all_insumos
        if elemento_despesa:
            df_elem_filtered = df_elem_filtered[df_elem_filtered["elemento_despesa"] == elemento_despesa]
        espec_possiveis = sorted(df_elem_filtered["especificacao_padrao"].dropna().unique())

        # se a espec nao estiver mais na lista, reset
        if especificacao and especificacao not in espec_possiveis:
            especificacao = ""
            st.session_state[spec_key] = ""

        # filtra localmente p/ descobrir elem. possíveis p/ a espec atual
        df_spec_filtered = df_all_insumos
        if especificacao:
            df_spec_filtered = df_spec_filtered[df_spec_filtered["especificacao_padrao"] == especificacao]
        elem_possiveis = sorted(df_spec_filtered["elemento_despesa"].dropna().unique())

        if elemento_despesa and elemento_despesa not in elem_possiveis:
            elemento_despesa = ""
            st.session_state[elem_key] = ""

        with st.expander("🔍 Filtros de Insumos", expanded=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                # exibe combo de elem. despesa
                novo_elem = st.selectbox(
                    "Filtrar por elemento de despesa:",
                    options=[""] + elem_possiveis,
                    index=([""] + elem_possiveis).index(elemento_despesa)
                )
            with col_f2:
                # exibe combo de espec padrao
                novo_spec = st.selectbox(
                    "Filtrar por especificação padrão:",
                    options=[""] + espec_possiveis,
                    index=([""] + espec_possiveis).index(especificacao)
                )

        # se combos mudaram
        if (novo_elem != elemento_despesa) or (novo_spec != especificacao):
            st.session_state[elem_key] = novo_elem
            st.session_state[spec_key] = novo_spec
            st.rerun()

        # 2) Define o subset final do DF p/ exibir
        df_filter = df_all_insumos.copy()
        if st.session_state[elem_key]:
            df_filter = df_filter[df_filter["elemento_despesa"] == st.session_state[elem_key]]
        if st.session_state[spec_key]:
            df_filter = df_filter[df_filter["especificacao_padrao"] == st.session_state[spec_key]]

        # 3) Formulário p/ data_editor
        with st.form(f"form_insumos_{index_eixo}", clear_on_submit=False):
            st.write("**Selecione os insumos para cada ação**")

            for ac_id in novas_acoes:
                st.markdown(f"### Ação: {eixo['acoes_manejo'].get(ac_id, {}).get('nome_acao', acoes_opcoes.get(ac_id, '(sem nome)'))}")
                ac_data = eixo["acoes_manejo"].get(ac_id, {"insumos": [], "valor_ucs": {}})

                # 4) Pega insumos ja selecionados (mesmo que nao batam no filter)
                selecionados_ids = set(ac_data["insumos"])
                df_sel = df_all_insumos[df_all_insumos["id"].isin(selecionados_ids)]

                # 5) Unimos df_filter (batem no filtro) + df_sel (itens ja marcados)
                df_final = pd.concat([df_filter, df_sel]).drop_duplicates(subset=["id"])

                # 6) Marca col. Selecionado
                df_final["Selecionado"] = df_final["id"].apply(lambda x: x in selecionados_ids)

                # Remove colunas que não queremos exibir no data_editor
                cols_to_remove = ["elemento_despesa", "especificacao_padrao"]
                for c in cols_to_remove:
                    if c in df_final.columns:
                        df_final.drop(columns=[c], inplace=True)

                
                # Ajusta nomes de colunas
                df_final.rename(columns={
                    "id": "ID",
                    "descricao_insumo": "Insumo"
                }, inplace=True)

                edited_insumos = st.data_editor(
                    df_final,
                    column_config={
                        "ID": st.column_config.TextColumn(disabled=True),
                        "Insumo": st.column_config.TextColumn(disabled=True),
                        "Selecionado": st.column_config.CheckboxColumn("Selecionar")
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=f"editor_insumos_{ac_id}"
                )

                # 7) Lê as linhas marcadas
                insumos_selecionados = edited_insumos.loc[edited_insumos["Selecionado"], "ID"].tolist()
                ac_data["insumos"] = insumos_selecionados
                eixo["acoes_manejo"][ac_id] = ac_data

            submit_insumos = st.form_submit_button("Salvar Insumos")
            if submit_insumos:
                st.session_state["eixos_tematicos"][index_eixo] = eixo
                st.success("Insumos atualizados com sucesso!")
                st.toast("Insumos atualizados!")
                time.sleep(2)
                st.rerun()

    # Botão geral para sair
    if st.button("Fechar e Voltar", key=f"btn_fechar_{index_eixo}"):
        st.session_state.modal_fechado = True
        st.rerun()





# Main UI para Eixos
#col_sel_eixo, col_btn_eixo = st.columns([8,2])
#with col_sel_eixo:
novo_eixo_id = st.selectbox(
    "Escolha um Eixo (Processo SAMGe) para adicionar:",
    options=[None] + sorted(eixos_opcoes.keys(), key=lambda x: eixos_opcoes[x]),
    format_func=lambda x: eixos_opcoes.get(x, "Selecione..."),
    key="sel_novo_eixo"
    )
#with col_sel_eixo:
if st.button("➕ Adicionar Eixo Temático", key="btn_add_eixo"):
    if novo_eixo_id and novo_eixo_id not in [e["id_eixo"] for e in st.session_state["eixos_tematicos"]]:
        st.session_state["eixos_tematicos"].append({
            "id_eixo": novo_eixo_id,
            "nome_eixo": eixos_opcoes.get(novo_eixo_id, "Novo Eixo"),
            "acoes_manejo": {},
            "valor_ucs": {}
        })
        st.rerun()


for i, eixo in enumerate(st.session_state["eixos_tematicos"]):
    stats = calcular_estatisticas_eixo(eixo)
    with st.expander(f"📌 Eixo: {eixo['nome_eixo']}", expanded=False):
        col1, col2, col3 = st.columns(3)
        col1.metric("Ações", stats["acoes"])
        col2.metric("Insumos", stats["insumos"])
        col3.metric("Valor Total", f"R$ {stats['valor_total']:,.2f}")

        col_edit, col_del = st.columns(2)
        if col_edit.button("✏️ Editar", key=f"btn_edit_{i}"):
            st.session_state["modo_editar_eixo"] = i
            st.session_state.modal_fechado = False
            st.rerun()

        if col_del.button("🗑️ Excluir", key=f"btn_del_{i}"):
            # Remover o eixo corretamente do session_state
            st.session_state["eixos_tematicos"].pop(i)
            st.rerun()

modo_idx = st.session_state.get("modo_editar_eixo")
modal_fechado = st.session_state.get("modal_fechado", True)

# Verifica se há índice válido e se o modal não está fechado
if modo_idx is not None and not modal_fechado:
    if 0 <= modo_idx < len(st.session_state["eixos_tematicos"]):
        editar_eixo_dialog(modo_idx)
        st.stop()
    else:
        # Se o índice for inválido, podemos simplesmente resetar
        st.session_state["modo_editar_eixo"] = None

st.divider()
if st.button("💾 Salvar Cadastro", key="btn_salvar_geral"):
    salvar_dados_iniciativa(
        id_iniciativa=nova_iniciativa,
        usuario=cpf_usuario,
        objetivo_geral=st.session_state["objetivo_geral"],
        objetivos_especificos=st.session_state["objetivos_especificos"],
        eixos_tematicos=st.session_state["eixos_tematicos"]
    )
    st.success("✅ Cadastro atualizado com sucesso!")
    st.toast("Cadastro atualizado com sucesso!")
    st.session_state["modo_editar_eixo"] = None
    st.rerun()
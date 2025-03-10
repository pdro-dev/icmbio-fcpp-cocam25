import streamlit as st
import sqlite3
import pandas as pd
import os

# ------------------------------------------------------------------------
#           Configurações de Página e Verificação de Login
# ------------------------------------------------------------------------
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login.")
    st.stop()

# Exemplo: supondo que guardamos no session_state:
#   st.session_state["cpf"] = "000.000.000-00"
#   st.session_state["perfil"] = "cocam" ou "padrao"
usuario_cpf   = st.session_state.get("cpf", "000.000.000-00")
usuario_perfil = st.session_state.get("perfil", "padrao")

st.set_page_config(
    page_title="Gestão de Insumos",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

os.makedirs("database", exist_ok=True)
conn = sqlite3.connect("database/app_data.db", check_same_thread=False)
cursor = conn.cursor()

# ------------------------------------------------------------------------
#              Funções Auxiliares
# ------------------------------------------------------------------------
def get_distinct_elementos():
    cursor.execute("SELECT DISTINCT elemento_despesa FROM td_insumos ORDER BY elemento_despesa")
    rows = cursor.fetchall()
    return [row[0] for row in rows if row[0]]

def get_distinct_espec_padrao(elemento=None):
    if elemento:
        cursor.execute("""
            SELECT DISTINCT especificacao_padrao 
              FROM td_insumos 
             WHERE elemento_despesa = ? 
          ORDER BY especificacao_padrao
        """, (elemento,))
    else:
        cursor.execute("SELECT DISTINCT especificacao_padrao FROM td_insumos ORDER BY especificacao_padrao")
    rows = cursor.fetchall()
    return [row[0] for row in rows if row[0]]

def get_distinct_insumos(elemento=None, espec=None):
    query = "SELECT DISTINCT descricao_insumo FROM td_insumos WHERE 1=1"
    params = []
    if elemento:
        query += " AND elemento_despesa = ?"
        params.append(elemento)
    if espec:
        query += " AND especificacao_padrao = ?"
        params.append(espec)
    query += " ORDER BY descricao_insumo"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [row[0] for row in rows if row[0]]

def get_preco(elemento, espec, insumo):
    """
    Retorna o primeiro preço encontrado (se houver) 
    para o trio (elemento, espec_padrao, insumo) com situacao = 'ativo'.
    """
    query = """
        SELECT preco_referencia
          FROM td_insumos
         WHERE elemento_despesa = ?
           AND especificacao_padrao = ?
           AND descricao_insumo = ?
           AND situacao = 'ativo'
         ORDER BY id DESC
         LIMIT 1
    """
    cursor.execute(query, (elemento, espec, insumo))
    row = cursor.fetchone()
    if row:
        return row[0]
    return None

def check_existing_insumo(elemento, espec, insumo):
    """
    Verifica se já existe algum registro (em qualquer situacao)
    com a mesma combinação de (elemento, espec_padrao, insumo).
    Fazemos comparação case-insensitive com LOWER(...).
    """
    query = """
        SELECT COUNT(*) 
          FROM td_insumos
         WHERE LOWER(elemento_despesa) = ?
           AND LOWER(especificacao_padrao) = ?
           AND LOWER(descricao_insumo) = ?
    """
    cursor.execute(
        query,
        (elemento.lower(), espec.lower(), insumo.lower())
    )
    (count,) = cursor.fetchone()
    return count > 0  # Se count > 0, já existe

def insert_insumo(elemento, espec_padrao, nome_insumo, preco, origem, situacao, registrado_por):
    cursor.execute("""
        INSERT INTO td_insumos (
            elemento_despesa,
            especificacao_padrao,
            descricao_insumo,
            especificacao_tecnica,
            preco_referencia,
            origem,
            situacao,
            registrado_por
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        elemento or "",
        espec_padrao or "",
        nome_insumo or "",
        "",  # especificacao_tecnica pode ficar vazio
        preco or 0.0,
        origem,
        situacao,
        registrado_por
    ))
    conn.commit()

def update_insumo(insumo_id, elemento, espec_padrao, nome_insumo, espec_tecnica, preco, situacao):
    cursor.execute("""
        UPDATE td_insumos
           SET elemento_despesa = ?,
               especificacao_padrao = ?,
               descricao_insumo = ?,
               especificacao_tecnica = ?,
               preco_referencia = ?,
               situacao = ?
         WHERE id = ?
    """, (
        elemento,
        espec_padrao,
        nome_insumo,
        espec_tecnica,
        preco,
        situacao,
        insumo_id
    ))
    conn.commit()

def get_sugestoes_insumos(perfil):
    if perfil == "cocam":
        query = "SELECT * FROM td_insumos WHERE situacao = 'em análise' ORDER BY id DESC"
        df = pd.read_sql_query(query, conn)
    else:
        query = "SELECT * FROM td_insumos WHERE situacao = 'em análise' AND registrado_por = ? ORDER BY id DESC"
        df = pd.read_sql_query(query, conn, params=[usuario_cpf])
    return df

def get_insumos_ativos():
    query = "SELECT * FROM td_insumos WHERE situacao = 'ativo' ORDER BY id DESC"
    return pd.read_sql_query(query, conn)

def get_insumos_desativados():
    query = "SELECT * FROM td_insumos WHERE situacao = 'desativado' ORDER BY id DESC"
    return pd.read_sql_query(query, conn)


# ------------------------------------------------------------------------
#                 Interface - Cabeçalho
# ------------------------------------------------------------------------
st.subheader("Gestão de Insumos 🔧")
st.markdown("---")

# =============================================================================
# 1) DOIS FORMULÁRIOS LADO A LADO
#    - Formulário da ESQUERDA: inputs de texto (INSERIR NOVO INSUMO)
#    - Formulário da DIREITA: selectboxes (CONSULTAR INSUMO EXISTENTE)
# =============================================================================

col1, col2, col3 = st.columns([10, 0.1, 10])	

# ---------------------------------------------------------------------
# FORMULÁRIO 1 (ESQUERDA) - SUGERIR NOVO INSUMO (CAMPOS LIVRES)
# ---------------------------------------------------------------------
with col1:
    st.markdown("#### Formulário de Sugestão (campos livres)")

    with st.form(key="form_sugestao_texto_livre"):
        elemento_text = st.text_input("Elemento de Despesa (texto livre)").strip()
        espec_text = st.text_input("Especificação Padrão (texto livre)").strip()
        desc_insumo_text = st.text_input("Descrição do Insumo (texto livre)").strip()
        preco_input = st.number_input("Preço de Referência (R$)", min_value=0.0, step=0.5, value=0.0)

        submitted_livre = st.form_submit_button("Enviar Sugestão")
        if submitted_livre:
            if not elemento_text:
                st.error("O campo 'Elemento de Despesa' é obrigatório!")
            elif not espec_text:
                st.error("O campo 'Especificação Padrão' é obrigatório!")
            elif not desc_insumo_text:
                st.error("O campo 'Descrição do Insumo' é obrigatório!")
            else:
                # Antes de inserir, verifica se existe duplicado
                if check_existing_insumo(elemento_text, espec_text, desc_insumo_text):
                    st.warning("Já existe um item com essa combinação de Elemento, Especificação e Descrição!")
                else:
                    # origem = st.session_state["setor"] (se existir) ou "desconhecido"
                    user_setor = st.session_state.get("setor", "desconhecido")
                    insert_insumo(
                        elemento=elemento_text,
                        espec_padrao=espec_text,
                        nome_insumo=desc_insumo_text,
                        preco=preco_input,
                        origem=user_setor,
                        situacao="em análise",
                        registrado_por=usuario_cpf
                    )
                    st.success("Sugestão adicionada com sucesso!")
                    st.rerun()

with col2:
    # Se precisar de algum espaçamento ou conteúdo mínimo
    st.write("") # Pode ser um espaço em branco ou texto

# ---------------------------------------------------------------------
# FORMULÁRIO 2 (DIREITA) - CONSULTAR ITENS (SELECTBOX COM FILTROS)
# ---------------------------------------------------------------------
with col3:
   
    st.markdown("##### Consulta de Itens Existentes")

    elemento_sel = st.selectbox(
        "Elemento de Despesa",
        options=[""] + get_distinct_elementos(),
        help="Selecione para filtrar as próximas opções."
    )

    if elemento_sel:
        especs = get_distinct_espec_padrao(elemento_sel)
    else:
        especs = []

    espec_sel = st.selectbox(
        "Especificação Padrão",
        options=[""] + especs,
        help="Filtra o campo seguinte."
    )

    if espec_sel:
        insumos = get_distinct_insumos(elemento_sel, espec_sel)
    else:
        insumos = []

    insumo_sel = st.selectbox(
        "Descrição do Insumo",
        options=[""] + insumos,
        help="Selecione para ver o preço (se ativo)."
    )

    # Exibindo o preço do item selecionado (se existir e estiver ativo)
    if elemento_sel and espec_sel and insumo_sel:
        preco_encontrado = get_preco(elemento_sel, espec_sel, insumo_sel)
        if preco_encontrado is not None:
            st.info(f"Preço de Referência (Ativo): R$ {preco_encontrado:,.2f}")
        else:
            st.warning("Não há preço ativo cadastrado para esta combinação.")
    else:
        st.write("Selecione todos os campos para consultar preço.")

st.markdown("---")


# =============================================================================
# 2) Tabela de Itens Sugeridos (situacao = 'em análise')
# =============================================================================
st.markdown("#### Itens Sugeridos (Em Análise)")

df_sugestoes = get_sugestoes_insumos(usuario_perfil)

if df_sugestoes.empty:
    st.info("Não há itens sugeridos em análise no momento.")
else:
    if usuario_perfil in ["cocam", "admin"]:
        col_config_sug = {
            "situacao": st.column_config.SelectboxColumn(
                "Situação",
                width="small",
                options=["em análise", "ativo", "desativado"]
            ),
        }
    else:
        col_config_sug = {
            "id": st.column_config.TextColumn("ID", disabled=True),
            "elemento_despesa": st.column_config.TextColumn("Elemento de Despesa", disabled=False),
            "especificacao_padrao": st.column_config.TextColumn("Especificação Padrão", disabled=False),
            "descricao_insumo": st.column_config.TextColumn("Nome do Insumo", disabled=False),
            "situacao": st.column_config.TextColumn("Situação", disabled=True),
            "origem": st.column_config.TextColumn("Origem", disabled=True),
            "registrado_por": st.column_config.TextColumn("Registrado Por", disabled=True),
        }

    # Configuração de preço formatado
    col_config_sug["preco_referencia"] = st.column_config.NumberColumn(
        "Preço de Referência",
        format="localized",
        disabled=False
    )

    df_sugestoes = df_sugestoes[[
        "id", "elemento_despesa", "especificacao_padrao",
        "descricao_insumo", "preco_referencia", "origem",
        "situacao", "registrado_por"
    ]]

    edited_df_sug = st.data_editor(
        df_sugestoes,
        column_config=col_config_sug,
        use_container_width=True,
        hide_index=True,
        key="editor_sugestoes"
    )

    if st.button("Salvar Alterações em Itens Sugeridos"):
        for index, row in edited_df_sug.iterrows():
            update_insumo(
                insumo_id=row["id"],
                elemento=row["elemento_despesa"],
                espec_padrao=row["especificacao_padrao"],
                nome_insumo=row["descricao_insumo"],
                espec_tecnica="",
                preco=row["preco_referencia"],
                situacao=row["situacao"]
            )
        st.success("Sugestões atualizadas com sucesso!")
        st.rerun()

st.markdown("---")


# =============================================================================
# 3) Tabela de Itens Ativos (Edição de 'Situação' apenas para cocam/admin)
# =============================================================================
st.markdown("#### Itens Ativos")

df_ativos = get_insumos_ativos()
df_ativos = df_ativos[[
    "id", "elemento_despesa", "especificacao_padrao", "descricao_insumo",
    "preco_referencia", "origem", "situacao", "registrado_por"
]]

if df_ativos.empty:
    st.info("Não há itens ativos no momento.")
else:
    col_config_ativos = {
        "id": st.column_config.TextColumn("ID", disabled=True),
        "elemento_despesa": st.column_config.TextColumn("Elemento de Despesa", disabled=True),
        "especificacao_padrao": st.column_config.TextColumn("Especificação Padrão", disabled=True),
        "descricao_insumo": st.column_config.TextColumn("Nome do Insumo", disabled=True),
        "preco_referencia": st.column_config.NumberColumn(
            "Preço de Referência",
            format="localized",
            disabled=False
        ),
        "origem": st.column_config.TextColumn("Origem", disabled=True),
        "registrado_por": st.column_config.TextColumn("Registrado Por", disabled=True),
    }

    if usuario_perfil in ["cocam", "admin"]:
        col_config_ativos["situacao"] = st.column_config.SelectboxColumn(
            "Situação",
            width="small",
            options=["em análise", "ativo", "desativado"]
        )
    else:
        col_config_ativos["situacao"] = st.column_config.TextColumn("Situação", disabled=True)

    edited_df_ativos = st.data_editor(
        df_ativos,
        column_config=col_config_ativos,
        use_container_width=True,
        hide_index=True,
        key="editor_ativos"
    )

    if usuario_perfil in ["cocam", "admin"]:
        if st.button("Salvar Alterações em Itens Ativos"):
            for index, row in edited_df_ativos.iterrows():
                update_insumo(
                    insumo_id=row["id"],
                    elemento=row["elemento_despesa"],
                    espec_padrao=row["especificacao_padrao"],
                    nome_insumo=row["descricao_insumo"],
                    espec_tecnica="",
                    preco=row["preco_referencia"],
                    situacao=row["situacao"]
                )
            st.success("Itens ativos atualizados com sucesso!")
            st.rerun()

st.markdown("---")


# =============================================================================
# 4) Expander com Itens Desativados
# =============================================================================
with st.expander("Itens Desativados"):
    df_desativados = get_insumos_desativados()
    if df_desativados.empty:
        st.info("Não há itens desativados no momento.")
    else:
        # Adiciona a coluna "excluir" ao DataFrame apenas em memória
        # para controlar a remoção
        if usuario_perfil in ["cocam", "admin"]:
            # Cria a coluna 'excluir' com valor False por padrão
            df_desativados["excluir"] = False  
        # Caso queira que outros perfis vejam a coluna, mas sem poder marcar,
        # você poderia também criar df_desativados["excluir"] = False
        # e exibir como disabled. Depende da sua regra de negócio.

        # Mantemos as mesmas colunas de exibição + a nova "excluir" se for cocam/admin
        cols_to_show = [
            "id", "elemento_despesa", "especificacao_padrao", "descricao_insumo",
            "preco_referencia", "origem", "situacao", "registrado_por"
        ]
        if "excluir" in df_desativados.columns:
            cols_to_show.append("excluir")

        df_desativados = df_desativados[cols_to_show]

        # Configuração das colunas
        if usuario_perfil in ["cocam", "admin"]:
            col_config_des = {
                "situacao": st.column_config.SelectboxColumn(
                    "Situação",
                    width="small",
                    options=["em análise", "ativo", "desativado"]
                ),
                "preco_referencia": st.column_config.NumberColumn(
                    "Preço de Referência",
                    format="localized",
                    disabled=True
                ),
                # Nova coluna para exclusão
                "excluir": st.column_config.CheckboxColumn(
                    "Excluir?",
                    help="Marque para excluir este registro.",
                    disabled=False
                )
            }
        else:
            # Perfil que não pode excluir nem alterar situação
            col_config_des = {
                "id": st.column_config.TextColumn("ID", disabled=True),
                "elemento_despesa": st.column_config.TextColumn("Elemento de Despesa", disabled=True),
                "especificacao_padrao": st.column_config.TextColumn("Especificação Padrão", disabled=True),
                "descricao_insumo": st.column_config.TextColumn("Nome do Insumo", disabled=True),
                "preco_referencia": st.column_config.NumberColumn(
                    "Preço de Referência",
                    format="localized",
                    disabled=True
                ),
                "origem": st.column_config.TextColumn("Origem", disabled=True),
                "situacao": st.column_config.TextColumn("Situação", disabled=True),
                "registrado_por": st.column_config.TextColumn("Registrado Por", disabled=True),
            }
            # Se quiser que "excluir" apareça mesmo para não-admin, mas travada:
            # col_config_des["excluir"] = st.column_config.CheckboxColumn(
            #     "Excluir?",
            #     disabled=True
            # )

        edited_df_des = st.data_editor(
            df_desativados,
            column_config=col_config_des,
            use_container_width=True,
            hide_index=True,
            key="editor_desativados"
        )

        # Apenas perfis com permissão podem salvar alterações
        if usuario_perfil in ["cocam", "admin"]:
            if st.button("Salvar Alterações nos Itens Desativados"):
                for index, row in edited_df_des.iterrows():
                    # Se o usuário marcou "excluir", removemos do banco de dados
                    if "excluir" in row and row["excluir"]:
                        cursor.execute("DELETE FROM td_insumos WHERE id = ?", (row["id"],))
                        conn.commit()
                    else:
                        # Caso contrário, apenas atualizamos a situação (e outros campos se desejar)
                        update_insumo(
                            insumo_id=row["id"],
                            elemento=row["elemento_despesa"],
                            espec_padrao=row["especificacao_padrao"],
                            nome_insumo=row["descricao_insumo"],
                            espec_tecnica="",
                            preco=row["preco_referencia"],
                            situacao=row["situacao"]
                        )
                st.success("Itens desativados atualizados com sucesso!")
                st.rerun()

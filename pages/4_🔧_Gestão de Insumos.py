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

def get_distinct_espec_padrao():
    cursor.execute("SELECT DISTINCT especificacao_padrao FROM td_insumos ORDER BY especificacao_padrao")
    rows = cursor.fetchall()
    return [row[0] for row in rows if row[0]]

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
        elemento,
        espec_padrao,
        nome_insumo or "",
        "",  # especificacao_tecnica pode ficar vazio por enquanto
        preco or 0.0,
        origem,
        situacao,
        registrado_por
    ))
    conn.commit()

def update_insumo(insumo_id, elemento, espec_padrao, nome_insumo, espec_tecnica, preco, situacao):
    """
    Atualiza o insumo no banco.
    """
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
    """
    Retorna DataFrame com insumos em 'em análise'.
    Se perfil != 'cocam', podemos filtrar apenas os registrados pelo usuário.
    """
    if perfil == "cocam":
        query = "SELECT * FROM td_insumos WHERE situacao = 'em análise' ORDER BY id DESC"
        df = pd.read_sql_query(query, conn)
    else:
        # usuário normal enxerga apenas os insumos dele com situacao = em análise
        query = "SELECT * FROM td_insumos WHERE situacao = 'em análise' AND registrado_por = ? ORDER BY id DESC"
        df = pd.read_sql_query(query, conn, params=[usuario_cpf])
    return df

def get_insumos_ativos():
    """
    Retorna DataFrame com insumos 'ativo'.
    """
    query = "SELECT * FROM td_insumos WHERE situacao = 'ativo' ORDER BY id DESC"
    return pd.read_sql_query(query, conn)

# ------------------------------------------------------------------------
#                 Interface - Cabeçalho
# ------------------------------------------------------------------------
st.subheader("Gestão de Insumos 🔧")
st.markdown("---")

# =============================================================================
# 1) Formulário para Inserir Novo Insumo (Sugestão)
# =============================================================================
st.markdown("#### Adicionar Novo Insumo (Sugestão)")
with st.form(key="add_insumo_form"):
    elementos = get_distinct_elementos()
    selected_elemento = st.selectbox("Elemento de Despesa", [""] + elementos)
    especs = get_distinct_espec_padrao()
    selected_espec = st.selectbox("Especificação Padrão", [""] + especs)
    nome_insumo = st.text_input("Nome do Insumo (opcional)")
    preco = st.number_input("Preço de Referência (R$)", min_value=0.0, step=0.01, value=0.0)

    submitted = st.form_submit_button("Enviar Sugestão")
    if submitted:
        if not selected_elemento:
            st.error("O campo 'Elemento de Despesa' é obrigatório!")
        elif not selected_espec:
            st.error("O campo 'Especificação Padrão' é obrigatório!")
        else:
            # Quando for novo item sugerido:
            #   origem = st.session_state["setor"], p.ex.
            #   situacao = 'em análise'
            #   registrado_por = st.session_state["cpf"]
            user_setor = st.session_state.get("setor", "desconhecido")
            insert_insumo(
                elemento=selected_elemento,
                espec_padrao=selected_espec,
                nome_insumo=nome_insumo,
                preco=preco,
                origem=user_setor,
                situacao="em análise",
                registrado_por=usuario_cpf
            )
            st.success("Sugestão adicionada com sucesso!")
            st.rerun()

st.markdown("---")

# =============================================================================
# 2) Tabela de Itens Sugeridos (situacao = 'em análise')
# =============================================================================
st.markdown("#### Itens Sugeridos (Em Análise)")

df_sugestoes = get_sugestoes_insumos(usuario_perfil)

if df_sugestoes.empty:
    st.info("Não há itens sugeridos em análise no momento.")
else:
    # Se o usuário for 'cocam', permitimos que ele edite a coluna situacao.
    # Senão, deixamos 'situacao' desabilitada.
    if usuario_perfil == "cocam":
        col_config = {
            "situacao": st.column_config.SelectboxColumn(
                "Situação",
                width="small",
                options=["em análise", "ativo", "desativado"]
            )
        }
        # (Opcional) Você pode desabilitar a edição de outras colunas que não devem ser alteradas
        # ex: "origem": st.column_config.TextColumn("Origem", disabled=True)
    else:
        col_config = {
            "id": st.column_config.TextColumn("ID", disabled=True),
            "elemento_despesa": st.column_config.TextColumn("Elemento de Despesa", disabled=False),
            "especificacao_padrao": st.column_config.TextColumn("Especificação Padrão", disabled=False),
            "descricao_insumo": st.column_config.TextColumn("Nome do Insumo", disabled=False),
            "especificacao_tecnica": st.column_config.TextColumn("Especificação Técnica", disabled=False),
            "preco_referencia": st.column_config.NumberColumn("Preço de Referência", disabled=False),
            "origem": st.column_config.TextColumn("Origem", disabled=True),
            "situacao": st.column_config.TextColumn("Situação", disabled=True),
            "registrado_por": st.column_config.TextColumn("Registrado Por", disabled=True)      
        }

    edited_df_sug = st.data_editor(
        df_sugestoes,
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
        key="editor_sugestoes"
    )

    if st.button("Salvar Alterações em Itens Sugeridos"):
        # Percorre as linhas editadas e atualiza no banco
        for index, row in edited_df_sug.iterrows():
            update_insumo(
                insumo_id=row["id"],
                elemento=row["elemento_despesa"],
                espec_padrao=row["especificacao_padrao"],
                nome_insumo=row["descricao_insumo"],
                espec_tecnica=row["especificacao_tecnica"],
                preco=row["preco_referencia"],
                situacao=row["situacao"]
            )
        st.success("Sugestões atualizadas com sucesso!")
        st.rerun()

st.markdown("---")

# =============================================================================
# 3) Tabela de Itens Ativos (Somente Leitura ou Edição Limitada)
# =============================================================================
st.markdown("#### Itens Ativos")

df_ativos = get_insumos_ativos()
if df_ativos.empty:
    st.info("Não há itens ativos no momento.")
else:
    # Exibimos read-only
    edited_df_ativos = st.data_editor(
        df_ativos,
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True),
            "elemento_despesa": st.column_config.TextColumn("Elemento de Despesa", disabled=True),
            "especificacao_padrao": st.column_config.TextColumn("Especificação Padrão", disabled=True),
            "descricao_insumo": st.column_config.TextColumn("Nome do Insumo", disabled=True),
            "especificacao_tecnica": st.column_config.TextColumn("Especificação Técnica", disabled=True),
            "preco_referencia": st.column_config.NumberColumn("Preço de Referência", disabled=True),
            "origem": st.column_config.TextColumn("Origem", disabled=True),
            "situacao": st.column_config.TextColumn("Situação", disabled=True),
            "registrado_por": st.column_config.TextColumn("Registrado Por", disabled=True),
        },
        use_container_width=True,
        hide_index=True,
        key="editor_ativos"
    )

    # Se quiser permitir que 'cocam' edite mesmo os ativos, basta mudar
    # as colunas para não disabled. Mas, normalmente, itens ativos ficam read-only.

# st.write("© 2025 Gestão de Insumos")

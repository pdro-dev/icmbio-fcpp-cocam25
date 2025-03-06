import streamlit as st
import sqlite3
import pandas as pd
import os

# -----------------------------------------------------------------------------
#                     Verificação de Login e Configurações de Página
# -----------------------------------------------------------------------------
if "usuario_logado" not in st.session_state or not st.session_state["usuario_logado"]:
    st.warning("🔒 Acesso negado! Faça login.")
    st.stop()

# configurar o tema do Streamlit
st.set_page_config(
    page_title="Gestão de Insumos",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Criar diretório para o banco de dados, se necessário
os.makedirs("database", exist_ok=True)

# Conexão com o banco de dados SQLite
conn = sqlite3.connect("database/app_data.db", check_same_thread=False)
cursor = conn.cursor()

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================
def get_distinct_elementos():
    cursor.execute("SELECT DISTINCT elemento_despesa FROM td_insumos ORDER BY elemento_despesa")
    rows = cursor.fetchall()
    return [row[0] for row in rows if row[0]]

def get_distinct_espec_padrao():
    cursor.execute("SELECT DISTINCT especificacao_padrao FROM td_insumos ORDER BY especificacao_padrao")
    rows = cursor.fetchall()
    return [row[0] for row in rows if row[0]]

def insert_insumo(elemento, espec_padrao, nome_insumo, preco):
    cursor.execute("""
        INSERT INTO td_insumos (
            elemento_despesa,
            especificacao_padrao,
            descricao_insumo,
            especificacao_tecnica,
            preco_referencia
        ) VALUES (?, ?, ?, ?, ?)
    """, (elemento, espec_padrao, nome_insumo or "", "", preco or 0.0))
    conn.commit()

def get_all_insumos():
    query = """
        SELECT * FROM td_insumos
        ORDER BY id DESC
    """
    return pd.read_sql_query(query, conn)

def update_insumo(insumo_id, elemento, espec_padrao, nome_insumo, espec_tecnica, preco):
    cursor.execute("""
        UPDATE td_insumos
        SET elemento_despesa = ?, especificacao_padrao = ?, descricao_insumo = ?, especificacao_tecnica = ?, preco_referencia = ?
        WHERE id = ?
    """, (elemento, espec_padrao, nome_insumo, espec_tecnica, preco, insumo_id))
    conn.commit()

# =============================================================================
# INTERFACE STREAMLIT
# =============================================================================
st.subheader("Gestão de Insumos 🔧")  # Título da página

st.markdown("---")  

# --- Seção para Adicionar Novo Insumo ---
st.markdown("##### Adicionar Novo Insumo")
with st.form(key="add_insumo_form" ):
    
    elementos = get_distinct_elementos()
    selected_elemento = st.selectbox("Elemento de Despesa", elementos)
    especs = get_distinct_espec_padrao()
    selected_espec = st.selectbox("Especificação Padrão", especs)
    nome_insumo = st.text_input("Nome do Insumo (opcional)")
    preco = st.number_input("Preço de Referência (R$)", min_value=0.0, step=0.01, value=0.0)

    submitted = st.form_submit_button("Adicionar Insumo")
    if submitted:
        if not selected_elemento:
            st.error("O campo 'Elemento de Despesa' é obrigatório!")
        elif not selected_espec:
            st.error("O campo 'Especificação Padrão' é obrigatório!")
        else:
            insert_insumo(selected_elemento, selected_espec, nome_insumo, preco)
            st.success(f"Insumo adicionado com sucesso!")
            st.rerun()


st.markdown("---")

# --- Seção para Edição dos Insumos ---
st.markdown("##### Tabela de Insumos Cadastrados") 
df = get_all_insumos()
if df.empty:
    st.info("Nenhum insumo cadastrado.")
else:
    edited_df = st.data_editor(
        data=df,
        key="insumos_editor"
    )
    
    if st.button("Salvar Alterações"):
        for _, row in edited_df.iterrows():
            update_insumo(
                row["id"], row["elemento_despesa"], row["especificacao_padrao"],
                row["descricao_insumo"], row["especificacao_tecnica"], row["preco_referencia"]
            )
        st.success("Alterações salvas com sucesso!")
        st.rerun()

st.write("© 2025 Gestão de Insumos")

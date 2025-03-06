import streamlit as st
import sqlite3
import pandas as pd
import os

# Conexão com o banco de dados.
conn = sqlite3.connect("database/app_data.db", check_same_thread=False)
cursor = conn.cursor()

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------
def get_distinct_elementos():
    """Retorna todos os valores distintos de elemento_despesa em td_insumos."""
    cursor.execute("SELECT DISTINCT elemento_despesa FROM td_insumos ORDER BY elemento_despesa")
    rows = cursor.fetchall()
    return [row[0] for row in rows if row[0]]

def get_distinct_espec_padrao():
    """Retorna todos os valores distintos de especificacao_padrao em td_insumos."""
    cursor.execute("SELECT DISTINCT especificacao_padrao FROM td_insumos ORDER BY especificacao_padrao")
    rows = cursor.fetchall()
    return [row[0] for row in rows if row[0]]

def insert_insumo(elemento, espec_padrao, desc, espec_tec, preco):
    """Insere um novo insumo na tabela td_insumos."""
    cursor.execute("""
        INSERT INTO td_insumos (
            elemento_despesa,
            especificacao_padrao,
            descricao_insumo,
            especificacao_tecnica,
            preco_referencia
        ) VALUES (?, ?, ?, ?, ?)
    """, (elemento, espec_padrao, desc, espec_tec, preco))
    conn.commit()

def get_all_insumos():
    """Retorna todos os insumos cadastrados como DataFrame."""
    query = """
        SELECT
            id,
            elemento_despesa,
            especificacao_padrao,
            descricao_insumo,
            especificacao_tecnica,
            preco_referencia
        FROM td_insumos
        ORDER BY id DESC
    """
    return pd.read_sql_query(query, conn)

def delete_insumo(insumo_id):
    """Exclui um insumo pelo ID."""
    cursor.execute("DELETE FROM td_insumos WHERE id = ?", (insumo_id,))
    conn.commit()

def update_insumo(insumo_id, elemento, espec_padrao, desc, espec_tec, preco):
    """Atualiza os campos de um insumo específico."""
    cursor.execute("""
        UPDATE td_insumos
        SET
            elemento_despesa = ?,
            especificacao_padrao = ?,
            descricao_insumo = ?,
            especificacao_tecnica = ?,
            preco_referencia = ?
        WHERE id = ?
    """, (elemento, espec_padrao, desc, espec_tec, preco, insumo_id))
    conn.commit()

# -----------------------------------------------------------------------------
# INTERFACE STREAMLIT
# -----------------------------------------------------------------------------
st.title("Gestão de Insumos")
st.write("Bem-vindo à página de gestão de insumos. Aqui você pode gerenciar todos os insumos necessários para o seu projeto.")

# Seção para adicionar um novo insumo (formulário complementar)
st.header("Adicionar Novo Insumo")

with st.form(key="add_insumo_form"):
    # Permite escolher ou criar um novo "Elemento de Despesa"
    elementos_existentes = get_distinct_elementos()
    selected_elemento = st.selectbox("Elemento de Despesa", ["<Novo>"] + elementos_existentes)
    if selected_elemento == "<Novo>":
        elemento_despesa = st.text_input("Digite o novo Elemento de Despesa")
    else:
        elemento_despesa = selected_elemento

    # Permite escolher ou criar uma nova "Especificação Padrão"
    espec_padrao_existentes = get_distinct_espec_padrao()
    selected_espec = st.selectbox("Especificação Padrão", ["<Novo>"] + espec_padrao_existentes)
    if selected_espec == "<Novo>":
        espec_padrao = st.text_input("Digite a nova Especificação Padrão")
    else:
        espec_padrao = selected_espec

    descricao_insumo = st.text_input("Descrição do Insumo")
    especificacao_tecnica = st.text_area("Especificação Técnica (detalhamento)")
    preco_referencia = st.number_input("Preço de Referência (R$)", min_value=0.0, step=0.01)

    submitted_add = st.form_submit_button("Adicionar Insumo")

    if submitted_add:
        if not elemento_despesa:
            st.error("É necessário informar o Elemento de Despesa!")
        else:
            insert_insumo(
                elemento_despesa,
                espec_padrao,
                descricao_insumo,
                especificacao_tecnica,
                preco_referencia
            )
            st.success(f"Insumo '{descricao_insumo}' adicionado com sucesso!")
            st.rerun()

# Seção de edição via DataFrame
st.header("Editar Insumos (DataFrame)")

# Carrega os insumos atuais
df_original = get_all_insumos()

if df_original.empty:
    st.info("Nenhum insumo cadastrado ainda.")
else:
    # Exibe o DataFrame em modo edição, permitindo inserção/remoção de linhas
    edited_df = st.data_editor(
        "Edite os insumos abaixo:",
        df_original,
        num_rows="dynamic",
        key="insumos_editor"
    )

    # Botão para salvar alterações
    if st.button("Salvar Alterações"):
        # Converte a coluna 'id' para numérica, onde possível
        df_edited = edited_df.copy()
        df_edited["id"] = pd.to_numeric(df_edited["id"], errors="coerce")

        # Identifica os IDs originais e os IDs presentes após edição
        original_ids = set(df_original["id"].dropna().astype(int))
        edited_ids = set(df_edited["id"].dropna().astype(int))
        
        # Exclusões: IDs que foram removidos no editor
        deleted_ids = original_ids - edited_ids
        for insumo_id in deleted_ids:
            delete_insumo(insumo_id)
        
        # Atualizações e Inserções:
        for _, row in df_edited.iterrows():
            # Se o valor de 'id' for NaN, trata-se de um novo insumo
            if pd.isna(row["id"]):
                insert_insumo(
                    row["elemento_despesa"],
                    row["especificacao_padrao"],
                    row["descricao_insumo"],
                    row["especificacao_tecnica"],
                    row["preco_referencia"]
                )
            else:
                update_insumo(
                    int(row["id"]),
                    row["elemento_despesa"],
                    row["especificacao_padrao"],
                    row["descricao_insumo"],
                    row["especificacao_tecnica"],
                    row["preco_referencia"]
                )
        st.success("Alterações salvas com sucesso!")
        st.rerun()

# Rodapé
st.write("© 2025 Gestão de Insumos")

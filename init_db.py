import json
import numpy as np
import pandas as pd
import sqlite3
import os

def init_database():
    # 📌 Caminhos dos arquivos de dados e do banco
    json_path = "dados/base_iniciativas_consolidada.json"
    excel_path = "dados/base_iniciativas_resumos_sei.xlsx"
    db_path = "database/app_data.db"

    # 📌 Criando diretório do banco de dados se não existir
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()


    # 📌 Criar tabela de usuários
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tf_usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf TEXT UNIQUE NOT NULL,
            nome_completo TEXT NOT NULL,
            email TEXT NOT NULL,
            setor_demandante TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'comum' -- Pode ser 'comum' ou 'admin'
        )
    """)

    # 📌 Criando um usuário "admin master" caso não exista
    cursor.execute("""
        INSERT OR IGNORE INTO tf_usuarios (cpf, nome_completo, email, setor_demandante, perfil)
        VALUES ({ADMIN_CPF},{ADMIN_NOME},{ADMIN_EMAIL},{ADMIN_SETOR},{ADMIN_PERFIL})
    """)


    # 📌 Carregando dados do JSON (dados base fixos)
    df_base = pd.read_json(json_path)

    # 📌 Tratamento da coluna "Nº SEI"
    df_base["Nº SEI"] = df_base["Nº SEI"].astype(str).replace("-", np.nan)
    df_base["Nº SEI"] = pd.to_numeric(df_base["Nº SEI"], errors="coerce")

    # 📌 Seleção das colunas desejadas
    colunas_base = [
        "DEMANDANTE",
        "Nome da Proposta/Iniciativa Estruturante",
        "Unidade de Conservação",
        "Observações",
        "VALOR TOTAL ALOCADO",
        "Valor da Iniciativa (R$)",
        "Valor Total da Iniciativa",
        "SALDO",
        "Nº SEI",
        "AÇÃO DE APLICAÇÃO",
        "CATEGORIA UC",
        "CNUC",
        "GR",
        "BIOMA",
        "UF"
    ]
    
    df_base = df_base[colunas_base]

    # 📌 Criando a tabela fixa `td_dados_base_iniciativas` (somente consulta)
    df_base.to_sql("td_dados_base_iniciativas", conn, if_exists="replace", index=False)

    # 📌 Carregando os dados do Excel a partir da Planilha1
    df_resumos = pd.read_excel(excel_path, sheet_name="Planilha1", engine="openpyxl")

    # 📌 Removendo possíveis linhas completamente vazias
    df_resumos.dropna(how="all", inplace=True)

    # 📌 Padronizando os nomes das colunas (removendo espaços e convertendo para minúsculas)
    df_resumos.columns = [col.strip().lower().replace(" ", "_") for col in df_resumos.columns]



    # 📌 Criar a tabela no banco de dados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_dados_resumos_sei (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diretoria TEXT,
            coordenacao_geral TEXT,
            coordenacao TEXT,
            demandante TEXT,
            iniciativa TEXT,
            introducao TEXT,
            justificativa TEXT,
            objetivo_geral TEXT,
            unidades_conservacao TEXT,
            metodologia TEXT
        )
    """)

    conn.commit()

    # 📌 Criando a tabela `td_dados_resumos_sei`
    df_resumos.to_sql("td_dados_resumos_sei", conn, if_exists="replace", index=False)

    # 📌 Criando tabelas dimensão para armazenar IDs únicos
    cursor.execute("CREATE TABLE IF NOT EXISTS td_demandantes (id_demandante INTEGER PRIMARY KEY AUTOINCREMENT, nome_demandante TEXT UNIQUE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS td_iniciativas (id_iniciativa INTEGER PRIMARY KEY AUTOINCREMENT, nome_iniciativa TEXT UNIQUE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS td_acoes_aplicacao (id_acao INTEGER PRIMARY KEY AUTOINCREMENT, nome_acao TEXT UNIQUE)")

    # 📌 Criando `td_unidades` com `CNUC` como chave primária
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_unidades (
            cnuc TEXT PRIMARY KEY,
            nome_unidade TEXT,
            gr TEXT,
            categoria_uc TEXT,
            bioma TEXT,
            uf TEXT
        )
    """)

    # 📌 Criando a tabela fato `tf_cadastros_iniciativas`
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tf_cadastros_iniciativas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_demandante INTEGER,
            id_iniciativa INTEGER,
            id_acao INTEGER,
            cnuc TEXT,
            id_composto TEXT UNIQUE,
            observacoes TEXT,
            saldo REAL,
            valor_total_alocado REAL,
            valor_iniciativa REAL,
            valor_total_iniciativa REAL,
            num_sei TEXT,
            FOREIGN KEY (id_demandante) REFERENCES td_demandantes(id_demandante),
            FOREIGN KEY (id_iniciativa) REFERENCES td_iniciativas(id_iniciativa),
            FOREIGN KEY (id_acao) REFERENCES td_acoes_aplicacao(id_acao),
            FOREIGN KEY (cnuc) REFERENCES td_unidades(cnuc)
        )
    """)

    conn.commit()

    # 📌 Inserindo valores únicos nas tabelas dimensão
    for table, column, name_col in [
        ("td_demandantes", "DEMANDANTE", "nome_demandante"), 
        ("td_iniciativas", "Nome da Proposta/Iniciativa Estruturante", "nome_iniciativa"), 
        ("td_acoes_aplicacao", "AÇÃO DE APLICAÇÃO", "nome_acao")
    ]:
        unique_values = df_base[column].dropna().unique()
        for value in unique_values:
            cursor.execute(f"INSERT OR IGNORE INTO {table} ({name_col}) VALUES (?)", (value,))

    # 📌 Preenchendo `td_unidades`
    unidades_unicas = df_base[["CNUC", "Unidade de Conservação", "GR", "CATEGORIA UC", "BIOMA", "UF"]].drop_duplicates()
    for _, row in unidades_unicas.iterrows():
        cursor.execute("""
            INSERT OR IGNORE INTO td_unidades (cnuc, nome_unidade, gr, categoria_uc, bioma, uf) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (row["CNUC"], row["Unidade de Conservação"], row["GR"], row["CATEGORIA UC"], row["BIOMA"], row["UF"]))

    conn.commit()

    # 📌 Criando mapeamento de IDs para referência
    id_maps = {}
    for table, column, id_col, name_col in [
        ("td_demandantes", "DEMANDANTE", "id_demandante", "nome_demandante"), 
        ("td_iniciativas", "Nome da Proposta/Iniciativa Estruturante", "id_iniciativa", "nome_iniciativa"), 
        ("td_acoes_aplicacao", "AÇÃO DE APLICAÇÃO", "id_acao", "nome_acao")
    ]:
        id_maps[table] = pd.read_sql_query(f"SELECT * FROM {table}", conn).set_index(name_col)[id_col].to_dict()

    # 📌 Criando `tf_cadastros_iniciativas` com IDs e um ID único composto
    df_base["id_demandante"] = df_base["DEMANDANTE"].map(id_maps["td_demandantes"]).fillna(-1)
    df_base["id_iniciativa"] = df_base["Nome da Proposta/Iniciativa Estruturante"].map(id_maps["td_iniciativas"]).fillna(-1)
    df_base["id_acao"] = df_base["AÇÃO DE APLICAÇÃO"].map(id_maps["td_acoes_aplicacao"]).fillna(-1)

    df_base.to_sql("tf_cadastros_iniciativas", conn, if_exists="replace", index=False)

    conn.close()
    print("✅ Banco de dados inicializado com sucesso!")

if __name__ == "__main__":
    init_database()

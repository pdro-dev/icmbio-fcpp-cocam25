import json
import numpy as np
import pandas as pd
import sqlite3
import os
import streamlit as st


def init_database():
    # 📌 Caminhos dos arquivos de dados e do banco
    json_path = "dados/base_iniciativas_consolidada.json"
    excel_path = "dados/base_iniciativas_resumos_sei.xlsx"
    db_path = "database/app_data.db"

    # Credenciais do usuário admin (vêm do [Secrets] do Streamlit)
    admin_cpf = st.secrets["ADMIN_CPF"]
    admin_nome = st.secrets["ADMIN_NOME"]
    admin_email = st.secrets["ADMIN_EMAIL"]
    admin_setor = st.secrets["ADMIN_SETOR"]
    admin_perfil = st.secrets["ADMIN_PERFIL"]

    # 📌 Criando diretório do banco de dados se não existir
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ----------------------------------------------------------------------------
    # 1) TABELA DE USUÁRIOS
    # ----------------------------------------------------------------------------
    cursor.execute(""" DROP TABLE IF EXISTS tf_usuarios """)
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

    # Cria (ou ignora) um usuário admin master
    cursor.execute("""
        INSERT OR IGNORE INTO tf_usuarios (cpf, nome_completo, email, setor_demandante, perfil)
        VALUES (?, ?, ?, ?, ?)
    """, (admin_cpf, admin_nome, admin_email, admin_setor, admin_perfil))

    # Cria (ou ignora) um usuário com perfil cocam
    cursor.execute("""
        INSERT OR IGNORE INTO tf_usuarios (cpf, nome_completo, email, setor_demandante, perfil)
        VALUES (?, ?, ?, ?, ?)
    """, ("11111111111", "COCAM", " ", "COCAM", "cocam"))


    # ----------------------------------------------------------------------------
    # 2) LEITURA DA BASE JSON (df_base) E CRIAÇÃO DE TABELAS DE APOIO
    # ----------------------------------------------------------------------------
    df_base = pd.read_json(json_path)

    # Converter "Nº SEI" para numérico, tratar "-" como NaN
    df_base["Nº SEI"] = df_base["Nº SEI"].astype(str).replace("-", np.nan)
    df_base["Nº SEI"] = pd.to_numeric(df_base["Nº SEI"], errors="coerce")

    # Selecionar colunas relevantes
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

    # Criar tabela fixa de consulta
    cursor.execute(""" DROP TABLE IF EXISTS td_dados_base_iniciativas """)
    df_base.to_sql("td_dados_base_iniciativas", conn, if_exists="replace", index=False)

    # ----------------------------------------------------------------------------
    # 3) LEITURA DA PLANILHA (EXCEL) COM RESUMOS SEI
    # ----------------------------------------------------------------------------
    df_resumos = pd.read_excel(excel_path, sheet_name="Planilha1", engine="openpyxl")
    df_resumos.dropna(how="all", inplace=True)

    # Padroniza colunas (minúsculas, underscores)
    df_resumos.columns = [col.strip().lower().replace(" ", "_") for col in df_resumos.columns]

    # Cria tabela para armazenar resumos SEI
    cursor.execute(""" DROP TABLE IF EXISTS td_dados_resumos_sei """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_dados_resumos_sei (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diretoria TEXT,
            coordenacao_geral TEXT,
            coordenacao TEXT,
            demandante TEXT,
            id_resumo TEXT,
            iniciativa TEXT,
            introducao TEXT,
            justificativa TEXT,
            objetivo_geral TEXT,
            unidades_conservacao TEXT,
            metodologia TEXT
        )
    """)
    conn.commit()

    # Salva dados do Excel na tabela
    df_resumos.to_sql("td_dados_resumos_sei", conn, if_exists="replace", index=False)

    # ----------------------------------------------------------------------------
    # 4) CRIAÇÃO DAS TABELAS DIMENSÃO
    # ----------------------------------------------------------------------------
    cursor.execute(""" DROP TABLE IF EXISTS td_demandantes """)
    cursor.execute(""" DROP TABLE IF EXISTS td_iniciativas """)
    cursor.execute(""" DROP TABLE IF EXISTS td_acoes_aplicacao """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_demandantes (
            id_demandante INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_demandante TEXT UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_iniciativas (
            id_iniciativa INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_iniciativa TEXT UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_acoes_aplicacao (
            id_acao INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_acao TEXT UNIQUE
        )
    """)

    # ----------------------------------------------------------------------------
    # 5) TABELA DE UNIDADES
    # ----------------------------------------------------------------------------
    cursor.execute(""" DROP TABLE IF EXISTS td_unidades """)
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

    # ----------------------------------------------------------------------------
    # 6) TABELA FATO - tf_cadastros_iniciativas
    # ----------------------------------------------------------------------------
    cursor.execute(""" DROP TABLE IF EXISTS tf_cadastros_iniciativas """)
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
            formas_contratacao TEXT,
            FOREIGN KEY (id_demandante) REFERENCES td_demandantes(id_demandante),
            FOREIGN KEY (id_iniciativa) REFERENCES td_iniciativas(id_iniciativa),
            FOREIGN KEY (id_acao) REFERENCES td_acoes_aplicacao(id_acao),
            FOREIGN KEY (cnuc) REFERENCES td_unidades(cnuc)
        )
    """)

    # ----------------------------------------------------------------------------
    # 7) TABELA PRINCIPAL DE REGRAS DE NEGÓCIO
    # ----------------------------------------------------------------------------
    cursor.execute(""" DROP TABLE IF EXISTS tf_cadastro_regras_negocio """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tf_cadastro_regras_negocio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_iniciativa INTEGER NOT NULL,
            usuario TEXT NOT NULL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            objetivo_geral TEXT NOT NULL,            -- Texto simples
            objetivos_especificos TEXT NOT NULL,     -- JSON (lista de strings)
            introducao TEXT NOT NULL,
            justificativa TEXT NOT NULL,
            metodologia TEXT NOT NULL,
            demais_informacoes TEXT,                 -- JSON (dict)
            eixos_tematicos TEXT NOT NULL,           -- JSON (lista de dicts)
            acoes_manejo TEXT NOT NULL,              -- JSON (dict com ações)
            insumos TEXT NOT NULL,                   -- JSON (dict ou lista com insumos)
            regra TEXT NOT NULL,                     -- JSON consolidado (opcional)
            distribuicao_ucs TEXT,                   -- JSON (DataFrame ou lista)
            formas_contratacao TEXT,                 -- JSON (dict com detalhes)

            FOREIGN KEY (id_iniciativa) REFERENCES td_iniciativas(id_iniciativa)
        )
    """)

    # ----------------------------------------------------------------------------
    # 8) TABELA DE INSUMOS
    # ----------------------------------------------------------------------------
    cursor.execute(""" DROP TABLE IF EXISTS td_insumos """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_insumos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elemento_despesa TEXT NOT NULL,
            especificacao_padrao TEXT,
            descricao_insumo TEXT,
            especificacao_tecnica TEXT,
            preco_referencia REAL,
            data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


    # verifica se colunas origem, situacao e registrado_por existem na tabela td_insumos
    # se não existirem, cria as colunas com valores default
    cursor.execute("PRAGMA table_info(td_insumos)")
    columns = cursor.fetchall()
    columns = [col[1] for col in columns]
    if "origem" not in columns:
        cursor.execute(""" ALTER TABLE td_insumos ADD COLUMN origem TEXT DEFAULT 'base_funbio' """)
    if "situacao" not in columns:
        cursor.execute(""" ALTER TABLE td_insumos ADD COLUMN situacao TEXT DEFAULT 'ativo' """)
    if "registrado_por" not in columns:
        cursor.execute(""" ALTER TABLE td_insumos ADD COLUMN registrado_por TEXT DEFAULT 'admin' """)
    conn.commit()


    # ----------------------------------------------------------------------------
    # 9) POPULA AS TABELAS DIMENSÃO (demandantes, iniciativas, ações, unidades)
    # ----------------------------------------------------------------------------
    # Insere valores únicos
    for table, column, name_col in [
        ("td_demandantes", "DEMANDANTE", "nome_demandante"),
        ("td_iniciativas", "Nome da Proposta/Iniciativa Estruturante", "nome_iniciativa"),
        ("td_acoes_aplicacao", "AÇÃO DE APLICAÇÃO", "nome_acao")
    ]:
        unique_values = df_base[column].dropna().unique()
        for value in unique_values:
            cursor.execute(f"INSERT OR IGNORE INTO {table} ({name_col}) VALUES (?)", (value,))

    # Popula td_unidades
    unidades_unicas = df_base[["CNUC", "Unidade de Conservação", "GR", "CATEGORIA UC", "BIOMA", "UF"]].drop_duplicates()
    for _, row in unidades_unicas.iterrows():
        cursor.execute("""
            INSERT OR IGNORE INTO td_unidades (cnuc, nome_unidade, gr, categoria_uc, bioma, uf)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row["CNUC"],
            row["Unidade de Conservação"],
            row["GR"],
            row["CATEGORIA UC"],
            row["BIOMA"],
            row["UF"]
        ))

    conn.commit()

    # ----------------------------------------------------------------------------
    # 10) CRIA MAPEAMENTOS DE ID (p/ relacionar no tf_cadastros_iniciativas)
    # ----------------------------------------------------------------------------
    id_maps = {}
    for table, column, id_col, name_col in [
        ("td_demandantes", "DEMANDANTE", "id_demandante", "nome_demandante"),
        ("td_iniciativas", "Nome da Proposta/Iniciativa Estruturante", "id_iniciativa", "nome_iniciativa"),
        ("td_acoes_aplicacao", "AÇÃO DE APLICAÇÃO", "id_acao", "nome_acao")
    ]:
        df_map = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        id_maps[table] = df_map.set_index(name_col)[id_col].to_dict()

    # Preenche colunas ID na df_base
    df_base["id_demandante"] = df_base["DEMANDANTE"].map(id_maps["td_demandantes"]).fillna(-1)
    df_base["id_iniciativa"] = df_base["Nome da Proposta/Iniciativa Estruturante"].map(id_maps["td_iniciativas"]).fillna(-1)
    df_base["id_acao"] = df_base["AÇÃO DE APLICAÇÃO"].map(id_maps["td_acoes_aplicacao"]).fillna(-1)

    # Salva na tabela fato
    df_base.to_sql("tf_cadastros_iniciativas", conn, if_exists="replace", index=False)

    # ----------------------------------------------------------------------------
    # 11) CARREGA INSUMOS A PARTIR DO EXCEL base_insumos.xlsx
    # ----------------------------------------------------------------------------
    try:
        excel_insumos_path = "dados/base_insumos.xlsx"
        df_raw = pd.read_excel(excel_insumos_path, sheet_name=0)

        # Garante colunas mínimas
        if "Especificação Técnica (detalhamento)" not in df_raw.columns:
            df_raw["Especificação Técnica (detalhamento)"] = ""

        df_insumos = df_raw.rename(columns={
            "Elemento de Despesa": "elemento_despesa",
            "Especificação Padrão": "especificacao_padrao",
            "Descrição do Insumo": "descricao_insumo",
            "Especificação Técnica (detalhamento)": "especificacao_tecnica",
            "Valor ATUALIZADO EM Dezembro/2024": "valor_referencia"
        })

        # # Ajusta valores numéricos
        # df_insumos["valor_referencia"] = (
        #     df_insumos["valor_referencia"]
        #     .astype(str)
        #     .str.replace(".", "")   # remove milhar
        #     .str.replace(",", ".")  # vírgula decimal -> ponto
        # )
        df_insumos["valor_referencia"] = pd.to_numeric(df_insumos["valor_referencia"], errors="coerce").fillna(0.0)

        # Seleciona colunas na ordem
        df_insumos = df_insumos[[
            "elemento_despesa",
            "especificacao_padrao",
            "descricao_insumo",
            "especificacao_tecnica",
            "valor_referencia"
        ]]

        # Renomeia "valor_referencia" -> "preco_referencia"
        df_insumos.rename(columns={"valor_referencia": "preco_referencia"}, inplace=True)

        # Insere no banco (append)
        df_insumos.to_sql("td_insumos", conn, if_exists="append", index=False)
        print("✅ Tabela td_insumos populada com sucesso a partir do Excel!")
    except Exception as e:
        print("❌ Erro ao tentar popular td_insumos:", e)

    conn.close()
    print("✅ Banco de dados inicializado com sucesso!")


def init_samge_database():
    # Caminho do arquivo Excel com os dados do SAMGe
    excel_path = "dados/matrizConceitual_linguagemSAMGe.xlsx"
    db_path = "database/app_data.db"

    """Cria as tabelas do SAMGe no banco de dados e popula com os dados do Excel."""
    if not os.path.exists(excel_path):
        print("❌ Arquivo do SAMGe não encontrado!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ----------------------------------------------------------------------------
    # Tabelas do SAMGe: Macroprocessos, Processos, Ações de Manejo, Atividades
    # ----------------------------------------------------------------------------
    cursor.execute(""" DROP TABLE IF EXISTS td_samge_macroprocessos """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_samge_macroprocessos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_m TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT
        )
    """)

    cursor.execute(""" DROP TABLE IF EXISTS td_samge_processos """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_samge_processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_p TEXT UNIQUE NOT NULL,
            macroprocesso_id TEXT NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT,
            explicacao TEXT,
            FOREIGN KEY (macroprocesso_id) REFERENCES td_samge_macroprocessos(id_m)
        )
    """)

    cursor.execute(""" DROP TABLE IF EXISTS td_samge_acoes_manejo """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_samge_acoes_manejo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_ac TEXT UNIQUE NOT NULL,
            processo_id TEXT NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT,
            explicacao TEXT,
            entrega TEXT,
            FOREIGN KEY (processo_id) REFERENCES td_samge_processos(id_p)
        )
    """)

    cursor.execute(""" DROP TABLE IF EXISTS td_samge_atividades """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS td_samge_atividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_at TEXT UNIQUE NOT NULL,
            acao_manejo_id TEXT NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT,
            explicacao TEXT,
            subentrega TEXT,
            FOREIGN KEY (acao_manejo_id) REFERENCES td_samge_acoes_manejo(id_ac)
        )
    """)

    conn.commit()

    # Lê o Excel do SAMGe
    df = pd.read_excel(excel_path, engine="openpyxl")

    # Padroniza colunas
    df.columns = df.columns.str.strip()

    # ----------------------------------------------------------------------------
    # Insere Macroprocessos
    # ----------------------------------------------------------------------------
    macroprocessos = df[["ID-M", "Macroprocesso"]].drop_duplicates()
    macroprocessos.columns = ["id_m", "nome"]
    macroprocessos["descricao"] = None
    macroprocessos.to_sql("td_samge_macroprocessos", conn, if_exists="replace", index=False)

    # ----------------------------------------------------------------------------
    # Insere Processos
    # ----------------------------------------------------------------------------
    processos = df[["ID-P", "Processo", "Descrição do Processo", "Explicação do Processo", "ID-M"]].drop_duplicates()
    processos.columns = ["id_p", "nome", "descricao", "explicacao", "macroprocesso_id"]
    processos.to_sql("td_samge_processos", conn, if_exists="replace", index=False)

    # ----------------------------------------------------------------------------
    # Insere Ações de Manejo
    # ----------------------------------------------------------------------------
    acoes_manejo = df[["ID-AC", "Ação de Manejo", "Descrição da Ação de Manejo", "Explicação da Ação de Manejo", "Entrega", "ID-P"]].drop_duplicates()
    acoes_manejo.columns = ["id_ac", "nome", "descricao", "explicacao", "entrega", "processo_id"]
    acoes_manejo.to_sql("td_samge_acoes_manejo", conn, if_exists="replace", index=False)

    # ----------------------------------------------------------------------------
    # Insere Atividades
    # ----------------------------------------------------------------------------
    atividades = df[["ID-AT", "Atividade", "Descrição da Atividade", "Explicação da Atividade", "Subentrega", "ID-AC"]].drop_duplicates()
    atividades.columns = ["id_at", "nome", "descricao", "explicacao", "subentrega", "acao_manejo_id"]
    atividades.to_sql("td_samge_atividades", conn, if_exists="replace", index=False)

    conn.close()
    print("✅ Banco de dados SAMGe atualizado com sucesso!")


if __name__ == "__main__":
    init_database()
    init_samge_database()

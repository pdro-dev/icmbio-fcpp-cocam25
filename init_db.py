# init_db.py
import json
import numpy as np
import pandas as pd
import sqlite3
import os

def init_database():
    # Caminhos do JSON e do banco
    json_path = "dados/base_iniciativas_consolidada.json"
    db_path = "database/app_data.db"

    # Carrega o arquivo JSON em um DataFrame
    df = pd.read_json(json_path)

    # Exemplo de tratamento de coluna "Nº SEI"
    # Converte "-" em NaN e tenta converter para numérico
    df["Nº SEI"] = df["Nº SEI"].astype(str).replace("-", np.nan)
    df["Nº SEI"] = pd.to_numeric(df["Nº SEI"], errors="coerce")

    # Ajuste para as colunas que você realmente deseja
    colunas_desejadas = [
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

    
    # Filtra o DataFrame
    df_filtrado = df[colunas_desejadas]

    # Cria um ID automático, de 1 até o número de linhas
    df_filtrado.insert(0, "ID", range(1, len(df_filtrado) + 1))

    # Garante a existência do diretório e cria/atualiza o banco
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(db_path)
    df_filtrado.to_sql("cadastros_iniciais", conn, if_exists="replace", index=False)
    conn.close()

    print("Banco de dados inicializado com sucesso!")

# Se chamar este arquivo diretamente: cria/recria o banco
if __name__ == "__main__":
    init_database()

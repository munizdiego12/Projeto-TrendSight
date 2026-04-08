from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
from sqlalchemy import create_engine, text
import pandas as pd

app = Flask(__name__)
CORS(app) 

# --- ROTA PRINCIPAL: HTML ---
@app.route('/')
def home():
    return send_file('index.html')

# Variável de conexão com a Nuvem Neon (COLE SUA URL AQUI)
DATABASE_URL = "postgresql://neondb_owner:npg_esUo6BKpL4Ib@ep-crimson-lab-amurwrao.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require"

# --- ROTA 1: Visão Geral do Mercado ---
@app.route('/api/mercado', methods=['GET'])
def obter_dados_mercado():
    try:
        engine = create_engine(DATABASE_URL)
        query = text('SELECT * FROM analise_mercado ORDER BY "Probabilidade (%)" DESC')
        df = pd.read_sql_query(query, engine)
        
        dados = df.to_dict(orient='records')
        
        top_compras = [acao for acao in dados if acao['Sinal'] == 'COMPRA'][:5]
        top_vendas = [acao for acao in dados if acao['Sinal'] == 'VENDA'][:5]
        top_espera = [acao for acao in dados if acao['Sinal'] == 'ESPERAR'][:3]
        
        return jsonify({"status": "sucesso", "compras": top_compras, "vendas": top_vendas, "espera": top_espera})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

# --- ROTA 2: Ler Carteira ---
@app.route('/api/carteira', methods=['GET'])
def obter_dados_carteira():
    try:
        engine = create_engine(DATABASE_URL)
        query = text("""
            SELECT c."Ativo", c."Quantidade", c."Preco_Medio", m."Preço (R$)" as "Preco_Atual", m."Sinal"
            FROM minha_carteira c LEFT JOIN analise_mercado m ON c."Ativo" = m."Ativo"
        """)
        df_carteira = pd.read_sql_query(query, engine)

        df_carteira['Preco_Atual'] = df_carteira['Preco_Atual'].fillna(df_carteira['Preco_Medio'])
        df_carteira['Saldo_Total'] = round(df_carteira['Quantidade'] * df_carteira['Preco_Atual'], 2)
        df_carteira['Lucro_R$'] = round((df_carteira['Preco_Atual'] - df_carteira['Preco_Medio']) * df_carteira['Quantidade'], 2)
        df_carteira['Rentabilidade_%'] = round(((df_carteira['Preco_Atual'] / df_carteira['Preco_Medio']) - 1) * 100, 2)
        
        patrimonio_total = round(df_carteira['Saldo_Total'].sum(), 2)
        lucro_total = round(df_carteira['Lucro_R$'].sum(), 2)

        return jsonify({"status": "sucesso", "resumo": {"patrimonio_total": patrimonio_total, "lucro_total": lucro_total}, "ativos": df_carteira.to_dict(orient='records')})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

# --- ROTA 3: Adicionar Ativo (NOVO) ---
@app.route('/api/carteira/adicionar', methods=['POST'])
def adicionar_ativo():
    dados = request.json
    ativo = dados.get('Ativo').upper().strip()
    quantidade = int(dados.get('Quantidade'))
    preco = float(dados.get('Preco_Medio'))

    try:
        engine = create_engine(DATABASE_URL)
        with engine.begin() as conn:
            # Apaga se já existir para não dar erro, e insere os dados novos
            conn.execute(text('DELETE FROM minha_carteira WHERE "Ativo" = :ativo'), {"ativo": ativo})
            conn.execute(text('INSERT INTO minha_carteira ("Ativo", "Quantidade", "Preco_Medio") VALUES (:ativo, :qtd, :preco)'), 
                         {"ativo": ativo, "qtd": quantidade, "preco": preco})
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

# --- ROTA 4: Remover Ativo (NOVO) ---
@app.route('/api/carteira/remover/<ativo>', methods=['DELETE'])
def remover_ativo(ativo):
    try:
        engine = create_engine(DATABASE_URL)
        with engine.begin() as conn:
            conn.execute(text('DELETE FROM minha_carteira WHERE "Ativo" = :ativo'), {"ativo": ativo.upper()})
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
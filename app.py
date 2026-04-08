from flask import Flask, jsonify, send_file
from flask_cors import CORS
from sqlalchemy import create_engine, text
import pandas as pd

app = Flask(__name__)
CORS(app) 

# --- ROTA PRINCIPAL: Mostra o site visual (HTML) ---
@app.route('/')
def home():
    return send_file('index.html')

# Variável de conexão com a Nuvem
DATABASE_URL = "postgresql://neondb_owner:npg_esUo6BKpL4Ib@ep-crimson-lab-amurwrao.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require"

# --- ROTA 1: Visão Geral do Mercado ---
@app.route('/api/mercado', methods=['GET'])
def obter_dados_mercado():
    try:
        engine = create_engine(DATABASE_URL)
        # Consulta protegida com text()
        query = text('SELECT * FROM analise_mercado ORDER BY "Probabilidade (%)" DESC')
        df = pd.read_sql_query(query, engine)
        
        dados = df.to_dict(orient='records')
        
        top_compras = [acao for acao in dados if acao['Sinal'] == 'COMPRA'][:5]
        top_vendas = [acao for acao in dados if acao['Sinal'] == 'VENDA'][:5]
        top_espera = [acao for acao in dados if acao['Sinal'] == 'ESPERAR'][:3]
        
        return jsonify({
            "status": "sucesso",
            "compras": top_compras,
            "vendas": top_vendas,
            "espera": top_espera
        })
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

# --- ROTA 2: O Raio-X da Carteira do Usuário ---
@app.route('/api/carteira', methods=['GET'])
def obter_dados_carteira():
    try:
        engine = create_engine(DATABASE_URL)
        
        # Consulta protegida com text()
        query = text("""
            SELECT 
                c."Ativo", 
                c."Quantidade", 
                c."Preco_Medio", 
                m."Preço (R$)" as "Preco_Atual",
                m."Sinal"
            FROM minha_carteira c
            LEFT JOIN analise_mercado m ON c."Ativo" = m."Ativo"
        """)
        df_carteira = pd.read_sql_query(query, engine)

        df_carteira['Preco_Atual'] = df_carteira['Preco_Atual'].fillna(df_carteira['Preco_Medio'])
        
        df_carteira['Saldo_Total'] = round(df_carteira['Quantidade'] * df_carteira['Preco_Atual'], 2)
        df_carteira['Lucro_R$'] = round((df_carteira['Preco_Atual'] - df_carteira['Preco_Medio']) * df_carteira['Quantidade'], 2)
        df_carteira['Rentabilidade_%'] = round(((df_carteira['Preco_Atual'] / df_carteira['Preco_Medio']) - 1) * 100, 2)
        
        patrimonio_total = round(df_carteira['Saldo_Total'].sum(), 2)
        lucro_total = round(df_carteira['Lucro_R$'].sum(), 2)

        return jsonify({
            "status": "sucesso",
            "resumo": {
                "patrimonio_total": patrimonio_total,
                "lucro_total": lucro_total
            },
            "ativos": df_carteira.to_dict(orient='records')
        })
        
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

if __name__ == '__main__':
    print("🚀 Servidor da API TrendSight rodando!")
    print("-> Mercado: http://localhost:5000/api/mercado")
    print("-> Carteira: http://localhost:5000/api/carteira")
    app.run(debug=True, port=5000)
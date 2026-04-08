from flask import Flask, jsonify, send_file
from flask_cors import CORS
import sqlite3
import pandas as pd

app = Flask(__name__)
CORS(app) 

# --- ROTA PRINCIPAL: Mostra o site visual (HTML) ---
@app.route('/')
def home():
    return send_file('index.html')

# --- ROTA 1: Visão Geral do Mercado (Agora com Top 5 Dinâmico) ---
@app.route('/api/mercado', methods=['GET'])
def obter_dados_mercado():
    try:
        conexao = sqlite3.connect('trendsight.db')
        # Puxando tudo do banco ordenado da maior probabilidade para a menor
        df = pd.read_sql_query("SELECT * FROM analise_mercado ORDER BY `Probabilidade (%)` DESC", conexao)
        conexao.close()
        
        dados = df.to_dict(orient='records')
        
        # O Filtro Inteligente:
        top_compras = [acao for acao in dados if acao['Sinal'] == 'COMPRA'][:5]  # Top 5 Melhores
        top_vendas = [acao for acao in dados if acao['Sinal'] == 'VENDA'][:5]    # Top 5 Piores
        top_espera = [acao for acao in dados if acao['Sinal'] == 'ESPERAR'][:3]  # 3 Neutras
        
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
        conexao = sqlite3.connect('trendsight.db')
        
        # Juntando a carteira com o preço e sinal de hoje
        query = """
            SELECT 
                c.Ativo, 
                c.Quantidade, 
                c.Preco_Medio, 
                m.[Preço (R$)] as Preco_Atual,
                m.Sinal
            FROM minha_carteira c
            LEFT JOIN analise_mercado m ON c.Ativo = m.Ativo
        """
        df_carteira = pd.read_sql_query(query, conexao)
        conexao.close()

        # Calculando o Lucro ou Prejuízo em Reais e em Porcentagem
        # Se a ação não estiver no radar do mercado hoje, preenchemos com 0 para não dar erro
        df_carteira['Preco_Atual'] = df_carteira['Preco_Atual'].fillna(df_carteira['Preco_Medio'])
        
        df_carteira['Saldo_Total'] = round(df_carteira['Quantidade'] * df_carteira['Preco_Atual'], 2)
        df_carteira['Lucro_R$'] = round((df_carteira['Preco_Atual'] - df_carteira['Preco_Medio']) * df_carteira['Quantidade'], 2)
        df_carteira['Rentabilidade_%'] = round(((df_carteira['Preco_Atual'] / df_carteira['Preco_Medio']) - 1) * 100, 2)
        
        # Somatório Geral da Carteira
        patrimonio_total = round(df_carteira['Saldo_Total'].sum(), 2)
        lucro_total = round(df_carteira['Lucro_R$'].sum(), 2)

        # Prepara a entrega para o site
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
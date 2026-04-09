from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

def get_db_connection():
    conn = sqlite3.connect('trendsight.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/mercado', methods=['GET'])
def mercado():
    try:
        conn = get_db_connection()
        ativos_db = conn.execute('SELECT * FROM mercado_diario').fetchall()
        conn.close()
        
        todos = [dict(row) for row in ativos_db]
        
        # Opcional: injetar dados fictícios de gráfico para o front se não existirem
        for a in todos:
            a['Probabilidade (%)'] = a.get('Score', 0) * 16.6
            a['Historico_Precos'] = "10,12,15,14,16,18,17,19,21,20" # Simulando array p/ chart.js
            a['Historico_Datas'] = "2026-04-01,2026-04-02,2026-04-03,2026-04-04,2026-04-05,2026-04-06,2026-04-07,2026-04-08,2026-04-09,2026-04-10"
            
        compras = sorted([a for a in todos if a['Sinal'] == 'COMPRA'], key=lambda x: x['Score'], reverse=True)
        vendas = sorted([a for a in todos if a['Sinal'] == 'VENDA'], key=lambda x: x['Score'])
        espera = [a for a in todos if a['Sinal'] == 'ESPERAR']
        
        return jsonify({'status': 'sucesso', 'compras': compras, 'vendas': vendas, 'espera': espera, 'todos': todos})
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)})

@app.route('/api/historico', methods=['GET'])
def historico():
    try:
        conn = get_db_connection()
        # A query agora traz o Resultado_Atual oficial calculado pelo Python
        sinais = conn.execute('SELECT * FROM historico_sinais ORDER BY id DESC LIMIT 50').fetchall()
        conn.close()
        
        sinais_dict = [dict(s) for s in sinais]
        
        # Garante a compatibilidade dos nomes das chaves com o front-end
        for s in sinais_dict:
            s['Preço (R$)'] = s.pop('Preço_Base', 0)
            s['Alvo (R$)'] = s.pop('Alvo', 0)
            s['Stop (R$)'] = s.pop('Stop', 0)
            
        return jsonify({'status': 'sucesso', 'sinais': sinais_dict})
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)})

@app.route('/api/carteira', methods=['GET'])
def carteira():
    try:
        conn = get_db_connection()
        # FASE 1: Query enriquecida fazendo JOIN com a tabela mercado_diario para pegar os indicadores
        query = """
            SELECT 
                c.Ativo, c.Quantidade, c.Preco_Medio,
                m."Preço (R$)", m.Sinal, m.RSI, m.Score, m.BB_Posicao, m.MM50, m.MM200, m."Variação (%)"
            FROM carteira_usuario c
            LEFT JOIN mercado_diario m ON c.Ativo = m.Ativo
        """
        ativos_db = conn.execute(query).fetchall()
        
        ativos_formatados = []
        patrimonio_total = 0
        lucro_total = 0
        
        for row in ativos_db:
            ativo = dict(row)
            preco_atual = ativo.get('Preço (R$)') or ativo['Preco_Medio']
            saldo = preco_atual * ativo['Quantidade']
            lucro = (preco_atual - ativo['Preco_Medio']) * ativo['Quantidade']
            rentabilidade = ((preco_atual / ativo['Preco_Medio']) - 1) * 100 if ativo['Preco_Medio'] > 0 else 0
            
            patrimonio_total += saldo
            lucro_total += lucro
            
            ativo['Saldo_Total'] = saldo
            ativo['Lucro_R$'] = lucro
            ativo['Rentabilidade_%'] = round(rentabilidade, 2)
            
            ativos_formatados.append(ativo)
            
        conn.close()
        
        return jsonify({
            'status': 'sucesso',
            'resumo': {
                'patrimonio_total': patrimonio_total,
                'lucro_total': lucro_total
            },
            'ativos': ativos_formatados
        })
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)})

@app.route('/api/carteira/adicionar', methods=['POST'])
def add_carteira():
    dados = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT Quantidade, Preco_Medio FROM carteira_usuario WHERE Ativo = ?", (dados['Ativo'],))
        existente = cursor.fetchone()
        
        qtd_nova = float(dados['Quantidade'])
        preco_novo = float(dados['Preco_Medio'])
        
        if existente:
            qtd_atual = existente['Quantidade']
            preco_atual = existente['Preco_Medio']
            qtd_total = qtd_atual + qtd_nova
            preco_medio_total = ((qtd_atual * preco_atual) + (qtd_nova * preco_novo)) / qtd_total
            
            cursor.execute("UPDATE carteira_usuario SET Quantidade = ?, Preco_Medio = ? WHERE Ativo = ?", 
                           (qtd_total, preco_medio_total, dados['Ativo']))
        else:
            cursor.execute("INSERT INTO carteira_usuario (Ativo, Quantidade, Preco_Medio) VALUES (?, ?, ?)", 
                           (dados['Ativo'], qtd_nova, preco_novo))
            
        conn.commit()
        conn.close()
        return jsonify({'status': 'sucesso'})
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)})

@app.route('/api/carteira/remover/<ativo>', methods=['DELETE'])
def rem_carteira(ativo):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM carteira_usuario WHERE Ativo = ?", (ativo,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'sucesso'})
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
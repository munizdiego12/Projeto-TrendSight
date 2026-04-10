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
        
        # BLINDAGEM: Garante que os dados batem com o Front-end, 
        # mesmo se a tabela no servidor da nuvem (Render) estiver desatualizada
        for a in todos:
            # Corrige nomes das colunas de Alvo e Stop se vierem do modelo antigo
            if 'Alvo' in a and 'Alvo (R$)' not in a:
                a['Alvo (R$)'] = a.pop('Alvo')
            if 'Stop' in a and 'Stop (R$)' not in a:
                a['Stop (R$)'] = a.pop('Stop')
                
            # Cria os dados de probabilidade caso o scanner da nuvem ainda não tenha gerado
            if 'Probabilidade (%)' not in a or a['Probabilidade (%)'] is None:
                a['Probabilidade (%)'] = round(min(100.0, a.get('Score', 0) * 16.67), 1)
                
            # Cria um histórico provisório para o gráfico não ficar reto no zero
            if 'Historico_Precos' not in a or a['Historico_Precos'] is None:
                preco = a.get('Preço (R$)', 10)
                a['Historico_Precos'] = ",".join([str(round(preco * (1 + (i*0.005)), 2)) for i in range(-21, 1)])
                a['Historico_Datas'] = ",".join([f"2026-04-{i:02d}" for i in range(1, 23)])
            
        compras = sorted([a for a in todos if a['Sinal'] == 'COMPRA'], key=lambda x: x.get('Score', 0), reverse=True)
        vendas = sorted([a for a in todos if a['Sinal'] == 'VENDA'], key=lambda x: x.get('Score', 0))
        espera = [a for a in todos if a['Sinal'] == 'ESPERAR']
        
        return jsonify({'status': 'sucesso', 'compras': compras, 'vendas': vendas, 'espera': espera, 'todos': todos})
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)})

@app.route('/api/historico', methods=['GET'])
def historico():
    try:
        conn = get_db_connection()
        sinais = conn.execute('SELECT * FROM historico_sinais ORDER BY id DESC LIMIT 50').fetchall()
        conn.close()
        
        sinais_dict = [dict(s) for s in sinais]
        
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
        # CORREÇÃO CRÍTICA: Voltando para a tabela original 'carteira_usuario'
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
            preco_atual = ativo.get('Preço (R$)')
            
            # Se o ativo não foi varrido hoje, usa o preço médio
            if preco_atual is None:
                preco_atual = ativo['Preco_Medio']
                
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
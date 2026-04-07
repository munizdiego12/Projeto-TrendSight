import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings('ignore') # Oculta avisos do pandas para deixar o terminal limpo

def analisar_mercado(tickers):
    print(f"Iniciando varredura de {len(tickers)} ativos da B3...\n")
    resultados = []

    for ticker in tickers:
        try:
            # 1. Extração: Baixa os dados de cada ação
            acao = yf.Ticker(ticker)
            df = acao.history(period="1mo")
            
            if df.empty:
                continue

            # 2. Transformação: Cálculos matemáticos
            preco_atual = round(df['Close'].iloc[-1], 2)
            media_5d = round(df['Close'].tail(5).mean(), 2)
            media_20d = round(df['Close'].tail(20).mean(), 2) # Adicionamos a média de 20 dias para maior precisão

            # 3. Lógica do Algoritmo (Sinais)
            # Regra: Preço acima das médias curtas e longas indica alta forte.
            if preco_atual > media_5d and preco_atual > media_20d:
                sinal = "COMPRA"
                probabilidade = 80 + (preco_atual / media_20d) # Cálculo simples de força
                alvo = preco_atual * 1.06
                stop = preco_atual * 0.96
            elif preco_atual < media_5d and preco_atual < media_20d:
                sinal = "VENDA"
                probabilidade = 70 + (media_20d / preco_atual)
                alvo = preco_atual * 0.94
                stop = preco_atual * 1.04
            else:
                sinal = "NEUTRO"
                probabilidade = 50.0
                alvo = preco_atual
                stop = preco_atual

            # Guarda o resultado da ação atual
            resultados.append({
                'Ativo': ticker.replace('.SA', ''),
                'Preço (R$)': preco_atual,
                'Sinal': sinal,
                'Probabilidade (%)': round(probabilidade, 1),
                'Alvo (R$)': round(alvo, 2),
                'Stop (R$)': round(stop, 2)
            })

        except Exception as e:
            print(f"Erro ao processar {ticker}: {e}")

    # 4. Carga: Converte a lista para um DataFrame do Pandas para facilitar a visualização e ranqueamento
    df_final = pd.DataFrame(resultados)
    return df_final

# --- Execução Principal ---
if __name__ == "__main__":
    # Lista representativa dos "pesos pesados" do Ibovespa
    lista_acoes = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'WEGE3.SA', 
                   'ABEV3.SA', 'MGLU3.SA', 'BBAS3.SA', 'RENT3.SA', 'B3SA3.SA']
    
    # Roda o cérebro
    tabela_mercado = analisar_mercado(lista_acoes)

    # Ordena a tabela pela maior probabilidade para criar os rankings
    tabela_mercado = tabela_mercado.sort_values(by='Probabilidade (%)', ascending=False)

    # Filtra os Tops e Bottoms
    top_compras = tabela_mercado[tabela_mercado['Sinal'] == 'COMPRA']
    top_vendas = tabela_mercado[tabela_mercado['Sinal'] == 'VENDA']

    print("🟢 TOP COMPRAS (Os cards verdes do seu site):")
    print(top_compras.head(3).to_string(index=False)) # Mostra as 3 melhores
    
    print("\n🔴 TOP VENDAS (Os cards vermelhos do seu site):")
    print(top_vendas.head(3).to_string(index=False)) # Mostra as 3 piores

    import sqlite3

# ... (Mantenha sua função analisar_mercado inteira aqui em cima) ...

def salvar_no_banco(df):
    print("\n💾 Salvando dados no banco de dados SQL...")
    
    # 1. Conecta (ou cria) o arquivo do banco de dados na mesma pasta do seu projeto
    conexao = sqlite3.connect('trendsight.db')
    
    # 2. A mágica do Pandas: transforma o DataFrame em uma tabela SQL em uma linha
    # if_exists='replace' garante que a tabela seja atualizada com dados frescos toda vez que rodar
    df.to_sql('analise_mercado', conexao, if_exists='replace', index=False)
    
    # 3. Teste de fogo: Fazendo um SELECT com SQL puro para provar que salvou
    cursor = conexao.cursor()
    cursor.execute("SELECT Ativo, Sinal, `Probabilidade (%)` FROM analise_mercado LIMIT 3")
    linhas = cursor.fetchall()
    
    print("Leitura do Banco de Dados confirmada com sucesso:")
    for linha in linhas:
        print(f" -> {linha}")
        
    conexao.close()
    print("✅ Banco de dados 'trendsight.db' criado e atualizado!")

# --- Execução Principal ---
if __name__ == "__main__":
    lista_acoes = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'WEGE3.SA', 
                   'ABEV3.SA', 'MGLU3.SA', 'BBAS3.SA', 'RENT3.SA', 'B3SA3.SA']
    
    tabela_mercado = analisar_mercado(lista_acoes)

    # --- NOVO: Chamando a função de salvar no banco ---
    # Passamos a tabela inteira (sem os filtros de top/bottom) para o banco ter todos os dados
    salvar_no_banco(tabela_mercado)
    
    tabela_mercado = tabela_mercado.sort_values(by='Probabilidade (%)', ascending=False)
    top_compras = tabela_mercado[tabela_mercado['Sinal'] == 'COMPRA']
    top_vendas = tabela_mercado[tabela_mercado['Sinal'] == 'VENDA']

    print("\n🟢 TOP COMPRAS (Os cards verdes do seu site):")
    print(top_compras.head(3).to_string(index=False))
    
    print("\n🔴 TOP VENDAS (Os cards vermelhos do seu site):")
    print(top_vendas.head(3).to_string(index=False))
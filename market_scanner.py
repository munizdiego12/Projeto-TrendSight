import yfinance as yf
import pandas as pd
import warnings
from sqlalchemy import create_engine, text
warnings.filterwarnings('ignore')

def analisar_mercado(tickers):
    print(f"Iniciando varredura de {len(tickers)} ativos da B3...\n")
    resultados = []

    for ticker in tickers:
        try:
            acao = yf.Ticker(ticker)
            df = acao.history(period="1mo")
            
            # Garante que temos pelo menos 2 dias de dados para comparar
            if df.empty or len(df) < 2:
                continue

            preco_atual = round(df['Close'].iloc[-1], 2)
            preco_ontem = df['Close'].iloc[-2]
            
            # --- NOVO CÁLCULO: Variação Diária (%) ---
            variacao = round(((preco_atual / preco_ontem) - 1) * 100, 2)

            media_5d = round(df['Close'].tail(5).mean(), 2)
            media_20d = round(df['Close'].tail(20).mean(), 2)

            if preco_atual > media_5d and preco_atual > media_20d:
                sinal = "COMPRA"
                probabilidade = 80 + (preco_atual / media_20d) 
                alvo = preco_atual * 1.06
                stop = preco_atual * 0.96
            elif preco_atual < media_5d and preco_atual < media_20d:
                sinal = "VENDA"
                probabilidade = 70 + (media_20d / preco_atual)
                alvo = preco_atual * 0.94
                stop = preco_atual * 1.04
            else:
                sinal = "ESPERAR"
                probabilidade = 50.0
                alvo = preco_atual
                stop = preco_atual

            resultados.append({
                'Ativo': ticker.replace('.SA', ''),
                'Preço (R$)': preco_atual,
                'Variação (%)': variacao,  # Salvando o novo dado
                'Sinal': sinal,
                'Probabilidade (%)': round(probabilidade, 1),
                'Alvo (R$)': round(alvo, 2),
                'Stop (R$)': round(stop, 2)
            })

        except Exception as e:
            print(f"Erro ao processar {ticker}: {e}")

    return pd.DataFrame(resultados)


def salvar_no_banco(df):
    print("\n💾 Salvando dados no PostgreSQL (Neon)...")
    DATABASE_URL = "SUA_URL_AQUI"
    engine = create_engine(DATABASE_URL)
    
    df.to_sql('analise_mercado', engine, if_exists='replace', index=False)
    
    query_teste = text('SELECT "Ativo", "Sinal", "Variação (%)" FROM analise_mercado LIMIT 3')
    teste_df = pd.read_sql_query(query_teste, engine)
    
    print("Leitura do Banco de Dados confirmada com sucesso:")
    print(teste_df.to_string(index=False))
    print("✅ Tabela 'analise_mercado' atualizada na nuvem com a nova Variação!")

if __name__ == "__main__":
    lista_acoes = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'WEGE3.SA', 
                   'ABEV3.SA', 'MGLU3.SA', 'BBAS3.SA', 'RENT3.SA', 'B3SA3.SA']
    
    tabela_mercado = analisar_mercado(lista_acoes)
    salvar_no_banco(tabela_mercado)
    
    tabela_mercado = tabela_mercado.sort_values(by='Probabilidade (%)', ascending=False)
    top_compras = tabela_mercado[tabela_mercado['Sinal'] == 'COMPRA']
    top_vendas = tabela_mercado[tabela_mercado['Sinal'] == 'VENDA']

    print("\n🟢 TOP COMPRAS:")
    print(top_compras.head(3).to_string(index=False))
    
    print("\n🔴 TOP VENDAS:")
    print(top_vendas.head(3).to_string(index=False))
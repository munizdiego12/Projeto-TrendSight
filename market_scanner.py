import yfinance as yf
import pandas as pd
import warnings
from sqlalchemy import create_engine, text
warnings.filterwarnings('ignore')

def analisar_mercado(tickers):
    print(f"Iniciando varredura profunda (1 ano) de {len(tickers)} ativos...\n")
    resultados = []

    for ticker in tickers:
        try:
            acao = yf.Ticker(ticker)
            # Baixamos 1 ano para ter dados para todos os filtros do site
            df = acao.history(period="1y")
            
            if df.empty or len(df) < 2:
                continue

            # Dados atuais e Variação
            preco_atual = round(df['Close'].iloc[-1], 2)
            preco_ontem = df['Close'].iloc[-2]
            variacao = round(((preco_atual / preco_ontem) - 1) * 100, 2)
            volume = int(df['Volume'].iloc[-1])

            # Médias para o Algoritmo
            media_5d = round(df['Close'].tail(5).mean(), 2)
            media_20d = round(df['Close'].tail(20).mean(), 2)

            # Lógica de Sinais
            if preco_atual > media_5d and preco_atual > media_20d:
                sinal, prob = "COMPRA", 80 + (preco_atual / media_20d)
            elif preco_atual < media_5d and preco_atual < media_20d:
                sinal, prob = "VENDA", 70 + (media_20d / preco_atual)
            else:
                sinal, prob = "ESPERAR", 50.0

            # HISTÓRICO PARA O GRÁFICO (Enviamos como uma string separada por vírgulas)
            # Pegamos os últimos 250 dias úteis (aprox. 1 ano)
            historico_precos = ",".join(df['Close'].tail(250).round(2).astype(str).tolist())

            resultados.append({
                'Ativo': ticker.replace('.SA', ''),
                'Preço (R$)': preco_atual,
                'Variação (%)': variacao,
                'Volume': volume,
                'Sinal': sinal,
                'Probabilidade (%)': round(prob, 1),
                'Alvo (R$)': round(preco_atual * 1.06, 2),
                'Stop (R$)': round(preco_atual * 0.94, 2),
                'Historico': historico_precos # <- NOVA COLUNA
            })

        except Exception as e:
            print(f"Erro em {ticker}: {e}")

    return pd.DataFrame(resultados)

def salvar_no_banco(df):
    DATABASE_URL = "postgresql://neondb_owner:npg_esUo6BKpL4Ib@ep-crimson-lab-amurwrao.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require"
    engine = create_engine(DATABASE_URL)
    df.to_sql('analise_mercado', engine, if_exists='replace', index=False)
    print("✅ Banco de dados atualizado com histórico de 1 ano!")

if __name__ == "__main__":
    lista = ['PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'WEGE3.SA', 'ABEV3.SA', 'MGLU3.SA', 'BBAS3.SA', 'RENT3.SA', 'B3SA3.SA']
    tabela = analisar_mercado(lista)
    salvar_no_banco(tabela)
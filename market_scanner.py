import os
import yfinance as yf
import pandas as pd
import warnings
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

warnings.filterwarnings('ignore')
load_dotenv() 

def analisar_mercado(tickers):
    print(f"Iniciando varredura quantitativa (Nativa) em {len(tickers)} ativos...\n")
    resultados = []

    for ticker in tickers:
        try:
            acao = yf.Ticker(ticker)
            df = acao.history(period="1y")
            
            if df.empty or len(df) < 35: 
                continue

            # --- MATEMÁTICA PURA (Sem depender do pandas-ta) ---
            # 1. Cálculo do RSI (Índice de Força Relativa) - 14 dias
            delta = df['Close'].diff()
            ganho = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
            perda = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
            rs = ganho / perda
            df['RSI_14'] = 100 - (100 / (1 + rs))

            # 2. Cálculo do MACD (Média Móvel Convergente e Divergente)
            ema_rapida = df['Close'].ewm(span=12, adjust=False).mean()
            ema_lenta = df['Close'].ewm(span=26, adjust=False).mean()
            linha_macd = ema_rapida - ema_lenta
            linha_sinal = linha_macd.ewm(span=9, adjust=False).mean()
            df['MACD_Hist'] = linha_macd - linha_sinal
            
            df.dropna(inplace=True)
            if df.empty: continue

            # Extração dos dados mais recentes
            preco_atual = round(df['Close'].iloc[-1], 2)
            preco_ontem = df['Close'].iloc[-2]
            variacao = round(((preco_atual / preco_ontem) - 1) * 100, 2)
            volume = int(df['Volume'].iloc[-1]) if not pd.isna(df['Volume'].iloc[-1]) else 0

            # Leituras dos indicadores quantitativos hoje
            rsi_atual = round(df['RSI_14'].iloc[-1], 2)
            macd_hist = df['MACD_Hist'].iloc[-1]

            # --- LÓGICA DO ALGORITMO (Cérebro Quantitativo) ---
            if rsi_atual < 45 and macd_hist > 0:
                sinal = "COMPRA"
                probabilidade = min(95.0, 100 - rsi_atual + 10) 
            elif rsi_atual > 60 and macd_hist < 0:
                sinal = "VENDA"
                probabilidade = min(95.0, rsi_atual + 10)
            else:
                sinal = "ESPERAR"
                probabilidade = 50.0

            # Prepara os dados do gráfico do site
            df_historico = df.tail(250)
            historico_precos = ",".join(df_historico['Close'].round(2).astype(str).tolist())
            historico_datas = ",".join(df_historico.index.strftime('%Y-%m-%d').tolist())

            resultados.append({
                'Ativo': ticker.replace('.SA', ''),
                'Preço (R$)': preco_atual,
                'Variação (%)': variacao,
                'Volume': volume,
                'Sinal': sinal,
                'Probabilidade (%)': round(probabilidade, 1),
                'Alvo (R$)': round(preco_atual * 1.06, 2),
                'Stop (R$)': round(preco_atual * 0.94, 2),
                'Historico_Precos': historico_precos,
                'Historico_Datas': historico_datas
            })
        except Exception as e:
            print(f"Erro em {ticker}: {e}")

    return pd.DataFrame(resultados)

def salvar_no_banco(df):
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("⚠️ ERRO: DATABASE_URL não encontrada. Verifique o arquivo .env!")
        return

    engine = create_engine(DATABASE_URL)
    df.to_sql('analise_mercado', engine, if_exists='replace', index=False)
    print("✅ Banco atualizado com sinais quantitativos avançados (Matemática Nativa)!")

if __name__ == "__main__":
    # Lista atualizada com ações de altíssima liquidez (sem bugs no Yahoo Finance)
    lista = [
        'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'WEGE3.SA', 
        'ABEV3.SA', 'MGLU3.SA', 'BBAS3.SA', 'RENT3.SA', 'B3SA3.SA',
        'RADL3.SA', 'SUZB3.SA', 'EQTL3.SA', 'CSAN3.SA', 'VIVT3.SA', 
        'HAPV3.SA', 'PRIO3.SA', 'GGBR4.SA', 'RAIL3.SA', 'SBSP3.SA', 
        'CMIG4.SA', 'TOTS3.SA', 'BPAC11.SA', 'BBSE3.SA', 'KLBN11.SA'
    ]
    tabela = analisar_mercado(lista)
    salvar_no_banco(tabela)
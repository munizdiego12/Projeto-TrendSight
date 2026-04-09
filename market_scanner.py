import os
import yfinance as yf
import pandas as pd
import warnings
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

warnings.filterwarnings('ignore')
load_dotenv() 

def analisar_mercado(tickers):
    print("Analisando o termômetro global do IBOVESPA...")
    try:
        # Filtro Global - O Mercado dita a maré
        ibov = yf.Ticker('^BVSP').history(period='10d')
        ibov_tendencia = "ALTA" if ibov['Close'].iloc[-1] > ibov['Close'].iloc[-5] else "BAIXA"
        print(f"Tendência Global: {ibov_tendencia}\n")
    except:
        ibov_tendencia = "ALTA" # Fallback de segurança

    print(f"Iniciando varredura com Ensemble Learning em {len(tickers)} ativos...\n")
    resultados = []

    for ticker in tickers:
        try:
            acao = yf.Ticker(ticker)
            # Puxamos 2 anos para garantir o cálculo perfeito da Média de 200 dias
            df = acao.history(period="2y")
            
            if df.empty or len(df) < 200: 
                continue

            # 1. RSI (Índice de Força Relativa) - 14 dias
            delta = df['Close'].diff()
            ganho = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
            perda = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
            rs = ganho / perda
            df['RSI_14'] = 100 - (100 / (1 + rs))

            # 2. MACD (Convergência/Divergência)
            ema_rapida = df['Close'].ewm(span=12, adjust=False).mean()
            ema_lenta = df['Close'].ewm(span=26, adjust=False).mean()
            linha_macd = ema_rapida - ema_lenta
            linha_sinal = linha_macd.ewm(span=9, adjust=False).mean()
            df['MACD_Hist'] = linha_macd - linha_sinal

            # 3. Bandas de Bollinger (20 dias, 2 desvios)
            media_20 = df['Close'].rolling(20).mean()
            desvio = df['Close'].rolling(20).std()
            bb_upper = media_20 + 2 * desvio
            bb_lower = media_20 - 2 * desvio
            # Normalização: 0 = tocando a banda inferior (barato), 1 = tocando a superior (caro)
            amplitude_bb = bb_upper.iloc[-1] - bb_lower.iloc[-1]
            posicao_bb = (df['Close'].iloc[-1] - bb_lower.iloc[-1]) / amplitude_bb if amplitude_bb != 0 else 0.5

            # 4. Médias Móveis (Golden Cross / Death Cross)
            mm50 = df['Close'].tail(50).mean()
            mm200 = df['Close'].tail(200).mean()
            golden_cross = mm50 > mm200

            # 5. Confirmação de Volume
            volume_atual = int(df['Volume'].iloc[-1]) if not pd.isna(df['Volume'].iloc[-1]) else 0
            vol_medio_20d = df['Volume'].tail(20).mean()
            confirmacao_volume = volume_atual > (vol_medio_20d * 1.3) # 30% acima da média
            
            df.dropna(inplace=True)
            if df.empty: continue

            # Leituras Finais
            preco_atual = round(df['Close'].iloc[-1], 2)
            preco_ontem = df['Close'].iloc[-2]
            variacao = round(((preco_atual / preco_ontem) - 1) * 100, 2)
            rsi_atual = round(df['RSI_14'].iloc[-1], 2)
            macd_hist = df['MACD_Hist'].iloc[-1]

            # --- SISTEMA DE PONTOS (ENSEMBLE SCORING) ---
            score = 0
            max_score = 5
            
            if rsi_atual < 45: score += 1           # Sobrevendido
            if macd_hist > 0: score += 1            # Força compradora
            if posicao_bb < 0.30: score += 1        # Esticado para baixo
            if golden_cross: score += 1             # Tendência de alta longa
            if confirmacao_volume: score += 1       # Dinheiro institucional entrando

            # Trava de Segurança Institucional: Se o mercado derrete, rebaixamos o sinal
            if ibov_tendencia == "BAIXA" and score >= 3:
                score -= 1 

            probabilidade = (score / max_score) * 100

            # Decisão de Negócio baseada em Score
            if score >= 3:
                sinal = "COMPRA"
                alvo = round(preco_atual * 1.06, 2)
                stop = round(preco_atual * 0.94, 2)
            elif score <= 1:
                sinal = "VENDA"
                alvo = round(preco_atual * 0.94, 2)
                stop = round(preco_atual * 1.06, 2)
            else:
                sinal = "ESPERAR"
                alvo = preco_atual
                stop = preco_atual

            # Prepara os dados visuais (1 ano de gráfico)
            df_historico = df.tail(250)
            historico_precos = ",".join(df_historico['Close'].round(2).astype(str).tolist())
            historico_datas = ",".join(df_historico.index.strftime('%Y-%m-%d').tolist())

            resultados.append({
                'Ativo': ticker.replace('.SA', ''),
                'Preço (R$)': preco_atual,
                'Variação (%)': variacao,
                'Volume': volume_atual,
                'Sinal': sinal,
                'Probabilidade (%)': round(probabilidade, 1),
                'Alvo (R$)': alvo,
                'Stop (R$)': stop,
                'Score': score,                           # NOVO: Dado para o Front-end
                'RSI': rsi_atual,                         # NOVO: Dado para o Front-end
                'MACD_Hist': round(float(macd_hist), 4),  # NOVO: Dado para o Front-end
                'BB_Posicao': round(float(posicao_bb), 2),# NOVO: Dado para o Front-end
                'MM50': round(float(mm50), 2),            # NOVO: Dado para o Front-end
                'MM200': round(float(mm200), 2),          # NOVO: Dado para o Front-end
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
    print("✅ Banco atualizado! Estrutura de Score e Indicadores salva com sucesso!")

if __name__ == "__main__":
    lista = [
        'PETR4.SA', 'VALE3.SA', 'ITUB4.SA', 'BBDC4.SA', 'WEGE3.SA', 
        'ABEV3.SA', 'MGLU3.SA', 'BBAS3.SA', 'RENT3.SA', 'B3SA3.SA',
        'RADL3.SA', 'SUZB3.SA', 'EQTL3.SA', 'CSAN3.SA', 'VIVT3.SA', 
        'HAPV3.SA', 'PRIO3.SA', 'GGBR4.SA', 'RAIL3.SA', 'SBSP3.SA', 
        'CMIG4.SA', 'TOTS3.SA', 'BPAC11.SA', 'BBSE3.SA', 'KLBN11.SA'
    ]
    tabela = analisar_mercado(lista)
    salvar_no_banco(tabela)
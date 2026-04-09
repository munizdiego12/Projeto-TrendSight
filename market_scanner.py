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
        ibov = yf.Ticker('^BVSP').history(period='10d')
        ibov_tendencia = "ALTA" if ibov['Close'].iloc[-1] > ibov['Close'].iloc[-5] else "BAIXA"
        print(f"Tendência Global: {ibov_tendencia}\n")
    except:
        ibov_tendencia = "ALTA"

    print(f"Iniciando varredura Quantitativa Avançada (ATR/EMA9) em {len(tickers)} ativos...\n")
    resultados = []

    for ticker in tickers:
        try:
            acao = yf.Ticker(ticker)
            df = acao.history(period="2y")
            
            if df.empty or len(df) < 200: 
                continue

            # 1. RSI (14 dias) e Cálculo de Divergência
            delta = df['Close'].diff()
            ganho = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
            perda = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
            rs = ganho / perda
            df['RSI_14'] = 100 - (100 / (1 + rs))

            preco_min_recente = df['Close'].tail(20).min()
            indice_min_preco = df['Close'].tail(20).idxmin()
            rsi_no_min_preco = df['RSI_14'].loc[indice_min_preco]
            rsi_atual_val = df['RSI_14'].iloc[-1]
            
            # 2. MACD
            ema_rapida = df['Close'].ewm(span=12, adjust=False).mean()
            ema_lenta = df['Close'].ewm(span=26, adjust=False).mean()
            linha_macd = ema_rapida - ema_lenta
            linha_sinal = linha_macd.ewm(span=9, adjust=False).mean()
            df['MACD_Hist'] = linha_macd - linha_sinal

            # 3. Bandas de Bollinger
            media_20 = df['Close'].rolling(20).mean()
            desvio = df['Close'].rolling(20).std()
            bb_upper = media_20 + 2 * desvio
            bb_lower = media_20 - 2 * desvio
            amplitude_bb = bb_upper.iloc[-1] - bb_lower.iloc[-1]
            posicao_bb = (df['Close'].iloc[-1] - bb_lower.iloc[-1]) / amplitude_bb if amplitude_bb != 0 else 0.5

            # 4. Médias Móveis Clássicas e EMA 9 (Tendência Curta)
            mm50 = df['Close'].tail(50).mean()
            mm200 = df['Close'].tail(200).mean()
            golden_cross = mm50 > mm200
            ema9 = df['Close'].ewm(span=9, adjust=False).mean().iloc[-1]

            # 5. Volume
            volume_atual = int(df['Volume'].iloc[-1]) if not pd.isna(df['Volume'].iloc[-1]) else 0
            vol_medio_20d = df['Volume'].tail(20).mean()
            confirmacao_volume = volume_atual > (vol_medio_20d * 1.3)
            
            # 6. NOVO: ATR (Average True Range) para Volatilidade Real
            high_low = df['High'] - df['Low']
            high_prev = abs(df['High'] - df['Close'].shift(1))
            low_prev = abs(df['Low'] - df['Close'].shift(1))
            tr = pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            df.dropna(inplace=True)
            if df.empty: continue

            # Extrações Finais
            preco_atual = round(df['Close'].iloc[-1], 2)
            preco_ontem = df['Close'].iloc[-2]
            variacao = round(((preco_atual / preco_ontem) - 1) * 100, 2)
            macd_hist = df['MACD_Hist'].iloc[-1]
            tendencia_curta = preco_atual > ema9

            # --- NOVO SISTEMA DE PONTOS (Score Máximo = 6) ---
            score = 0
            max_score = 6
            
            if rsi_atual_val < 45: score += 1
            if macd_hist > 0: score += 1
            if posicao_bb < 0.30: score += 1
            if golden_cross: score += 1
            if confirmacao_volume: score += 1
            
            # Bônus: Divergência de Alta
            divergencia_alta = (preco_atual <= preco_min_recente * 1.02) and (rsi_atual_val > rsi_no_min_preco + 5)
            if divergencia_alta: score += 1

            if ibov_tendencia == "BAIXA" and score >= 3:
                score -= 1 

            probabilidade = (score / max_score) * 100

            # --- DECISÃO DE NEGÓCIO (Usando ATR para Alvos e Stops) ---
            if score >= 4: # Aumentei a exigência para 4/6 para filtrar melhor
                sinal = "COMPRA"
                alvo = round(preco_atual + (atr * 3.0), 2) # Risco Retorno 1:2
                stop = round(preco_atual - (atr * 1.5), 2)
            elif score <= 1:
                sinal = "VENDA"
                alvo = round(preco_atual - (atr * 3.0), 2) 
                stop = round(preco_atual + (atr * 1.5), 2)
            else:
                sinal = "ESPERAR"
                alvo = preco_atual
                stop = preco_atual

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
                'Score': score,
                'RSI': round(rsi_atual_val, 2),
                'MACD_Hist': round(float(macd_hist), 4),
                'BB_Posicao': round(float(posicao_bb), 2),
                'MM50': round(float(mm50), 2),
                'MM200': round(float(mm200), 2),
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
    
    # 2. Salva o Histórico (Empilha os dados para Backtesting)
    try:
        from datetime import datetime
        hoje = datetime.now().strftime('%Y-%m-%d')
        
        # Filtra apenas os sinais fortes (ignora o ESPERAR para limpar o banco)
        df_sinais = df[df['Sinal'].isin(['COMPRA', 'VENDA'])].copy()
        
        if not df_sinais.empty:
            df_sinais['Data'] = hoje
            # Seleciona apenas as colunas vitais para o histórico
            colunas_historico = ['Data', 'Ativo', 'Sinal', 'Preço (R$)', 'Alvo (R$)', 'Stop (R$)', 'Score']
            df_historico = df_sinais[colunas_historico]
            
            with engine.begin() as conn:
                # Remove registros de hoje (caso o script rode duas vezes no mesmo dia) para não duplicar
                conn.execute(text(f"DELETE FROM historico_sinais WHERE \"Data\" = '{hoje}'"))
            
            # Adiciona os sinais de hoje no fundo da pilha
            df_historico.to_sql('historico_sinais', engine, if_exists='append', index=False)
            print(f"✅ Histórico salvo! {len(df_historico)} sinais registrados para backtesting.")
    except Exception as e:
        # Se a tabela não existir ainda, o to_sql('append') cria ela automaticamente
        try:
            df_historico.to_sql('historico_sinais', engine, if_exists='append', index=False)
            print(f"✅ Tabela de histórico criada e primeiros {len(df_historico)} sinais registrados.")
        except Exception as ex:
            print(f"⚠️ Erro ao salvar histórico: {ex}")
    print("✅ Banco atualizado! Gestão de Risco por ATR e EMA9 aplicados com sucesso!")

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
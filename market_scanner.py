import yfinance as yf
import pandas as pd
import pymysql
from datetime import datetime
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Lista de ativos da B3 para o scanner
ATIVOS_B3 = [
    'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'BBAS3', 'ABEV3', 'WEGE3', 'MGLU3',
    'RENT3', 'SUZB3', 'EQTL3', 'RADL3', 'B3SA3', 'CSAN3', 'BBSE3', 'KLBN11',
    'PRIO3', 'HAPV3', 'TOTS3', 'SBSP3', 'CMIG4', 'VIVT3', 'BPAC11', 'RAIL3'
]

def get_db_connection():
    # Conexão segura com a nuvem puxando a senha do .env
    return pymysql.connect(
        host='trendsight-db-trendsight-db.a.aivencloud.com',
        port=27805,
        user='avnadmin',
        password=os.getenv('DB_PASSWORD'),
        database='defaultdb',
        autocommit=True
    )

def setup_database(conn):
    with conn.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS mercado_diario")
        
        cursor.execute('''
            CREATE TABLE mercado_diario (
                Ativo VARCHAR(10),
                `Preço (R$)` FLOAT,
                `Variação (%)` FLOAT,
                Volume FLOAT,
                Sinal VARCHAR(20),
                Score INT,
                RSI FLOAT,
                MACD_Hist FLOAT,
                BB_Posicao FLOAT,
                MM50 FLOAT,
                MM200 FLOAT,
                `Alvo (R$)` FLOAT,
                `Stop (R$)` FLOAT,
                `Probabilidade (%)` FLOAT,
                Historico_Precos TEXT,
                Historico_Datas TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historico_sinais (
                id INT AUTO_INCREMENT PRIMARY KEY,
                Data VARCHAR(20),
                Ativo VARCHAR(10),
                Sinal VARCHAR(20),
                `Preço_Base` FLOAT,
                Alvo FLOAT,
                Stop FLOAT,
                Score INT,
                Resultado_Atual VARCHAR(20)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carteira_usuario (
                Ativo VARCHAR(10) PRIMARY KEY,
                Quantidade FLOAT,
                Preco_Medio FLOAT
            )
        ''')

def calcular_indicadores(df):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Stochastic RSI (Mais sensível)
    rsi_min = df['RSI'].rolling(window=14).min()
    rsi_max = df['RSI'].rolling(window=14).max()
    df['StochRSI'] = (df['RSI'] - rsi_min) / (rsi_max - rsi_min + 1e-9)
    
    # OBV (On-Balance Volume)
    direcao = df['Close'].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    df['OBV'] = (df['Volume'] * direcao).cumsum()
    df['OBV_Media'] = df['OBV'].rolling(window=20).mean()
    
    # Médias Móveis e Bandas
    df['MM50'] = df['Close'].rolling(window=50).mean()
    df['MM200'] = df['Close'].rolling(window=200).mean()
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
    df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)
    df['BB_Posicao'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
    
    # MACD e ATR
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df.dropna()

def resolver_backtesting_pendente(conn):
    with conn.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT id, Data, Ativo, Sinal, Alvo, Stop 
                FROM historico_sinais 
                WHERE Resultado_Atual = 'Em andamento' OR Resultado_Atual IS NULL
            """)
            sinais = cursor.fetchall()
            hoje = datetime.today().strftime('%Y-%m-%d')
            
            # Formato antigo era tupla de SQLite, PyMySQL DictCursor retorna dicionários se configurado no app.py,
            # mas aqui no scanner usamos cursor padrão (retorna tupla).
            for sinal in sinais:
                id_sinal, data_sinal, ativo, tipo_sinal, alvo, stop = sinal
                if data_sinal == hoje: continue
                    
                ticker = f"{ativo}.SA"
                hist = yf.Ticker(ticker).history(start=data_sinal, end=hoje)
                if hist.empty: continue
                    
                stop_atingido = False
                alvo_atingido = False
                data_stop = None
                data_alvo = None
                
                if tipo_sinal == 'COMPRA':
                    if (hist['Low'] <= stop).any():
                        stop_atingido = True
                        data_stop = hist[hist['Low'] <= stop].index[0]
                    if (hist['High'] >= alvo).any():
                        alvo_atingido = True
                        data_alvo = hist[hist['High'] >= alvo].index[0]
                elif tipo_sinal == 'VENDA':
                    if (hist['High'] >= stop).any():
                        stop_atingido = True
                        data_stop = hist[hist['High'] >= stop].index[0]
                    if (hist['Low'] <= alvo).any():
                        alvo_atingido = True
                        data_alvo = hist[hist['Low'] <= alvo].index[0]
                
                resultado_final = 'Em andamento'
                if stop_atingido and alvo_atingido:
                    resultado_final = 'LOSS' if data_stop <= data_alvo else 'GAIN'
                elif stop_atingido: resultado_final = 'LOSS'
                elif alvo_atingido: resultado_final = 'GAIN'
                    
                if resultado_final != 'Em andamento':
                    # MySQL usa %s
                    cursor.execute("UPDATE historico_sinais SET Resultado_Atual = %s WHERE id = %s", (resultado_final, id_sinal))
        except Exception as e:
            print(f"Erro no backtesting: {e}")

def scan_mercado():
    print(f"Iniciando varredura TrendSight B3 -> MySQL Nuvem... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    conn = get_db_connection()
    setup_database(conn)
    
    with conn.cursor() as cursor:
        for ativo in ATIVOS_B3:
            try:
                df = yf.Ticker(f"{ativo}.SA").history(period="2y")
                if df.empty or len(df) < 460: continue
                    
                df = calcular_indicadores(df)
                hoje = df.iloc[-1]
                ontem = df.iloc[-2]
                
                preco_atual = round(float(hoje['Close']), 2)
                variacao = round(float(((hoje['Close'] / ontem['Close']) - 1) * 100), 2)
                volume = float(hoje['Volume'])
                
                score = 0
                if float(hoje['RSI']) < 45: score += 1
                if float(hoje['MACD_Hist']) > 0: score += 1
                if float(hoje['BB_Posicao']) < 0.3: score += 1
                if float(hoje['MM50']) > float(hoje['MM200']): score += 2
                elif float(hoje['MM50']) > float(hoje['MM200']) * 0.95: score += 1
                
                if float(hoje['StochRSI']) < 0.20: score += 1
                if float(hoje['OBV']) > float(hoje['OBV_Media']): score += 1
                
                # FASE CRÍTICA: Removida a Sazonalidade Hardcoded (Item 3)
                
                sinal = "ESPERAR"
                alvo = 0.0
                stop = 0.0
                
                if score >= 5:
                    sinal = "COMPRA"
                    alvo = round(preco_atual + (float(hoje['ATR']) * 2.5), 2)
                    stop = round(preco_atual - (float(hoje['ATR']) * 1.5), 2)
                    cursor.execute("""
                        INSERT INTO historico_sinais (Data, Ativo, Sinal, `Preço_Base`, Alvo, Stop, Score, Resultado_Atual) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Em andamento')
                    """, (datetime.now().strftime('%Y-%m-%d'), ativo, sinal, preco_atual, alvo, stop, score))
                
                elif score <= 2:
                    sinal = "VENDA"
                    alvo = round(preco_atual - (float(hoje['ATR']) * 2.5), 2)
                    stop = round(preco_atual + (float(hoje['ATR']) * 1.5), 2)
                    cursor.execute("""
                        INSERT INTO historico_sinais (Data, Ativo, Sinal, `Preço_Base`, Alvo, Stop, Score, Resultado_Atual) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Em andamento')
                    """, (datetime.now().strftime('%Y-%m-%d'), ativo, sinal, preco_atual, alvo, stop, score))
                
                probabilidade = round(min(100.0, score * 12.5), 1)
                hist_precos = ",".join(df['Close'].tail(260).round(2).astype(str).tolist())
                hist_datas = ",".join(df.index[-260:].strftime('%Y-%m-%d').tolist())
                    
                cursor.execute("""
                    INSERT INTO mercado_diario 
                    (Ativo, `Preço (R$)`, `Variação (%)`, Volume, Sinal, Score, RSI, MACD_Hist, BB_Posicao, MM50, MM200, `Alvo (R$)`, `Stop (R$)`, `Probabilidade (%)`, Historico_Precos, Historico_Datas) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (ativo, preco_atual, variacao, volume, sinal, score, 
                      round(float(hoje['RSI']), 2), round(float(hoje['MACD_Hist']), 2), 
                      round(float(hoje['BB_Posicao']), 2), round(float(hoje['MM50']), 2), 
                      round(float(hoje['MM200']), 2), alvo, stop, probabilidade, hist_precos, hist_datas))
                
                time.sleep(0.5)
            except Exception as e:
                print(f"Erro ao processar {ativo}: {e}")
                
    print("Varredura concluída. Dados transferidos para MySQL com sucesso.")
    resolver_backtesting_pendente(conn)
    conn.close()

if __name__ == "__main__":
    scan_mercado()
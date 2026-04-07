import yfinance as yf
import pandas as pd

# 1. Definir a ação (adicionamos .SA para identificar que é um ativo da B3 brasileira)
ticker = "PETR4.SA"
acao = yf.Ticker(ticker)

print(f"Conectando ao mercado e puxando dados de {ticker}...\n")

# 2. Puxar o histórico de preços do último mês (1mo)
# O yfinance já nos entrega isso em um DataFrame do Pandas!
df = acao.history(period="1mo")

# 3. Limpar o DataFrame: para o nosso MVP, queremos apenas a data e o preço de Fechamento (Close)
df = df[['Close']].copy()
df.rename(columns={'Close': 'Preco_Fechamento'}, inplace=True)

# 4. Criando nossa Inteligência: Variação Percentual Diária
# Isso calcula se a ação subiu ou desceu em relação ao dia anterior (nosso embrião do sinal Verde/Vermelho)
df['Variacao_Diaria_%'] = df['Preco_Fechamento'].pct_change() * 100

# 5. Criando o indicador de Tendência: Média Móvel de 5 dias
# Ajuda a remover o "ruído" diário e ver para onde o preço está indo na semana
df['Media_Movel_5D'] = df['Preco_Fechamento'].rolling(window=5).mean()

# Limpar as linhas vazias iniciais geradas pela média móvel e arredondar os números
df = df.dropna()
df = df.round(2)

# Exibindo o resultado final processado (os últimos 5 dias)
print("=== Resumo Analítico (Últimos 5 dias) ===")
print(df.tail(5))

# --- ADICIONE ESTE CÓDIGO AO FINAL DO SEU ARQUIVO ---

print("\n=== Gerador de Sinais (A Mágica do TrendSight) ===")

# 1. Pegar apenas a última linha da tabela (o dia mais recente)
ultimo_dia = df.iloc[-1]
preco_atual = ultimo_dia['Preco_Fechamento']
media_5d = ultimo_dia['Media_Movel_5D']

# 2. A Regra de Decisão do Algoritmo
if preco_atual > media_5d:
    sinal = "COMPRAR"
    status_cor = "🟢 Verde"
    probabilidade = 82 # % de chance (simulado para o MVP)
    alvo_lucro = preco_atual * 1.05 # Calcula um alvo de 5% de lucro
    trava_seguranca = preco_atual * 0.97 # Aceita no máximo 3% de perda
    
elif preco_atual < media_5d:
    sinal = "VENDER"
    status_cor = "🔴 Vermelho"
    probabilidade = 73
    alvo_lucro = preco_atual * 0.95 # Alvo para ganhar na queda
    trava_seguranca = preco_atual * 1.03
    
else:
    sinal = "ESPERAR"
    status_cor = "🟡 Amarelo"
    probabilidade = 50
    alvo_lucro = preco_atual
    trava_seguranca = preco_atual

# 3. Exibindo o resultado mastigado para o usuário
print(f"Ativo analisado: {ticker}")
print(f"Veredito: {sinal} {status_cor} (Confiança: {probabilidade}%)")
print(f"Preço de Entrada: R$ {preco_atual:.2f}")
print(f"Venda no Alvo de Lucro: R$ {alvo_lucro:.2f}")
print(f"Saia na Trava de Segurança: R$ {trava_seguranca:.2f}")
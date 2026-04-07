import sqlite3
import pandas as pd

def criar_carteira_usuario():
    print("⚙️ Conectando ao banco de dados...")
    conexao = sqlite3.connect('trendsight.db')
    cursor = conexao.cursor()

    # 1. Cria a tabela da carteira (se não existir)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS minha_carteira (
        Ativo TEXT PRIMARY KEY,
        Quantidade INTEGER,
        Preco_Medio REAL
    )
    ''')

    # 2. Limpa os dados antigos para não duplicar se rodarmos o script duas vezes
    cursor.execute('DELETE FROM minha_carteira')

    # 3. Insere as ações fictícias que o usuário já tem na corretora
    # Formato: (Ticker, Quantidade de ações, Preço médio que pagou)
    acoes_compradas = [
        ('PETR4', 100, 36.50), # Está no lucro (preço atual é maior)
        ('VALE3', 50, 85.20),  # Está no prejuízo (preço atual é menor)
        ('MGLU3', 1000, 15.00) # Prejuízo extremo para testarmos o alerta de venda
    ]

    cursor.executemany('''
    INSERT INTO minha_carteira (Ativo, Quantidade, Preco_Medio)
    VALUES (?, ?, ?)
    ''', acoes_compradas)

    conexao.commit()

    # 4. Lê o banco para confirmar se deu certo
    df_carteira = pd.read_sql_query("SELECT * FROM minha_carteira", conexao)
    print("\n✅ Tabela 'minha_carteira' criada e populada com sucesso!")
    print(df_carteira.to_string(index=False))

    conexao.close()

if __name__ == "__main__":
    criar_carteira_usuario()
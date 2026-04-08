import pandas as pd
from sqlalchemy import create_engine, text

def criar_carteira_usuario():
    print("⚙️ Conectando ao banco de dados na Nuvem (Neon)...")
    DATABASE_URL = "postgresql://neondb_owner:npg_esUo6BKpL4Ib@ep-crimson-lab-amurwrao.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require"
    engine = create_engine(DATABASE_URL)

    # 1. Cria a lista de ações da sua carteira
    dados = [
        {'Ativo': 'PETR4', 'Quantidade': 100, 'Preco_Medio': 36.50},
        {'Ativo': 'VALE3', 'Quantidade': 50, 'Preco_Medio': 85.20},
        {'Ativo': 'MGLU3', 'Quantidade': 1000, 'Preco_Medio': 15.00}
    ]
    df_carteira = pd.DataFrame(dados)

    # 2. Salva direto no PostgreSQL (Substitui se já existir, evitando duplicidade)
    print("Enviando dados...")
    df_carteira.to_sql('minha_carteira', engine, if_exists='replace', index=False)

    # 3. Lê o banco na nuvem para confirmar se deu certo (AGORA COM O TEXT)
    query_confirmacao = text('SELECT * FROM minha_carteira')
    df_confirmacao = pd.read_sql_query(query_confirmacao, engine)
    
    print("\n✅ Tabela 'minha_carteira' criada e populada no PostgreSQL com sucesso!")
    print(df_confirmacao.to_string(index=False))

if __name__ == "__main__":
    criar_carteira_usuario()
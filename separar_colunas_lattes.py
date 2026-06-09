import pandas as pd

def carregar_e_agrupar_planilha(url_ou_caminho):
    """
    Carrega a planilha (via link de exportação do Google Sheets ou arquivo local)
    """
    try:
        df = pd.read_csv(url_ou_caminho)
    except Exception:
        df = pd.read_excel(url_ou_caminho)
    
    # Colunas de referência geral que sempre acompanham o grupo
    colunas_base = ['TAG', 'PESO', 'SAT']
    
    # Mapeamento dos grupos/subcomitês da PROPP identificados na planilha
    grupos_areas = {
        'BIO': 'Ciências Biológicas e Ciências Agrárias',
        'SAU': 'Ciências da Saúde',
        'EXA': 'Ciências Exatas e da Terra',
        'HUM': 'Ciências Humanas',
        'CSA': 'Ciências Sociais Aplicadas',
        'ENG': 'Engenharias e Ciência da Computação',
        'LLA': 'Linguística, Letras e Artes'
    }
    
    return df, colunas_base, grupos_areas

def buscar_grupo_especifico(df, colunas_base, sigla_grupo):
    """
    Busca e filtra apenas um grupo de cada vez, trazendo os dados gerais + os pesos do grupo
    """
    col_peso = f'PESO-{sigla_grupo}'
    col_sat = f'SAT-{sigla_grupo}'
    
    # Monta a lista de colunas que queremos extrair para este grupo
    colunas_filtradas = []
    for col in colunas_base:
        if col in df.columns:
            colunas_filtradas.append(col)
            
    if col_peso in df.columns:
        colunas_filtradas.append(col_peso)
    if col_sat in df.columns:
        colunas_filtradas.append(col_sat)
        
    return df[colunas_filtradas]

# --- EXECUÇÃO DO SCRIPT ---
if __name__ == "__main__":
    # URL configurada para exportar diretamente a aba específica em formato CSV
    SPREADSHEET_ID = "1rW1U0nG9Ua6Y5VOwzWxXfpSaLEKFrUp5XqXwGcuetjw"
    GID = "833349416"
    url_online = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID}"
    
    print("Acessando e lendo a planilha online...")
    df, colunas_base, grupos = carregar_e_agrupar_planilha(url_online)
    print("Planilha carregada com sucesso!\n")
    
    # Exibe o menu de grupos encontrados
    print("Grupos disponíveis para consulta:")
    for sigla, nome in grupos.items():
        print(f" [{sigla}] - {nome}")
    print("-" * 60)
    
    # EXAEMPLO: Buscando e isolando um grupo de cada vez de forma sequencial
    # Você pode mudar a lista abaixo para o grupo que deseja analisar no momento
    grupos_para_buscar = ['BIO', 'SAU', 'EXA', 'HUM', 'CSA', 'ENG', 'LLA'] 
    
    for grupo_alvo in grupos_para_buscar:
        print(f"\n[BUSCA] Isolando dados do grupo: {grupo_alvo} ({grupos[grupo_alvo]})")
        
        # Filtra a planilha trazendo apenas a TAG, a base e o grupo selecionado
        df_resultado = buscar_grupo_especifico(df, colunas_base, grupo_alvo)
        
        # Exibe as primeiras linhas do resultado filtrado
        #print(df_resultado.head(5))
        print(df_resultado)
        print("-" * 60)
        
        # Opcional: Salvar o resultado desse grupo específico em um arquivo separado
        # df_resultado.to_csv(f"tabela_{grupo_alvo}.csv", index=False)
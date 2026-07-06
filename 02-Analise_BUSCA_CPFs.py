# ==============================================================================
# SCRIPT 2: MOTOR DE REGRAS, MATRIZES E ANÁLISE DE FLUXOS (RODA INSTANTÂNEO)
# ==============================================================================
import os
import pandas as pd
from datetime import datetime
import re

ARQUIVO_CLIENTES = "Dados Clientes_V2.xlsx"
BASE_PARQUET = "raw_zendesk_tickets.parquet"

if not os.path.exists(BASE_PARQUET):
    print(f"❌ Erro: O arquivo de cache '{BASE_PARQUET}' não existe. Rode o Script 1 primeiro!")
    exit()

# --- FUNÇÕES DE HIGIENIZAÇÃO CIRÚRGICA DE TEXTO ---
def limpar_canal_parquet(txt):
    if pd.isna(txt) or not txt: return "Não Informado"
    txt_limpo = str(txt).replace("_", " ").replace("::", " - ")
    txt_limpo = re.sub(r'^(Canal de entrada|Canal De Entrada)\s+', '', txt_limpo, flags=re.IGNORECASE)
    return txt_limpo.strip().title()

def limpar_motivo_parquet(txt):
    if pd.isna(txt) or not txt: return "Não classificado"
    
    # 1. Elimina abreviações redundantes e sujeiras do sistema de uma só vez
    t = str(txt).replace("_", " ")
    t = re.sub(r'\bAss\s+Tec\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bAssTec\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bFinan\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bTendacomvoce\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bMot\b', '', t, flags=re.IGNORECASE)
    
    # 2. Divide a árvore pelos níveis originais mapeados pelo sinal '>'
    niveis = t.split(">")
    
    palavras_vistas = set()
    partes_finais = []
    
    # 3. Algoritmo de Deduplicação Hierárquica por Token
    for nivel in niveis:
        palavras_nivel = nivel.split()
        palavras_validas_no_nivel = []
        
        for p in palavras_nivel:
            p_clean = p.strip().title()
            p_lower = p_clean.lower()
            
            # Se a palavra nunca foi vista em níveis superiores, ela é mantida
            if p_lower not in palavras_vistas and p_clean != "":
                palavras_validas_no_nivel.append(p_clean)
                palavras_vistas.add(p_lower) # Registra no banco de memória do ticket
                
        if palavras_validas_no_nivel:
            partes_finais.append(" ".join(palavras_validas_no_nivel))
            
    if not partes_finais: 
        return "Não classificado"
        
    # Retorna o texto corrido limpo, sem os sinais de '>' conforme solicitado
    return " ".join(partes_finais)

def extrair_numeros(texto):
    if pd.isna(texto): return ""
    return re.sub(r'\D', '', str(texto)).zfill(11)

# --- CARGA DOS DADOS ---
print("📖 Carregando base de dados local parquet...")
df_zendesk = pd.read_parquet(BASE_PARQUET)

print("⚙️ Higienizando strings e aplicando novos filtros anti-repetição...")
df_zendesk['Canal de Entrada'] = df_zendesk['Canal de Entrada'].apply(limpar_canal_parquet)
df_zendesk['Motivo de Contato'] = df_zendesk['Motivo de Contato'].apply(limpar_motivo_parquet)

print(f"📖 Lendo arquivo Excel de entrada: {ARQUIVO_CLIENTES}...")
df_clientes = pd.read_excel(ARQUIVO_CLIENTES)
df_clientes['CPF_Limpo'] = df_clientes['Documento'].apply(extrair_numeros)

# --- PROCESSAMENTO DA BASE GERAL ---
print("⚙️ Cruzando dados de CPFs alvo...")
df_geral = pd.merge(df_clientes, df_zendesk, on='CPF_Limpo', how='left')
df_geral['Ticket ID'] = df_geral['Ticket ID'].fillna('-')

# Formatação de Data padrão brasileiro (DD/MM/AAAA)
def formatar_data_br(data_str):
    if not data_str or data_str == '-': return '-'
    try:
        dt = datetime.strptime(str(data_str).split('.')[0].strip(), "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d/%m/%Y")
    except:
        return str(data_str)[:10]

df_geral['Data do Contato'] = df_geral['Data_Ordenacao'].apply(formatar_data_br)
df_geral['Canal de Entrada'] = df_geral['Canal de Entrada'].fillna('Sem contato')
df_geral['Motivo de Contato'] = df_geral['Motivo de Contato'].fillna('Sem contato no período')

# --- FILTRO E ORDENAÇÃO DE JORNADA CRONOLÓGICA ---
df_validos = df_geral[df_geral['Ticket ID'] != '-'].copy()
df_validos['Data_Ordenacao'] = pd.to_datetime(df_validos['Data_Ordenacao'])
df_validos = df_validos.sort_values(by=['CPF_Limpo', 'Data_Ordenacao'])

# Ordenação técnica forçada via string de 2 dígitos (01º, 02º...) para o Excel não embaralhar
df_validos['Ordem_Contato'] = df_validos.groupby('CPF_Limpo').cumcount() + 1
df_validos['Nome_Coluna_Contato'] = df_validos['Ordem_Contato'].apply(lambda x: f"{x:02d}º Contato")

# --- ABA 2: JORNADA SEQUENCIAL DE CANAIS ---
print("📊 Estruturando Jornada Sequencial Ordenada (Apenas CPFs ativos)...")
df_pivot_canais = df_validos.pivot(index='CPF_Limpo', columns='Nome_Coluna_Contato', values='Canal de Entrada').fillna('-')
colunas_ordenadas = sorted(df_pivot_canais.columns)
df_pivot_canais = df_pivot_canais[colunas_ordenadas]

df_cadastro_unificado = df_clientes.drop_duplicates(subset=['CPF_Limpo']).set_index('CPF_Limpo')
df_jornada_final = df_cadastro_unificado.join(df_pivot_canais, how='inner').reset_index()
if 'CPF_Limpo' in df_jornada_final.columns: df_jornada_final.drop(columns=['CPF_Limpo'], inplace=True)
df_jornada_final.columns = [c.lstrip('0') if c.startswith('0') else c for c in df_jornada_final.columns]

# --- ABA 3: VOLUMETRIA POR ETAPA CRONOLÓGICA ---
print("📈 Calculando volumetria de canais por etapa...")
df_volumetria_canais = pd.crosstab(df_validos['Canal de Entrada'], df_validos['Nome_Coluna_Contato'], margins=True, margins_name='Total Geral')
df_volumetria_canais.columns = [c.lstrip('0') if c.startswith('0') else c for c in df_volumetria_canais.columns]

# --- ABA 4: MATRIZ MOTIVOS VS CANAIS POR ETAPA ---
print("🔍 Montando Matriz de Transbordo de Motivos...")
df_motivos_vs_canais_etapa = pd.crosstab(
    index=df_validos['Motivo de Contato'], 
    columns=[df_validos['Nome_Coluna_Contato'], df_validos['Canal de Entrada']], 
    margins=True, 
    margins_name='Total Geral'
)
novos_cabecalhos_etapa = [c.lstrip('0') if c.startswith('0') else c for c in df_motivos_vs_canais_etapa.columns.get_level_values(0)]
df_motivos_vs_canais_etapa.columns = pd.MultiIndex.from_arrays([novos_cabecalhos_etapa, df_motivos_vs_canais_etapa.columns.get_level_values(1)])

# --- ABA 5: FLUXO DE CANAIS POR MOTIVO UNIFICADO (DE -> PARA) ---
print("📊 Calculando Transbordo de Canais por Motivo Unificado...")
df_validos['Proximo_Canal'] = df_validos.groupby('CPF_Limpo')['Canal de Entrada'].shift(-1)
df_transicoes = df_validos[df_validos['Proximo_Canal'].notna()].copy()

df_fluxo_motivos = df_transicoes.groupby(['Motivo de Contato', 'Canal de Entrada', 'Proximo_Canal']).size().reset_index(name='Volume de Transições')
df_fluxo_motivos.columns = ['Motivo de Contato Unificado', 'Canal Origem', 'Canal Destino', 'Volume de Transições']
df_fluxo_motivos = df_fluxo_motivos.sort_values(by=['Motivo de Contato Unificado', 'Volume de Transições'], ascending=[True, False])

# --- ABA 6: FLUXO E COMPORTAMENTO DE CPFs (RANKING DE REPETIÇÃO) ---
print("🔍 Analisando caminhos completos percorridos pelos CPFs...")
df_jornada_por_cpf = df_validos.groupby('CPF_Limpo')['Canal de Entrada'].apply(lambda x: " ➔ ".join(x)).reset_index(name='Fluxo de Canais')
df_fluxo_cpfs = df_jornada_por_cpf['Fluxo de Canais'].value_counts().reset_index()
df_fluxo_cpfs.columns = ['Caminho Percorrido (Sequência de Canais)', 'Volume de Clientes (CPFs únicos)']

total_cpfs_ativos = df_fluxo_cpfs['Volume de Clientes (CPFs únicos)'].sum()
df_fluxo_cpfs['% de Representatividade'] = (df_fluxo_cpfs['Volume de Clientes (CPFs únicos)'] / total_cpfs_ativos * 100).round(2).astype(str) + '%'

# --- SALVAMENTO CONSOLIDADO NO LIVRO EXCEL ---
nome_saida = "Analise_Consolidada_CPFs_Tenda.xlsx"
print(f"💾 Exportando book completo de inteligência para: {nome_saida}...")

with pd.ExcelWriter(nome_saida, engine='openpyxl') as writer:
    colunas_finais_geral = ['Cliente SAP', 'Documento', 'Cliente', 'Ticket ID', 'Data do Contato', 'Canal de Entrada', 'Motivo de Contato']
    df_geral[colunas_finais_geral].to_excel(writer, sheet_name='Base_Geral_Cruzada', index=False)
    df_jornada_final.to_excel(writer, sheet_name='Jornada_Sequencial_Canais', index=False)
    df_volumetria_canais.to_excel(writer, sheet_name='Volumetria_Por_Etapa_Contato')
    df_motivos_vs_canais_etapa.to_excel(writer, sheet_name='Matriz_Motivos_vs_Canais')
    df_fluxo_motivos.to_excel(writer, sheet_name='Fluxo_Canais_Por_Motivo', index=False)
    df_fluxo_cpfs.to_excel(writer, sheet_name='Fluxo_Comportamento_CPFs', index=False)

print("\n🎉 Processo concluído com sucesso! Pode abrir o arquivo Excel final.")
# ==============================================================================
# SCRIPT 3: MACHINE LEARNING E ANÁLISE COMPLETA DE FLUXOS OPERACIONAIS
# ==============================================================================
import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import re

ARQUIVO_CLIENTES = "Dados Clientes_V2.xlsx"
BASE_PARQUET = "raw_zendesk_tickets.parquet"

if not os.path.exists(BASE_PARQUET):
    print(f"❌ Erro: O arquivo de cache '{BASE_PARQUET}' não foi localizado.")
    exit()

# --- FUNÇÕES DE HIGIENIZAÇÃO DE TEXTO ---
def limpar_canal_definitivo(txt):
    if pd.isna(txt) or not txt: return "Não Informado"
    txt_limpo = str(txt).replace("_", " ").replace("::", " - ")
    txt_limpo = re.sub(r'^(Canal de entrada|Canal De Entrada)\s+', '', txt_limpo, flags=re.IGNORECASE)
    return txt_limpo.strip().title()

def super_limpeza_motivo(texto):
    if pd.isna(texto) or not texto: return "Não classificado"
    s = str(texto).upper().replace(">", " ").replace("_", " ").replace("-", " ")
    s = re.sub(r'\bMOT\b|\bASS\b|\bTEC\b|\bFINAN\b|\bTENDACOMVOCE\b', ' ', s)
    palavras = s.split()
    vistas = set()
    resultado = []
    conectivos = {'DE', 'DA', 'DO', 'E', 'PARA', 'COM', 'POR', 'DAS', 'DOS'}
    for p in palavras:
        if len(p) > 1:
            p_clean = p.strip()
            if p_clean not in vistas and p_clean not in conectivos:
                resultado.append(p_clean.title())
                vistas.add(p_clean)
            elif p_clean in conectivos:
                resultado.append(p_clean.lower())
    return " ".join(resultado) if resultado else "Não classificado"

def extrair_numeros(texto):
    if pd.isna(texto): return ""
    return re.sub(r'\D', '', str(texto)).zfill(11)

print("📖 Carregando e higienizando base histórica local...")
df = pd.read_parquet(BASE_PARQUET)
df['Canal de Entrada'] = df['Canal de Entrada'].apply(limpar_canal_definitivo)
df['Motivo de Contato'] = df['Motivo de Contato'].apply(super_limpeza_motivo)

# Ordenação cronológica estrita por cliente
df['Data_Ordenacao'] = pd.to_datetime(df['Data_Ordenacao'])
df = df.sort_values(by=['CPF_Limpo', 'Data_Ordenacao'])

# --- DECOMPOSIÇÃO DA JORNADA SEQUENCIAL DE CANAIS ---
def decompor_jornada(lista_canais):
    canais = list(lista_canais)
    canal_inicial = canais[0]
    canal_final = canais[-1] if len(canais) > 1 else "Resolvido na Origem"
    if len(canais) > 2:
        # Remove duplicados consecutivos no meio para simplificar a visualização visual
        meio_lista = []
        for c in canais[1:-1]:
            if not meio_lista or c != meio_lista[-1]:
                meio_lista.append(c)
        canais_meio = " ➔ ".join(meio_lista)
    else:
         canais_meio = "Direto"
    return pd.Series([canal_inicial, canais_meio, canal_final, len(canais)])

# Agrupa por CPF para consolidar os caminhos de interações
df_jornadas = df.groupby('CPF_Limpo').agg({
    'Motivo de Contato': 'first',
    'Canal de Entrada': list
}).reset_index()

df_jornadas[['Canal Inicial', 'Canais Intermediários', 'Canal Final', 'Total de Interações']] = df_jornadas['Canal de Entrada'].apply(decompor_jornada)

# --- NOVA ABA SOLICITADA: FLUXO PURO DE CANAIS (SEM MOTIVO) ---
print("📊 Calculando a Matriz de Fluxo Puro de Canais...")
df_fluxo_puro = df_jornadas.groupby(['Canal Inicial', 'Canais Intermediários', 'Canal Final']).size().reset_index(name='Volume de Clientes (CPFs)')
df_fluxo_puro = df_fluxo_puro.sort_values(by='Volume de Clientes (CPFs)', ascending=False)

# Aba de Fluxo com Motivo (Mantida para cruzamentos secundários)
df_fluxo_motivos = df_jornadas.groupby(['Motivo de Contato', 'Canal Inicial', 'Canais Intermediários', 'Canal Final']).size().reset_index(name='Volume de Clientes (CPFs)')
df_fluxo_motivos = df_fluxo_motivos.sort_values(by=['Motivo de Contato', 'Volume de Clientes (CPFs)'], ascending=[True, False])

# --- ALIMENTAÇÃO E TREINAMENTO DO MACHINE LEARNING ---
print("🧠 Treinando IA com volumetria higienizada...")
df_primeiro_contato = df.groupby('CPF_Limpo').first().reset_index()
df_contagem = df.groupby('CPF_Limpo').size().reset_index(name='Total_Tickets')
df_ml = pd.merge(df_primeiro_contato, df_contagem, on='CPF_Limpo')

df_ml['Teve_Recontato'] = (df_ml['Total_Tickets'] > 1).astype(int)
df_modelo = df_ml[['Canal de Entrada', 'Motivo de Contato', 'Teve_Recontato']].copy()
df_modelo = df_modelo[~df_modelo['Motivo de Contato'].isin(["Não classificado", "0", ""])].dropna()

X = pd.get_dummies(df_modelo[['Canal de Entrada', 'Motivo de Contato']], drop_first=True)
y = df_modelo['Teve_Recontato']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
modelo_rf = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
modelo_rf.fit(X_train, y_train)

# Geração de Importância Limpa
df_importancia = pd.DataFrame({
    'Componente Operacional': X.columns,
    'Poder de Influência no Recontato (%)': modelo_rf.feature_importances_ * 100
})
df_importancia['Componente Operacional'] = df_importancia['Componente Operacional'].str.replace('Canal de Entrada_', 'Canal: ').str.replace('Motivo de Contato_', 'Motivo: ')
df_importancia = df_importancia.sort_values(by='Poder de Influência no Recontato (%)', ascending=False).head(20)

# --- EXPORTAÇÃO COMPLETA DAS ABAS ---
nome_saida = "ML_e_Fluxos_Preditivos_Tenda.xlsx"
print(f"💾 Gravando livro de insights em: {nome_saida}...")

with pd.ExcelWriter(nome_saida, engine='openpyxl') as writer:
    df_importancia.to_excel(writer, sheet_name='Pesos_Machine_Learning', index=False)
    df_fluxo_puro.to_excel(writer, sheet_name='Fluxo_Puro_Canais', index=False)
    df_fluxo_motivos.to_excel(writer, sheet_name='Fluxo_Canais_Por_Motivo', index=False)

print("\n🎉 Concluído! A nova aba 'Fluxo_Puro_Canais' está pronta para análise de transbordo.")
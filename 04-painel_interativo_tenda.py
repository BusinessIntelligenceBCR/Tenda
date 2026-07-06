# ==============================================================================
# SCRIPT 4: DASHBOARD OMNICHANNEL INTERATIVO COM UPLOAD DE ARQUIVO
# ==============================================================================
import os
import pandas as pd
import plotly.express as px
import re
import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Governança Omnichannel - Tenda", layout="wide")
st.title("📊 Painel Interativo de Fluxo e Atrito de Atendimento")
st.markdown("---")

# --- FUNÇÕES DE HIGIENIZAÇÃO ---
def limpar_canal(txt):
    if pd.isna(txt) or not txt: return "Não Informado"
    txt_limpo = str(txt).replace("_", " ").replace("::", " - ")
    txt_limpo = re.sub(r'^(Canal de entrada|Canal De Entrada)\s+', '', txt_limpo, flags=re.IGNORECASE)
    return txt_limpo.strip().title()

def super_limpeza_motivo(texto):
    if pd.isna(texto) or not texto: return "Não classificado"
    s = str(texto).upper().replace(">", " ").replace("_", " ").replace("-", " ")
    s = re.sub(r'\bMOT\b|\bASS\b|\bTEC\b|\bFINAN\b|\bTENDACOMVOCE\b', ' ', s)
    palavras = s.split()
    vistas, resultado = set(), []
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

# --- BARRA LATERAL: UPLOAD DO ARQUIVO ---
st.sidebar.header("📂 Inserção de Dados")
arquivo_upado = st.sidebar.file_uploader(
    "Arraste a base Parquet da Zendesk aqui:", 
    type=["parquet"],
    help="O painel só será carregado após a inserção do arquivo 'raw_zendesk_tickets.parquet'."
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Ajuste de Visualização")
vol_minimo = st.sidebar.slider("Ocultar fluxos com menos de X clientes:", 1, 50, 2)

# --- CARGA DOS DADOS (AGORA DEPENDE DO UPLOAD) ---
@st.cache_data
def carregar_e_processar_dados(arquivo):
    # O Pandas consegue ler o arquivo upado pelo Streamlit diretamente da memória
    df = pd.read_parquet(arquivo)
    df['Canal de Entrada'] = df['Canal de Entrada'].apply(limpar_canal)
    df['Motivo de Contato'] = df['Motivo de Contato'].apply(super_limpeza_motivo)
    df['Data_Ordenacao'] = pd.to_datetime(df['Data_Ordenacao'])
    df = df.sort_values(by=['CPF_Limpo', 'Data_Ordenacao'])
    
    df_primeiro = df.groupby('CPF_Limpo').first().reset_index()
    mapa_canal_inicial = dict(zip(df_primeiro['CPF_Limpo'], df_primeiro['Canal de Entrada']))
    mapa_motivo_inicial = dict(zip(df_primeiro['CPF_Limpo'], df_primeiro['Motivo de Contato']))
    
    df['Canal_Inicial_Jornada'] = df['CPF_Limpo'].map(mapa_canal_inicial)
    df['Motivo_Inicial_Jornada'] = df['CPF_Limpo'].map(mapa_motivo_inicial)
    return df

# Se nenhum arquivo foi upado, mostra a tela de espera e interrompe o script
if arquivo_upado is None:
    st.info("👋 Olá! Para iniciar a análise, arraste e solte o arquivo **raw_zendesk_tickets.parquet** na área indicada na barra lateral esquerda.")
    st.stop()

# Se o código passou do st.stop(), significa que o gestor upou o arquivo!
df = carregar_e_processar_dados(arquivo_upado)

# ==============================================================================
# ENGENHARIA DE MÉTRICAS E JORNADAS COMPLETAS
# ==============================================================================
df_cpfs = df.groupby('CPF_Limpo').agg({'Motivo_Inicial_Jornada': 'first', 'Ticket ID': 'count'}).reset_index()
df_cpfs['Teve_Recontato'] = (df_cpfs['Ticket ID'] > 1).astype(int)

total_recontatos_global = df_cpfs['Teve_Recontato'].sum()
total_clientes_global = df_cpfs['CPF_Limpo'].nunique()

df_taxa_motivo = df_cpfs.groupby('Motivo_Inicial_Jornada').agg(
    Volume_Clientes=('CPF_Limpo', 'count'), Total_Recontatos=('Teve_Recontato', 'sum')
).reset_index()

df_taxa_motivo['% do Total de Clientes'] = (df_taxa_motivo['Volume_Clientes'] / total_clientes_global * 100).round(2)
df_taxa_motivo['Taxa de Recontato (%)'] = (df_taxa_motivo['Total_Recontatos'] / df_taxa_motivo['Volume_Clientes'] * 100).round(2)
df_taxa_motivo['Impacto no Retrabalho (%)'] = (df_taxa_motivo['Total_Recontatos'] / total_recontatos_global * 100).round(2)

df_taxa_motivo = df_taxa_motivo[df_taxa_motivo['Volume_Clientes'] >= 2].sort_values(by='Impacto no Retrabalho (%)', ascending=False)
motivos_ordenados_por_impacto = df_taxa_motivo['Motivo_Inicial_Jornada'].tolist()

def construir_string_jornada(canais):
    caminho_limpo = []
    for c in canais:
        if not caminho_limpo or c != caminho_limpo[-1]:
            caminho_limpo.append(c)
    return " ➔ ".join(caminho_limpo)

df_jornadas_completas = df.groupby('CPF_Limpo').agg({
    'Canal de Entrada': construir_string_jornada,
    'Motivo_Inicial_Jornada': 'first'
}).reset_index().rename(columns={'Canal de Entrada': 'Jornada_Realizada'})

# --- FUNÇÃO GERADORA DO GRÁFICO ---
def desenhar_grafico_jornadas(df_input, titulo_grafico, min_vol, cor_barra="#2E86C1"):
    jornadas = df_input.groupby('CPF_Limpo')['Canal de Entrada'].apply(list)
    caminhos = []
    for canais in jornadas:
        caminho_limpo = []
        for c in canais:
            if not caminho_limpo or c != caminho_limpo[-1]:
                caminho_limpo.append(c)
        caminhos.append(" ➔ ".join(caminho_limpo))
        
    df_caminhos = pd.DataFrame({'Jornada (Início ➔ Meio ➔ Fim)': caminhos})
    df_ranking = df_caminhos.groupby('Jornada (Início ➔ Meio ➔ Fim)').size().reset_index(name='Quantidade de Clientes')
    df_ranking = df_ranking[df_ranking['Quantidade de Clientes'] >= min_vol]
    
    if df_ranking.empty:
        return None, None
        
    df_top = df_ranking.sort_values(by='Quantidade de Clientes', ascending=True).tail(15)
    fig = px.bar(
        df_top, x='Quantidade de Clientes', y='Jornada (Início ➔ Meio ➔ Fim)', 
        orientation='h', title=titulo_grafico, text='Quantidade de Clientes', color_discrete_sequence=[cor_barra]
    )
    fig.update_layout(yaxis_title="", xaxis_title="Volume de Clientes (CPFs)", height=500, font=dict(size=13))
    return fig, df_ranking

# ==============================================================================
# SEÇÃO 1: ANÁLISE COMPLETA POR CANAL INICIAL
# ==============================================================================
st.header("1️⃣ Tendência de Fluxo por Canal Inicial")
st.markdown("Selecione o canal de origem para analisar a esteira de transbordo utilizada pelos clientes.")

canais_contagem = df.groupby('Canal_Inicial_Jornada')['CPF_Limpo'].nunique().sort_values(ascending=False)
lista_canais = ["Todos (Visão Geral)"] + canais_contagem.index.tolist()
canal_selecionado = st.selectbox("📌 Filtrar Canal de Origem:", lista_canais, key="sec1")

df_sec1 = df[df['Canal_Inicial_Jornada'] == canal_selecionado] if canal_selecionado != "Todos (Visão Geral)" else df.copy()
grafico1, tb1 = desenhar_grafico_jornadas(df_sec1, f"Top Caminhos Percorridos - Iniciados em: {canal_selecionado}", vol_minimo, "#1F618D")

if grafico1:
    st.plotly_chart(grafico1, use_container_width=True)
else:
    st.info("Volume insuficiente para exibir os caminhos deste canal.")

st.markdown("---")

# ==============================================================================
# SEÇÃO 2: MATRIZ DE ATRITO PROPORCIONAL
# ==============================================================================
st.header("2️⃣ Diagnóstico de Atrito: Esforço Operacional Real")
st.markdown("Tabela ordenada pelo **Impacto no Retrabalho (%)**, evidenciando os maiores gargalos.")

df_top_exibicao = df_taxa_motivo.head(20).rename(columns={
    'Motivo_Inicial_Jornada': 'Motivo de Contato Unificado',
    'Volume_Clientes': 'Total de Clientes',
    'Total_Recontatos': 'Qtd. Retornos',
    'Taxa de Recontato (%)': 'Taxa Interna (%)',
    'Impacto no Retrabalho (%)': 'Impacto Global (%)'
})
st.dataframe(df_top_exibicao, use_container_width=True, hide_index=True)

with st.expander("📖 Como ler e interpretar esta tabela?"):
    st.markdown("""
    Esta tabela identifica a verdadeira dor da operação. A contagem **não é feita por número de tickets**, mas sim por **CPFs únicos**, evitando que um único cliente muito frustrado distorça os dados.
    
    * **Total de Clientes:** A quantidade exata de CPFs únicos que iniciaram a sua jornada com este assunto. É o volume bruto do tema.
    * **Qtd. Retornos:** Quantos clientes da coluna anterior falharam em ter o problema resolvido de primeira e abriram 2 ou mais chamados.
    * **Taxa Interna (%):** A eficiência do assunto. Responde: *"Independente do volume, qual é a chance de um cliente que liga sobre este tema precisar voltar?"* (Qtd. Retornos / Total de Clientes).
    * **Impacto Global (%):** A principal métrica estratégica. Responde: *"De todo o retrabalho gerado no SAC, quantos % são culpa deste motivo isolado?"*. Resolver um motivo com alto impacto global traz o maior alívio imediato para a fila de atendimento.
    """)

st.markdown("---")

# ==============================================================================
# SEÇÃO 3: ANÁLISE SETORIAL POR MOTIVO DE CONTATO
# ==============================================================================
st.header("3️⃣ Análise de Transbordo por Motivo de Contato")
st.markdown("Descubra as jornadas geradas por um motivo específico.")

lista_filtro_motivos = ["Todos (Visão Geral)"] + motivos_ordenados_por_impacto
motivo_selecionado = st.selectbox("📌 Filtrar por Motivo Específico:", lista_filtro_motivos, key="sec3")

df_sec3 = df[df['Motivo_Inicial_Jornada'] == motivo_selecionado] if motivo_selecionado != "Todos (Visão Geral)" else df.copy()
grafico3, tb3 = desenhar_grafico_jornadas(df_sec3, f"Top Caminhos Percorridos do Motivo: {motivo_selecionado}", vol_minimo, "#884EA0")

if grafico3:
    st.plotly_chart(grafico3, use_container_width=True)
else:
    st.info("Volume insuficiente para mapear a jornada deste motivo.")

st.markdown("---")

# ==============================================================================
# SEÇÃO 4: ANÁLISE INVERSA - MOTIVOS POR JORNADA
# ==============================================================================
st.header("4️⃣ Análise Inversa: Motivos por Fluxo de Jornada")
st.markdown("Selecione um caminho exato para descobrir quais assuntos empurraram o cliente para essa esteira.")

lista_jornadas_existentes = df_jornadas_completas['Jornada_Realizada'].value_counts().index.tolist()
jornada_selecionada = st.selectbox("📌 Filtrar por Jornada Específica:", lista_jornadas_existentes, key="sec4")

df_sec4 = df_jornadas_completas[df_jornadas_completas['Jornada_Realizada'] == jornada_selecionada]
total_clientes_jornada = len(df_sec4)

df_ranking_jornada = df_sec4.groupby('Motivo_Inicial_Jornada').size().reset_index(name='Quantidade de Clientes')
df_ranking_jornada = df_ranking_jornada.sort_values(by='Quantidade de Clientes', ascending=False)

df_ranking_jornada['% Dentro desta Jornada'] = (df_ranking_jornada['Quantidade de Clientes'] / total_clientes_jornada * 100).round(2).astype(str) + '%'
df_ranking_jornada['% do Total da Operação (CPFs)'] = (df_ranking_jornada['Quantidade de Clientes'] / total_clientes_global * 100).round(2).astype(str) + '%'

df_ranking_jornada = df_ranking_jornada.rename(columns={'Motivo_Inicial_Jornada': 'Motivo de Contato Unificado'})

st.markdown(f"**Volume de clientes (CPFs) que realizaram a jornada `{jornada_selecionada}`:** {total_clientes_jornada}")
st.dataframe(df_ranking_jornada.head(20), use_container_width=True, hide_index=True)

with st.expander("📖 Como interpretar as proporções desta análise?"):
    st.markdown("""
    Enquanto a Seção 3 avalia o caminho gerado por um motivo, esta seção faz o caminho inverso: ela pega um funil que deu errado (como *WhatsApp ➔ Voz*) e investiga quais assuntos causaram essa quebra.
    
    * **Quantidade de Clientes:** Volume de CPFs únicos que entraram no SAC por este motivo e acabaram fazendo exatamente o caminho selecionado.
    * **% Dentro desta Jornada:** O quanto este motivo domina o caminho filtrado. Exemplo: se estiver em 50%, significa que metade de todas as pessoas que sofreram esse transbordo queriam falar sobre este assunto específico.
    * **% do Total da Operação (CPFs):** Perspectiva de volume macro. Mostra qual é a relevância dessas pessoas frente a toda a base de clientes atendidos pela Tenda no período.
    """)
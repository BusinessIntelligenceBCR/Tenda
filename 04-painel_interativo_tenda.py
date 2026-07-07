# ==============================================================================
# SCRIPT 4: DASHBOARD OMNICHANNEL INTERATIVO COM TELA DE LOGIN E UPLOAD SENSÍVEL
# ==============================================================================
import os
import pandas as pd
import plotly.express as px
import re
import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Governança Omnichannel - Tenda", layout="wide")

# --- FUNÇÃO NATIVA DE AUTENTICAÇÃO ---
def verificar_autenticacao():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.title("🔑 Controle de Acesso - BCR CX")
        st.markdown("Insira suas credenciais para acessar o ambiente de Governança Tenda.")
        
        col1, col2 = st.columns(2)
        with col1:
            usuario_digitado = st.text_input("Usuário do Sistema:")
            senha_digitada = st.text_input("Senha de Acesso:", type="password")
            botao_login = st.button("Acessar Painel")
            
        if botao_login:
            if (usuario_digitado == st.secrets["acesso"]["usuario"] and 
                senha_digitada == st.secrets["acesso"]["senha"]):
                st.session_state["autenticado"] = True
                st.success("Acesso autorizado! Carregando dados...")
                st.rerun() 
            else:
                st.error("Usuário ou senha incorretos. Tente novamente.")
        
        return False 
    return True 

if not verificar_autenticacao():
    st.stop()

# ==============================================================================
# SEÇÃO PRINCIPAL DO DASHBOARD
# ==============================================================================
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
    help="O painel só será carregado após a inserção do arquivo 'safe_zendesk_tickets.parquet'."
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Filtro de Relevância")
# CORREÇÃO AQUI: Mudamos de slider para number_input, permitindo filtrar até milhares de clientes se necessário.
vol_minimo = st.sidebar.number_input(
    "Ocultar volumes com menos de X clientes:", 
    min_value=1, 
    value=5, 
    step=5,
    help="Remove os 'ruídos' (exceções e erros operacionais) para focar nas jornadas e motivos que afetam o grande volume."
)

# --- CARGA DOS DADOS ---
@st.cache_data
def carregar_e_processar_dados(arquivo):
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

if arquivo_upado is None:
    st.info("👋 Olá! Para iniciar a análise, realize o login e arraste o arquivo **safe_zendesk_tickets.parquet** na área indicada na barra lateral esquerda.")
    st.stop()

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

# CORREÇÃO AQUI: A tabela agora respeita o vol_minimo inserido na barra lateral!
df_taxa_motivo = df_taxa_motivo[df_taxa_motivo['Volume_Clientes'] >= vol_minimo].sort_values(by='Impacto no Retrabalho (%)', ascending=False)
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
    
    # CORREÇÃO AQUI: Aplica o volume mínimo de fato nos fluxos
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
    st.info("Volume insuficiente. Ajuste o Filtro de Relevância na barra lateral para um número menor.")

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
    st.info("Volume insuficiente. Ajuste o Filtro de Relevância na barra lateral para um número menor.")

st.markdown("---")

# ==============================================================================
# SEÇÃO 4: ANÁLISE INVERSA - MOTIVOS POR JORNADA
# ==============================================================================
st.header("4️⃣ Análise Inversa: Motivos por Fluxo de Jornada")
st.markdown("Selecione um caminho exato para descobrir quais assuntos empurraram o cliente para essa esteira.")

# CORREÇÃO AQUI: A lista suspensa só exibe jornadas que respeitam o volume mínimo
jornadas_filtradas = df_jornadas_completas['Jornada_Realizada'].value_counts()
jornadas_validas = jornadas_filtradas[jornadas_filtradas >= vol_minimo].index.tolist()

if not jornadas_validas:
    st.info("Nenhuma jornada alcançou o volume mínimo definido na barra lateral.")
else:
    jornada_selecionada = st.selectbox("📌 Filtrar por Jornada Específica:", jornadas_validas, key="sec4")

    df_sec4 = df_jornadas_completas[df_jornadas_completas['Jornada_Realizada'] == jornada_selecionada]
    total_clientes_jornada = len(df_sec4)

    df_ranking_jornada = df_sec4.groupby('Motivo_Inicial_Jornada').size().reset_index(name='Quantidade de Clientes')
    
    # CORREÇÃO AQUI: Aplica o volume mínimo nos motivos dentro desta jornada também
    df_ranking_jornada = df_ranking_jornada[df_ranking_jornada['Quantidade de Clientes'] >= vol_minimo]
    df_ranking_jornada = df_ranking_jornada.sort_values(by='Quantidade de Clientes', ascending=False)

    if df_ranking_jornada.empty:
        st.info("Não há motivos individuais suficientes para compor esse fluxo considerando o filtro atual.")
    else:
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
    * **% do Total da Operação (CPFs):** Perspectiva de volume macro. Shows qual é a relevância dessas pessoas frente a toda a base de clientes atendidos pela Tenda no período.
    """)


# ==============================================================================
# SEÇÃO 5: VISÃO EXECUTIVA - FLUXO OMNICHANNEL E KPIS
# ==============================================================================
import plotly.graph_objects as go 

st.header("5️⃣ Mapa de Jornada e KPIs de Retenção")
st.markdown("Visão executiva do comportamento de transbordo entre os canais de atendimento.")

# --- CÁLCULO DE KPIS GLOBAIS ---
media_canais_cpf = df.groupby('CPF_Limpo')['Canal de Entrada'].nunique().mean()

# Calcula porcentagem de clientes que precisaram usar mais de 1 canal
cpfs_multicanal = df.groupby('CPF_Limpo')['Canal de Entrada'].nunique()
taxa_transbordo = (cpfs_multicanal[cpfs_multicanal > 1].count() / total_clientes_global) * 100 if total_clientes_global > 0 else 0

# Calcula a pior rota de transbordo (A ➔ B)
pares_transbordo = []
for jornada in df.groupby('CPF_Limpo')['Canal de Entrada'].apply(list):
    j_limpa = []
    for c in jornada:
        if not j_limpa or c != j_limpa[-1]:
            j_limpa.append(c)
    if len(j_limpa) > 1:
        for i in range(len(j_limpa) - 1):
            pares_transbordo.append(f"{j_limpa[i]} ➔ {j_limpa[i+1]}")
            
if pares_transbordo:
    pior_rota = pd.Series(pares_transbordo).mode()[0]
else:
    pior_rota = "Nenhuma"

st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
col1.metric("Canais por CPF (Méd)", f"{media_canais_cpf:.1f}")
col2.metric("Clientes Multicanal", f"{taxa_transbordo:.1f}%", help="Percentual de clientes que foram forçados a trocar de canal ao menos uma vez.")
col3.metric("Maior Rota de Atrito", pior_rota, help="A rota de quebra de canal (Origem ➔ Destino) que possui o maior volume de clientes.")
st.markdown("<br>", unsafe_allow_html=True)

# --- FILTROS ESPECÍFICOS PARA O FLUXO ---
st.markdown("#### 🔍 Filtros do Fluxo de Transbordo")
col_filt1, col_filt2 = st.columns(2)
with col_filt1:
    filtro_visao_canais = st.selectbox(
        "Foco dos Canais:", 
        ["Apenas Principais (Voz, Whatsapp, E-mail)", "Ver Todos os Canais"]
    )
with col_filt2:
    lista_motivos = ["Todos (Geral)"] + df['Motivo_Inicial_Jornada'].dropna().unique().tolist()
    filtro_motivo_fluxo = st.selectbox("Filtrar por Motivo:", lista_motivos)

# --- PREPARAÇÃO DOS DADOS (SANKEY) ---
df_sec5 = df.copy()
if filtro_motivo_fluxo != "Todos (Geral)":
    df_sec5 = df_sec5[df_sec5['Motivo_Inicial_Jornada'] == filtro_motivo_fluxo]

transicoes = []
jornadas_list = df_sec5.groupby('CPF_Limpo')['Canal de Entrada'].apply(list)

canais_principais = ["VOZ", "WHATSAPP", "EMAIL", "E-MAIL"]

for jornada in jornadas_list:
    jornada_limpa = []
    for c in jornada:
        if filtro_visao_canais.startswith("Apenas"):
            eh_principal = any(principal in str(c).upper() for principal in canais_principais)
            nome_canal = c if eh_principal else "Outros Canais"
        else:
            nome_canal = c
            
        if not jornada_limpa or nome_canal != jornada_limpa[-1]:
            jornada_limpa.append(nome_canal)
            
    if len(jornada_limpa) > 1:
        for i in range(len(jornada_limpa) - 1):
            transicoes.append({'Origem': f"{jornada_limpa[i]} (Início)", 'Destino': f"{jornada_limpa[i+1]} (Destino)"})

df_fluxo = pd.DataFrame(transicoes)

# --- DESENHO DO GRÁFICO SANKEY ---
if not df_fluxo.empty:
    df_fluxo_agrupado = df_fluxo.groupby(['Origem', 'Destino']).size().reset_index(name='Volume')
    df_fluxo_agrupado = df_fluxo_agrupado[df_fluxo_agrupado['Volume'] >= vol_minimo]

    if not df_fluxo_agrupado.empty:
        todos_nos = list(pd.concat([df_fluxo_agrupado['Origem'], df_fluxo_agrupado['Destino']]).unique())
        mapeamento_nos = {nome: i for i, nome in enumerate(todos_nos)}
        
        df_fluxo_agrupado['Origem_ID'] = df_fluxo_agrupado['Origem'].map(mapeamento_nos)
        df_fluxo_agrupado['Destino_ID'] = df_fluxo_agrupado['Destino'].map(mapeamento_nos)
        
        fig = go.Figure(data=[go.Sankey(
            node = dict(
              pad = 20,
              thickness = 30,
              line = dict(color = "black", width = 0.5),
              label = todos_nos,
              color = "#1F618D"
            ),
            link = dict(
              source = df_fluxo_agrupado['Origem_ID'],
              target = df_fluxo_agrupado['Destino_ID'],
              value = df_fluxo_agrupado['Volume'],
              color = "rgba(46, 134, 193, 0.4)" 
            )
        )])
        
        fig.update_layout(title_text="", font_size=14, height=550)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Com o volume mínimo configurado na barra lateral, não há dados suficientes para exibir o fluxo.")
else:
    st.info("Não há transbordos registados para o filtro selecionado.")
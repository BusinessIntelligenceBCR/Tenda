# ==============================================================================
# SCRIPT 4: DASHBOARD OMNICHANNEL INTERATIVO COM TELA DE LOGIN E UPLOAD SENSÍVEL
# ==============================================================================
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
        st.markdown("Insira as suas credenciais para aceder ao ambiente de Governança Tenda.")
        
        col1, col2 = st.columns(2)
        with col1:
            usuario_digitado = st.text_input("Utilizador do Sistema:")
            senha_digitada = st.text_input("Senha de Acesso:", type="password")
            botao_login = st.button("Aceder ao Painel")
            
        if botao_login:
            if (usuario_digitado == st.secrets["acesso"]["usuario"] and 
                senha_digitada == st.secrets["acesso"]["senha"]):
                st.session_state["autenticado"] = True
                st.success("Acesso autorizado! A carregar dados...")
                st.rerun() 
            else:
                st.error("Utilizador ou senha incorretos. Tente novamente.")
        
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

# --- MAPEAR MESES GLOBAIS ---
dic_meses = {1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 
             7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'}
df['Num_Mes'] = df['Data_Ordenacao'].dt.month
df['Mês_Abrev'] = df['Num_Mes'].map(dic_meses)

# --- BARRA LATERAL: FILTROS GLOBAIS ---
st.sidebar.markdown("---")
st.sidebar.header("📅 Filtro Temporal (Visão Atual)")
meses_disponiveis = df[['Num_Mes', 'Mês_Abrev']].drop_duplicates().sort_values('Num_Mes')['Mês_Abrev'].tolist()
mes_filtro = st.sidebar.selectbox(
    "Analisar Mês Específico:", 
    ["Todos os Meses"] + meses_disponiveis,
    help="Este filtro atualiza as Seções 1 a 5. A Seção 6 sempre exibirá o histórico completo para comparação de cultura."
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Filtro de Relevância")
vol_minimo = st.sidebar.number_input(
    "Ocultar volumes com menos de X clientes:", 
    min_value=1, 
    value=5, 
    step=5,
    help="Remove os 'ruídos' operacionais para focar nas jornadas que afetam o grande volume."
)

# --- APLICAÇÃO DO FILTRO TEMPORAL NO DATAFRAME ATIVO ---
if mes_filtro == "Todos os Meses":
    df_ativo = df.copy()
else:
    df_ativo = df[df['Mês_Abrev'] == mes_filtro].copy()

if df_ativo.empty:
    st.warning("Não há tickets registados para o mês selecionado.")
    st.stop()

# ==============================================================================
# ENGENHARIA DE MÉTRICAS E JORNADAS COMPLETAS (BASEADO NO DF_ATIVO)
# ==============================================================================
df_cpfs = df_ativo.groupby('CPF_Limpo').agg({'Motivo_Inicial_Jornada': 'first', 'Ticket ID': 'count'}).reset_index()
df_cpfs['Teve_Recontato'] = (df_cpfs['Ticket ID'] > 1).astype(int)

total_recontatos_global = df_cpfs['Teve_Recontato'].sum()
total_clientes_global = df_cpfs['CPF_Limpo'].nunique()

df_taxa_motivo = df_cpfs.groupby('Motivo_Inicial_Jornada').agg(
    Volume_Clientes=('CPF_Limpo', 'count'), Total_Recontatos=('Teve_Recontato', 'sum')
).reset_index()

df_taxa_motivo['% do Total de Clientes'] = (df_taxa_motivo['Volume_Clientes'] / total_clientes_global * 100).round(2)
df_taxa_motivo['Taxa de Recontato (%)'] = (df_taxa_motivo['Total_Recontatos'] / df_taxa_motivo['Volume_Clientes'] * 100).round(2)
df_taxa_motivo['Impacto no Retrabalho (%)'] = (df_taxa_motivo['Total_Recontatos'] / total_recontatos_global * 100).round(2) if total_recontatos_global > 0 else 0

df_taxa_motivo = df_taxa_motivo[df_taxa_motivo['Volume_Clientes'] >= vol_minimo].sort_values(by='Impacto no Retrabalho (%)', ascending=False)
motivos_ordenados_por_impacto = df_taxa_motivo['Motivo_Inicial_Jornada'].tolist()

def construir_string_jornada(canais):
    caminho_limpo = []
    for c in canais:
        if not caminho_limpo or c != caminho_limpo[-1]:
            caminho_limpo.append(c)
    return " ➔ ".join(caminho_limpo)

df_jornadas_completas = df_ativo.groupby('CPF_Limpo').agg({
    'Canal de Entrada': construir_string_jornada,
    'Motivo_Inicial_Jornada': 'first'
}).reset_index().rename(columns={'Canal de Entrada': 'Jornada_Realizada'})

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
# SEÇÃO 1: VISÃO EXECUTIVA - FLUXO OMNICHANNEL E KPIS (Antiga Seção 5)
# ==============================================================================
st.header(f"1️⃣ Mapa de Jornada e KPIs de Retenção ({mes_filtro})")
st.markdown("Visão executiva do comportamento de transbordo entre os canais de atendimento no período selecionado.")

# --- CÁLCULO DE KPIS GLOBAIS ---
media_canais_cpf = df_ativo.groupby('CPF_Limpo')['Canal de Entrada'].nunique().mean()

cpfs_multicanal_count = df_ativo.groupby('CPF_Limpo')['Canal de Entrada'].nunique()
volume_clientes_transbordo = cpfs_multicanal_count[cpfs_multicanal_count > 1].count()
taxa_transbordo = (volume_clientes_transbordo / total_clientes_global) * 100 if total_clientes_global > 0 else 0

pares_transbordo = []
for jornada in df_ativo.groupby('CPF_Limpo')['Canal de Entrada'].apply(list):
    j_limpa = []
    for c in jornada:
        if not j_limpa or c != j_limpa[-1]:
            j_limpa.append(c)
    if len(j_limpa) > 1:
        for i in range(len(j_limpa) - 1):
            pares_transbordo.append(f"{j_limpa[i]} ➔ {j_limpa[i+1]}")
            
top1_str = "Nenhuma"
top23_html = ""
if pares_transbordo:
    total_transbordos_ocorridos = len(pares_transbordo)
    df_pares = pd.Series(pares_transbordo)
    top_3 = df_pares.value_counts().head(3)
    
    for i, (rota_nome, volume) in enumerate(top_3.items(), 1):
        percentual = (volume / total_transbordos_ocorridos) * 100 if total_transbordos_ocorridos > 0 else 0
        texto_rota = f"{rota_nome} ({percentual:.1f}%)"
        if i == 1:
            top1_str = texto_rota
        else:
            top23_html += f"<b>{i}º</b> {texto_rota}<br>"

st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 1, 2.5])
col1.metric("Canais por CPF (Méd)", f"{media_canais_cpf:.1f}")
col2.metric("Clientes Multicanal", f"{taxa_transbordo:.1f}%", help="Percentual de clientes únicos que foram forçados a usar 2 ou mais canais diferentes.")
with col3:
    st.metric("Maior Rota de Atrito", top1_str, help="As 3 maiores rotas de quebra de canal e a proporção de cada uma em relação ao total de transbordos.")
    if top23_html:
        st.markdown(f"<div style='margin-top:-15px; font-size:13px; color:gray;'>{top23_html}</div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# --- FILTROS ESPECÍFICOS PARA O FLUXO ---
st.markdown("#### 🔍 Filtros do Fluxo de Transbordo")
col_filt1, col_filt2, col_filt3 = st.columns(3)

lista_canais_unicos = sorted(df_ativo['Canal de Entrada'].dropna().unique().tolist())
canais_padrao = [c for c in lista_canais_unicos if c.upper() in ["VOZ", "WHATSAPP", "EMAIL", "E-MAIL"]]

with col_filt1:
    filtro_canal_inicio = st.multiselect("Filtrar Canal de Origem:", lista_canais_unicos, default=canais_padrao)
with col_filt2:
    filtro_canal_destino = st.multiselect("Filtrar Canal de Destino:", lista_canais_unicos, default=canais_padrao)
with col_filt3:
    lista_motivos = ["Todos (Geral)"] + df_ativo['Motivo_Inicial_Jornada'].dropna().unique().tolist()
    filtro_motivo_fluxo = st.selectbox("Filtrar por Motivo:", lista_motivos)

# --- PREPARAÇÃO DOS DADOS (SANKEY) ---
df_sec1_sankey = df_ativo.copy()
if filtro_motivo_fluxo != "Todos (Geral)":
    df_sec1_sankey = df_sec1_sankey[df_sec1_sankey['Motivo_Inicial_Jornada'] == filtro_motivo_fluxo]

transicoes = []

if filtro_canal_inicio and filtro_canal_destino:
    jornadas_list = df_sec1_sankey.groupby('CPF_Limpo')['Canal de Entrada'].apply(list)

    for jornada in jornadas_list:
        jornada_limpa = []
        for c in jornada:
            if not jornada_limpa or c != jornada_limpa[-1]:
                jornada_limpa.append(c)
                
        if len(jornada_limpa) > 1:
            for i in range(len(jornada_limpa) - 1):
                origem = jornada_limpa[i]
                destino = jornada_limpa[i+1]
                
                passa_origem = origem in filtro_canal_inicio
                passa_destino = destino in filtro_canal_destino
                
                if passa_origem and passa_destino:
                    transicoes.append({'Origem': f"{origem} (Início)", 'Destino': f"{destino} (Destino)"})

df_fluxo = pd.DataFrame(transicoes)

# --- DESENHO DO GRÁFICO SANKEY ---
if not df_fluxo.empty:
    df_fluxo_agrupado = df_fluxo.groupby(['Origem', 'Destino']).size().reset_index(name='Volume')
    df_fluxo_agrupado = df_fluxo_agrupado[df_fluxo_agrupado['Volume'] >= vol_minimo]

    if not df_fluxo_agrupado.empty:
        df_fluxo_agrupado['Total_Da_Origem'] = df_fluxo_agrupado.groupby('Origem')['Volume'].transform('sum')
        df_fluxo_agrupado['Porcentagem_Do_Fluxo'] = (df_fluxo_agrupado['Volume'] / df_fluxo_agrupado['Total_Da_Origem']) * 100

        nos_origem = df_fluxo_agrupado['Origem'].unique()
        nos_destino = df_fluxo_agrupado['Destino'].unique()
        todos_nos_puros = list(set(nos_origem).union(set(nos_destino)))
        mapeamento_nos = {nome: i for i, nome in enumerate(todos_nos_puros)}
        
        df_fluxo_agrupado['Origem_ID'] = df_fluxo_agrupado['Origem'].map(mapeamento_nos)
        df_fluxo_agrupado['Destino_ID'] = df_fluxo_agrupado['Destino'].map(mapeamento_nos)
        
        labels_com_valores = [""] * len(todos_nos_puros)
        for nome, idx in mapeamento_nos.items():
            if nome in nos_origem:
                total_bloco = df_fluxo_agrupado[df_fluxo_agrupado['Origem'] == nome]['Volume'].sum()
                labels_com_valores[idx] = f"<b>{nome}</b><br>Total: {total_bloco} CPFs"
            else:
                total_bloco = df_fluxo_agrupado[df_fluxo_agrupado['Destino'] == nome]['Volume'].sum()
                labels_com_valores[idx] = f"<b>{nome}</b><br>Total: {total_bloco} CPFs"
        
        fig = go.Figure(data=[go.Sankey(
            node = dict(
              pad = 18,
              thickness = 30,
              line = dict(color = "black", width = 0.5),
              label = labels_com_valores,
              color = "#1F618D"
            ),
            link = dict(
              source = df_fluxo_agrupado['Origem_ID'],
              target = df_fluxo_agrupado['Destino_ID'],
              value = df_fluxo_agrupado['Volume'],
              customdata = df_fluxo_agrupado['Porcentagem_Do_Fluxo'],
              color = "rgba(46, 134, 193, 0.35)",
              hovertemplate = (
                  "Origem: <b>%{source.label}</b><br>"
                  "Destino: <b>%{target.label}</b><br>"
                  "Volume: <b>%{value} CPFs</b><br>"
                  "Proporção: <b>%{customdata:.1f}%</b> de evasão para este canal<extra></extra>"
              )
            )
        )])
        
        fig.update_layout(title_text="", font_size=13, height=550)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Com o volume mínimo configurado na barra lateral, não há dados suficientes para exibir o fluxo.")
else:
    st.info("Não há transbordos registados para o filtro selecionado.")

st.markdown("---")

# ==============================================================================
# SEÇÃO 2: ANÁLISE COMPLETA POR CANAL INICIAL (Antiga Seção 1)
# ==============================================================================
st.header(f"2️⃣ Tendência de Fluxo por Canal Inicial ({mes_filtro})")
st.markdown("Selecione o canal de origem para analisar a esteira de transbordo utilizada pelos clientes.")

canais_contagem_s2 = df_ativo.groupby('Canal_Inicial_Jornada')['CPF_Limpo'].nunique().sort_values(ascending=False)
lista_canais_s2 = ["Todos (Visão Geral)"] + canais_contagem_s2.index.tolist()
canal_selecionado_s2 = st.selectbox("📌 Filtrar Canal de Origem:", lista_canais_s2, key="sec2_origem")

df_sec2 = df_ativo[df_ativo['Canal_Inicial_Jornada'] == canal_selecionado_s2] if canal_selecionado_s2 != "Todos (Visão Geral)" else df_ativo.copy()
grafico2, tb2 = desenhar_grafico_jornadas(df_sec2, f"Top Caminhos Percorridos - Iniciados em: {canal_selecionado_s2}", vol_minimo, "#1F618D")

if grafico2:
    st.plotly_chart(grafico2, use_container_width=True)
else:
    st.info("Volume insuficiente. Ajuste o Filtro de Relevância na barra lateral para um número menor.")

st.markdown("---")

# ==============================================================================
# SEÇÃO 3: MATRIZ DE ATRITO PROPORCIONAL (Antiga Seção 2)
# ==============================================================================
st.header(f"3️⃣ Diagnóstico de Atrito: Esforço Operacional ({mes_filtro})")
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
    Esta tabela identifica a verdadeira dor da operação. A contagem **não é feita por número de tickets**, mas sim por **CPFs únicos**.
    
    * **Total de Clientes:** A quantidade exata de CPFs únicos que iniciaram a sua jornada com este assunto.
    * **Qtd. Retornos:** Quantos clientes falharam em ter o problema resolvido de primeira e abriram 2 ou mais chamados.
    * **Taxa Interna (%):** A eficiência do assunto. Responde: *"Qual é a chance de um cliente que liga sobre este tema precisar voltar?"*
    * **Impacto Global (%):** Responde: *"De todo o retrabalho gerado, quantos % são culpa deste motivo isolado?"*. 
    """)

st.markdown("---")

# ==============================================================================
# SEÇÃO 4: ANÁLISE SETORIAL POR MOTIVO DE CONTATO (Antiga Seção 3)
# ==============================================================================
st.header(f"4️⃣ Análise de Transbordo por Motivo de Contato ({mes_filtro})")
st.markdown("Descubra as jornadas geradas por um motivo específico.")

lista_filtro_motivos_s4 = ["Todos (Visão Geral)"] + motivos_ordenados_por_impacto
motivo_selecionado_s4 = st.selectbox("📌 Filtrar por Motivo Específico:", lista_filtro_motivos_s4, key="sec4_motivo")

df_sec4 = df_ativo[df_ativo['Motivo_Inicial_Jornada'] == motivo_selecionado_s4] if motivo_selecionado_s4 != "Todos (Visão Geral)" else df_ativo.copy()
grafico4, tb4 = desenhar_grafico_jornadas(df_sec4, f"Top Caminhos Percorridos do Motivo: {motivo_selecionado_s4}", vol_minimo, "#884EA0")

if grafico4:
    st.plotly_chart(grafico4, use_container_width=True)
else:
    st.info("Volume insuficiente. Ajuste o Filtro de Relevância na barra lateral para um número menor.")

st.markdown("---")

# ==============================================================================
# SEÇÃO 5: ANÁLISE INVERSA - MOTIVOS POR JORNADA (Antiga Seção 4)
# ==============================================================================
st.header(f"5️⃣ Análise Inversa: Motivos por Fluxo de Jornada ({mes_filtro})")
st.markdown("Selecione um caminho exato para descobrir quais assuntos empurraram o cliente para essa esteira.")

jornadas_filtradas = df_jornadas_completas['Jornada_Realizada'].value_counts()
jornadas_validas = jornadas_filtradas[jornadas_filtradas >= vol_minimo].index.tolist()

if not jornadas_validas:
    st.info("Nenhuma jornada alcançou o volume mínimo definido na barra lateral.")
else:
    jornada_selecionada = st.selectbox("📌 Filtrar por Jornada Específica:", jornadas_validas, key="sec5_jornada")

    df_sec5_inv = df_jornadas_completas[df_jornadas_completas['Jornada_Realizada'] == jornada_selecionada]
    total_clientes_jornada = len(df_sec5_inv)

    df_ranking_jornada = df_sec5_inv.groupby('Motivo_Inicial_Jornada').size().reset_index(name='Quantidade de Clientes')
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

st.markdown("---")

# ==============================================================================
# SEÇÃO 6: EVOLUÇÃO HISTÓRICA MÊS A MÊS (ANÁLISE DE CULTURA DIGITAL)
# ==============================================================================
st.header("6️⃣ Evolução Mensal do Comportamento (Histórico Completo)")
st.markdown("Monitore a tendência histórica das rotas de transbordo para medir a mudança cultural do cliente ao longo de todos os meses analisados.")

transicoes_mensais = []
jornadas_por_mes = df.groupby(['CPF_Limpo', 'Mês_Abrev', 'Num_Mes'])['Canal de Entrada'].apply(list)

for (cpf, mes, num_mes), jornada in jornadas_por_mes.items():
    j_limpa = []
    for c in jornada:
        if not j_limpa or c != j_limpa[-1]:
            j_limpa.append(c)
    if len(j_limpa) > 1:
        for i in range(len(j_limpa) - 1):
            transicoes_mensais.append({
                'Mês': mes,
                'Num_Mes': num_mes,
                'Rota': f"{j_limpa[i]} ➔ {j_limpa[i+1]}"
            })

if transicoes_mensais:
    df_cronologico = pd.DataFrame(transicoes_mensais)
    
    df_tendencia = df_cronologico.groupby(['Num_Mes', 'Mês', 'Rota']).size().reset_index(name='Volume de Clientes')
    df_tendencia = df_tendencia.sort_values(by='Num_Mes')
    
    top_rotas_gerais = df_cronologico['Rota'].value_counts().head(5).index.tolist()
    rotas_existentes = df_cronologico['Rota'].unique()
    rota_alvo_sugerida = [r for r in rotas_existentes if "WHATSAPP" in r.upper() and "VOZ" in r.upper()]
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    opcao_visao_tempo = st.radio(
        "Selecione a perspectiva de análise temporal:",
        ["Top 5 Rotas de Maior Atrito Geral", "Isolar e Monitorar uma Rota Específica (Mudança Cultural)"],
        horizontal=True
    )
    
    if opcao_visao_tempo == "Top 5 Rotas de Maior Atrito Geral":
        df_grafico_tempo = df_tendencia[df_tendencia['Rota'].isin(top_rotas_gerais)]
        titulo_tempo = "Tendência Mensal das 5 Maiores Rotas de Transbordo (Volume Absoluto)"
    else:
        todas_rotas_disponiveis = sorted(df_cronologico['Rota'].unique())
        indice_padrao = todas_rotas_disponiveis.index(rota_alvo_sugerida[0]) if rota_alvo_sugerida else 0
        
        rota_selecionada_tempo = st.selectbox(
            "Escolha a rota de transbordo para auditoria de cultura:", 
            todas_rotas_disponiveis, 
            index=indice_padrao
        )
        df_grafico_tempo = df_tendencia[df_tendencia['Rota'] == rota_selecionada_tempo]
        titulo_tempo = f"Evolução Temporal do Comportamento Evasivo: {rota_selecionada_tempo}"
        
    fig_linha = px.line(
        df_grafico_tempo, 
        x='Mês', 
        y='Volume de Clientes', 
        color='Rota',
        markers=True,
        title=titulo_tempo,
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    
    fig_linha.update_layout(
        xaxis_title="Evolução Mensal", 
        yaxis_title="Volume de Clientes (CPFs)", 
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="left", x=0)
    )
    fig_linha.update_traces(line=dict(width=3), marker=dict(size=8))
    st.plotly_chart(fig_linha, use_container_width=True)
    
    with st.expander("📊 Visualizar Matriz de Dados Numéricos Proporcionais (MoM)"):
        df_pivot_tempo = df_tendencia.pivot(index='Rota', columns='Mês', values='Volume de Clientes').fillna(0).astype(int)
        colunas_ordenadas = [m for m in dic_meses.values() if m in df_pivot_tempo.columns]
        df_pivot_tempo = df_pivot_tempo[colunas_ordenadas]
        st.dataframe(df_pivot_tempo, use_container_width=True)
else:
    st.info("Não há dados de transbordo suficientes nos registos históricos para compor a análise temporal.")
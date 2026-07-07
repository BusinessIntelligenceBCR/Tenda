# ==============================================================================
# SCRIPT 6: EXTRATOR GERAL DA ZENDESK (PERÍODOS CUSTOMIZADOS)
# ==============================================================================
import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
import re

load_dotenv()

# --- CONFIGURAÇÕES DE PERÍODO E ACESSO ---
# Altere estas datas para o período curto que deseja extrair (Formato: YYYY-MM-DD)
DATA_INICIO = "2026-07-01"
DATA_FIM = "2026-07-06"

URL_ZENDESK = "tenda3527.zendesk.com" 
EMAIL = os.getenv("ZENDESK_EMAIL_MASTER")
TOKEN = os.getenv("ZENDESK_TOKEN_TENDA")

auth = (f"{EMAIL}/token", TOKEN)
url_base = f"https://{URL_ZENDESK.replace('https://', '').strip('/')}"

NOME_ARQUIVO_SAIDA = f"base_geral_zendesk_{DATA_INICIO}_a_{DATA_FIM}.parquet"

# --- MAPEAMENTO DE CAMPOS DA TENDA ---
ID_CPF_1 = "35552950044308"
ID_CPF_2 = "44634263918868"
IDS_CPFS = [ID_CPF_1, ID_CPF_2] 

ID_CANAL_ENTRADA = "33447993968660"
ID_MOTIVO_CONTATO = "33443012961300"
ID_IMPRODUTIVO = "34558918426004"

# Categorização exata das camadas (Níveis) conforme a regra da Tenda
IDS_NIVEL_2 = ["33443258674708", "33443700332308", "33444719484564", "33447369614484", "33447625386772"]
IDS_NIVEL_3 = ["33458144241940", "33865370675860", "33864528042644", "33864540439444", "33864826105748", "33864871025940", "33886243534356", "33443748074004", "33443783533716", "33444520472468", "33444552182932", "33446725088276", "33447356785940", "33446244824596", "33446668114964", "33446063999892", "33447576312852", "33447635141396", "33447712917396"]
IDS_NIVEL_4 = ["33864420942484", "33864459138452", "33864479056020", "33864176256020", "33864509585300", "33458341782164", "33458349894420", "33458223960724", "33458429608084", "33883535398292", "33883428929300", "33883756370580", "33884859672212", "33884848422676"]

# --- FUNÇÕES ÚTEIS E LIMPEZA ---
def extrair_numeros(texto):
    if pd.isna(texto): return ""
    return re.sub(r'\D', '', str(texto)).zfill(11)

def formatar_tag(valor):
    """Trata strings, listas de tags (multiselect) e valores nulos de forma segura"""
    if valor is None: return ""
    if isinstance(valor, list):
        valores_limpos = [str(v).replace("_", " ").strip().title() for v in valor if v]
        return " - ".join(valores_limpos)
    if isinstance(valor, (str, int, float)) and pd.isna(valor): return ""
    return str(valor).replace("_", " ").strip().title()

def inclui_tags(ticket_tags, tags_procuradas):
    return any(tag in ticket_tags for tag in tags_procuradas)

# --- A REGRA DE NEGÓCIO DA TENDA ---
def classificar_motivo_tenda(ticket):
    campos = {str(c['id']): c.get('value') for c in ticket.get('custom_fields', [])}
    tags = ticket.get('tags', [])
    n1_cru = campos.get(ID_MOTIVO_CONTATO)
    
    # 1. Motivo Unificado
    if n1_cru and str(n1_cru).strip().lower() not in ["none", "null", ""]:
        cadeia = [formatar_tag(n1_cru)]
        for id_n2 in IDS_NIVEL_2:
            val_n2 = campos.get(id_n2)
            if val_n2 is not None and str(val_n2).strip().lower() not in ["none", "null", ""]:
                cadeia.append(formatar_tag(val_n2))
                break
        for id_n3 in IDS_NIVEL_3:
            val_n3 = campos.get(id_n3)
            if val_n3 is not None and str(val_n3).strip().lower() not in ["none", "null", ""]:
                cadeia.append(formatar_tag(val_n3))
                break
        for id_n4 in IDS_NIVEL_4:
            val_n4 = campos.get(id_n4)
            if val_n4 is not None and str(val_n4).strip().lower() not in ["none", "null", ""]:
                cadeia.append(formatar_tag(val_n4))
                break
        return " > ".join(cadeia)
        
    # 2. Motivo por Tag
    if inclui_tags(tags, ["agendar-entrega", "cancelar-entrega", "entrega-chave-agendamento-com-possibilidade-reagendar", "entrega-chave-agendamento-sem-possibilidade-reagendar", "entrega-chave-nao-permitido-por-limite", "entrega-chave-nao-permitido", "entrega-chave-permitido", "entrega-chaves", "erro-cancelar-automatico-entrega-chave", "erro-cancelar-entrega", "erro-entrega-chave-consulta-data", "erro-entrega-chave-data", "erro-entrega-chave-status-condicional", "erro-entrega-chave-status", "erro-entrega-chave", "reagendar-entrega", "reagendar-limite-atingido-entrega-chaves"]): return "CRM > Entrega das chaves > Liberação de agendamento"
    if inclui_tags(tags, ["agendar-vistoria", "cancelar-vistoria", "erro-agendar-vistoria", "erro-cancelar-vistoria", "erro-consulta-datas-disponiveis-vistoria", "erro-escolhe-horario-vistoria", "erro-marcar-horario-vistoria", "erro-reagendar-vistoria", "erro-vistoria-consulta", "vistoria", "vistoria-agendada-nao-pode-reagendar", "vistoria-agendada-pode-reagendar", "vistoria-nao-permitida", "vistoria-permitida"]): return "Obras > Vistoria > Vistoria de entrega"
    if inclui_tags(tags, ["baixa-pagamento-mais-5-dias", "baixa-pagamento-menos-5-dias"]): return "Financeiro > CAR > Baixa de pagamento"
    if inclui_tags(tags, ["baixar-fatura", "entenda-seu-boleto-duvida", "fatura-mais-antiga-erro", "fatura-mais-recente-erro"]): return "Financeiro > CAR > Boleto"
    if inclui_tags(tags, ["cancelamento"]): return "Ciclo Financeiro > Reversão de Distratos > Cancelamento / Distrato"
    if inclui_tags(tags, ["contrato"]): return "Ciclo Financeiro > Contratos > Compra e venda"
    if inclui_tags(tags, ["erro-api-gape", "erro-assistencia-tecnica-encerrar-atendimento", "erro-assistencia-tecnica-falar-atendente"]): return "Assistência Técnica"
    if inclui_tags(tags, ["nao-pode-reagendar"]): return "CRM > Assembleia > Entrega da obra"
    if inclui_tags(tags, ["sindico"]): return "Financeiro > Cobrança > Negociação"

    # 3. Improdutivo
    improdutivo = campos.get(ID_IMPRODUTIVO)
    if improdutivo is not None and str(improdutivo).strip().lower() not in ["none", "null", ""]: 
        return f"Improdutivo > {formatar_tag(improdutivo)}"
        
    return "Não classificado"

# --- MOTOR DE EXTRAÇÃO ---
print(f"📥 Iniciando extração da Zendesk para o período de {DATA_INICIO} até {DATA_FIM}...")
url = f"{url_base}/api/v2/search/export.json"
query = f"created>={DATA_INICIO} created<={DATA_FIM}"
params = {'query': query, 'filter[type]': 'ticket', 'page[size]': 1000}
tickets_baixados = []

while True:
    response = requests.get(url, auth=auth, params=params)
    if response.status_code == 429:
        print("⏳ Limite da API atingido. Aguardando 10 segundos...")
        time.sleep(10)
        continue
    if response.status_code != 200:
        print(f"❌ Erro na extração: {response.text}")
        break
        
    dados = response.json()
    tickets = dados.get('results', [])
    if not tickets: break
    
    for t in tickets:
        campos_ticket = {str(c['id']): c.get('value') for c in t.get('custom_fields', [])}
        
        # Procura por qualquer CPF preenchido neste ticket
        cpf_valido = None
        for id_cpf in IDS_CPFS:
            num = extrair_numeros(campos_ticket.get(id_cpf, ""))
            if len(num) == 11: 
                cpf_valido = num
                break # Achou um CPF válido, pode parar de procurar nos outros campos
        
        # O ticket só entra na base final se tiver um CPF atrelado a ele (para a jornada funcionar)
        if cpf_valido:
            data_completa = t.get('created_at', 'Não informado').replace('T', ' ').replace('Z', '')
            motivo_bruto = classificar_motivo_tenda(t)
            canal_bruto = campos_ticket.get(ID_CANAL_ENTRADA, "Não Informado")
            
            tickets_baixados.append({
                'CPF_Limpo': cpf_valido, 
                'Ticket ID': t['id'],
                'Data_Ordenacao': data_completa, 
                'Canal de Entrada': canal_bruto, 
                'Motivo de Contato': motivo_bruto
            })
                
    meta = dados.get('meta', {})
    if not meta.get('has_more'): break
    params['page[after]'] = meta.get('after_cursor')
    print(f"✅ Total mapeado na fila: {len(tickets_baixados)} tickets...")

# Salva o arquivo local
if tickets_baixados:
    df = pd.DataFrame(tickets_baixados)
    df.to_parquet(NOME_ARQUIVO_SAIDA, index=False)
    print(f"\n💾 Sucesso! Foram extraídos {len(df)} tickets com CPF no período.")
    print(f"Arquivo salvo como: '{NOME_ARQUIVO_SAIDA}'")
else:
    print(f"\n⚠️ Nenhum ticket com CPF preenchido foi encontrado entre {DATA_INICIO} e {DATA_FIM}.")
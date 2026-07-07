# ==============================================================================
# SCRIPT 5: ANONIMIZAÇÃO DE DADOS SENSÍVEIS (LGPD)
# ==============================================================================
import pandas as pd
import hashlib
import os

ARQUIVO_ORIGINAL = "base_geral_zendesk_2026-07-01_a_2026-07-06.parquet"
ARQUIVO_SEGURO = "base_safe_zendesk_2026-07-01_a_2026-07-06.parquet"

print("🔒 Iniciando processo de anonimização de CPFs (LGPD)...")

if not os.path.exists(ARQUIVO_ORIGINAL):
    print(f"❌ Arquivo {ARQUIVO_ORIGINAL} não encontrado.")
    exit()

df = pd.read_parquet(ARQUIVO_ORIGINAL)

def mascarar_cpf(cpf):
    if pd.isna(cpf) or not str(cpf).strip():
        return "CLI-DESCONHECIDO"
    
    # Gera um hash criptográfico irreversível (SHA-256)
    hash_obj = hashlib.sha256(str(cpf).encode('utf-8'))
    
    # Retorna os 8 primeiros caracteres do hash (Ex: CLI-A1B2C3D4)
    return f"CLI-{hash_obj.hexdigest()[:8].upper()}"

print("⚙️ Criptografando coluna 'CPF_Limpo'...")
df['CPF_Limpo'] = df['CPF_Limpo'].apply(mascarar_cpf)

df.to_parquet(ARQUIVO_SEGURO, index=False)
print(f"✅ Sucesso! Base segura gerada: '{ARQUIVO_SEGURO}'.")
print("Pode compartilhar este arquivo sem medo na nuvem.")
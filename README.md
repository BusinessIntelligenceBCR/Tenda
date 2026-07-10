📊 Governança Omnichannel - Tenda (BCR CX)

Um ecossistema completo de extração, tratamento e visualização de dados focado em Customer Experience (CX). Este projeto foi desenvolvido para auditar e analisar o fluxo de transbordo e quebra de canais (Voz, WhatsApp, E-mail, etc.) dos clientes da Tenda na Zendesk, transformando um mar de tickets brutos num painel executivo interativo.

🎯 Objetivo do Projeto

A operação de atendimento enfrenta desafios de retenção e "First Call Resolution" (FCR). Clientes iniciam o contacto por um canal (ex: WhatsApp) e, não tendo o seu problema resolvido, desviam para outro canal (ex: Voz), gerando retrabalho, alto custo operacional e insatisfação.

Este projeto visa responder a três perguntas críticas:

Qual é o tamanho do problema? (Quantos CPFs únicos precisam transbordar?)

Quais são as piores rotas? (De onde os clientes vêm e para onde fogem?)

Qual é a causa raiz? (Quais os motivos da Zendesk que forçam esse desvio?)

🏗 Arquitetura da Solução

O projeto segue um pipeline de dados (ETL) robusto, dividindo a engenharia de dados da visualização:

Extração (Extract): Scripts conectam-se à API da Zendesk via Token para descarregar o histórico de tickets (filtrados por uma base de CPFs ou por um período específico).

Transformação (Transform): Regras de negócio complexas aplicadas em Pandas para classificar níveis de contato, higienizar nomes de canais (Regex) e agrupar múltiplos tickets num único "Caminho de Jornada" por cliente.

Carga (Load): Os dados tratados são salvos no formato colunar .parquet, garantindo compressão e leitura super-rápida.

Visualização (Data Viz): Um Dashboard interativo em Streamlit consome a base Parquet, renderizando gráficos Sankey, tabelas de impacto e tendências temporais.

🚀 Como Executar o Projeto

Pré-requisitos

Python instalado (versão 3.9 ou superior).

Dependências instaladas: pip install pandas streamlit plotly requests python-dotenv openpyxl xlsxwriter fastparquet

Um arquivo .env na raiz do seu diretório (C:\Data Warehouse) com as credenciais da Zendesk:

ZENDESK_EMAIL_MASTER=seu_email_admin@dominio.com
ZENDESK_TOKEN_TENDA=seu_token_de_api


Rodando a Aplicação

O projeto é modular. Pode rodar a extração ou apenas o painel.

Para rodar o Dashboard Executivo:
Navegue até a pasta do projeto e inicie o Streamlit:

cd "C:\Data Warehouse\Tenda\Analises\Busca_CPFs"
streamlit run 04-painel_interativo_tenda.py


O painel exigirá um login (configurado via secrets.toml do Streamlit) e o upload do arquivo safe_zendesk_tickets.parquet.

Para gerar auditoria Excel:

python 07-extrator_auditoria_rotas.py


📂 Estrutura de Diretórios e Scripts

Para um mergulho profundo no papel de cada arquivo de código, consulte a nossa documentação técnica:
👉 Guia dos Scripts e Pipeline de Dados

✨ Principais Funcionalidades do Dashboard

Controlo de Acesso: Sistema de autenticação nativo e injeção de base de dados sensível via Drag & Drop.

Sankey Diagram Dinâmico: Visualização do fluxo direcional entre canais (Origem ➔ Destino) com filtros independentes.

Matriz de Atrito: Tabela calculada por Impacto Global (%), isolando o motivo que mais causa retrabalho na operação.

Análise Inversa: Permite selecionar uma Rota exata (Ex: Formulário ➔ E-mail) e descobrir os top assuntos associados a essa quebra.

Monitorização MoM (Month-over-Month): Gráfico de linhas para avaliação de mudança de cultura e efetividade de novas políticas.

Desenvolvido para revolucionar a Governança e a Cultura Digital na Tenda.
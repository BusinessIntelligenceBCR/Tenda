📖 Guia Técnico: Pipeline de Dados e Scripts

Este documento detalha o propósito e o funcionamento interno de cada script desenvolvido para a análise de Governança Omnichannel da Tenda. A modularidade permite atualizar ou debugar partes isoladas do processo sem quebrar a aplicação final.

🔄 O Pipeline Principal

01-extrator_cpfs_zendesk.py (ou similar, do início do projeto)

Função: Extrair dados em massa.

Como funciona: Lê um arquivo base com uma lista de CPFs da Tenda, faz um loop chamando a API da Zendesk (/api/v2/search/export.json) e traz todos os tickets atrelados a esses CPFs específicos, ignorando o ruído geral da plataforma.

02-tratamento_e_classificacao.py (ou similar)

Função: Aplicar as regras de negócio da árvore da Tenda.

Como funciona: O "coração" lógico do projeto. Ele mapeia os Custom Fields da Zendesk (Nível 1, 2, 3, etc.), trata as tags complexas da Zendesk (ex: agendamento de vistoria, entrega de chaves) e consolida o verdadeiro "Motivo de Contato". Exporta o arquivo final limpo: safe_zendesk_tickets.parquet.

📊 Aplicações de Visualização e Auditoria

04-painel_interativo_tenda.py

Função: Frontend e Data Visualization.

Como funciona: É a aplicação Streamlit.

Possui tela de login rígida.

Agrupa os tickets isolados transformando-os em Jornadas de Cliente (Canal A ➔ Canal B ➔ Canal C).

Constrói todas as seções: Visão Executiva (com Top 3 Rotas em HTML injetado), Gráfico de Sankey com filtros direcionais de multiseleção, Tendências MoM (Mês a Mês), Matrizes de Esforço Operacional e Análise Inversa.

06-extrator_geral_zendesk.py

Função: Extrator Independente por Período.

Como funciona: Ao contrário da primeira extração que dependia de uma planilha do Excel, este script é livre. Você define variáveis DATA_INICIO e DATA_FIM (ex: últimos 30 dias). Ele consome a API da Zendesk iterando sobre todas as páginas de resultados e devolve um novo arquivo .parquet focado na visão temporal geral. Excelente para reuniões mensais de fechamento de resultados.

Nota: Requer que as variáveis de ambiente ZENDESK_EMAIL_MASTER (com nível Admin) e ZENDESK_TOKEN_TENDA estejam bem configuradas num arquivo .env.

07-extrator_auditoria_rotas.py

Função: Ferramenta de Deep Dive e Auditoria de Qualidade (QA).

Como funciona: Funciona como a "lupa" do projeto.

Carrega o safe_zendesk_tickets.parquet.

Mapeia os caminhos de todos os clientes.

Isola as Top 15 rotas mais críticas da operação (ex: "Whatsapp ➔ Voz").

Extrai todo o histórico dos CPFs que realizaram essas rotas e gera um arquivo Auditoria_Rotas_Zendesk.xlsx.

Cada aba do Excel recebe o nome de uma rota.

Uso Prático: A equipe de qualidade abre a aba "Não Informado", copia os IDs dos Tickets diretamente do Excel, cola na barra de pesquisa da Zendesk e pode auditar por que razão os agentes não estão classificando corretamente as chamadas ou os canais.

🛠 Bibliotecas e Ferramentas Fundamentais

Pandas: O motor de todas as manipulações matemáticas, joins e reconstruções de jornada.

Plotly (plotly.express e plotly.graph_objects): Responsável pela renderização elegante e interativa do Gráfico de Barras e do complexo Sankey Diagram.

XlsxWriter: Motor embutido no Pandas (engine='xlsxwriter') usado no script 07 para garantir auto-ajuste de colunas e criação segura de múltiplas abas no Excel.

Streamlit: Framework ágil que transforma o script Python numa Web App de uso corporativo instantâneo.
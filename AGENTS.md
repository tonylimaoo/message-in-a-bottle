# AGENTS

Documenta rapidamente o que cada “agente” do sistema faz e como eles conversam entre si. Mantém o time alinhado sobre responsabilidades e pontos de integração.

## Visão geral
- **Objetivo**: gerar diariamente uma tabela de análise de outliers no BigQuery (BQ) e notificar no Slack quando houver flags de anomalia.
- **Stack principal**: BigQuery + Cloud Scheduler + Cloud Functions (Node/Python) + Slack Webhook/App.
- **Entrada**: dados já carregados em BQ (particionamento diário recomendado por `DATE`/`TIMESTAMP`).
- **Saída**: mensagem formatada no Slack com métricas afetadas e links para inspeção.

## Agentes e responsabilidades
- **Agente Produtor (Job de geração de tabela BQ)**  
  - Executa diariamente (p.ex. via Airflow, Dataform ou outro orquestrador).  
  - Cria/atualiza a tabela `analytics.outlier_snapshot_YYYYMMDD`.  
  - Calcula métricas e escreve colunas booleanas/numéricas que indicam outliers (ex.: `is_outlier_latency`, `zscore_error_rate`).  
  - Garante schema estável e partição por data para leitura eficiente.

- **Agente Scheduler (Cloud Scheduler)**  
  - Dispara a Cloud Function uma vez por dia após a conclusão do produtor (sugestão: +15 min de margem).  
  - Envia payload mínimo (timestamp da janela) ou apenas aciona a função via HTTP.

- **Agente Analisador/Notifier (Cloud Function)**  
  - Lê a partição/tabela do dia no BQ.  
  - Seleciona linhas com flags de outlier (`WHERE is_outlier_* = TRUE` ou z-score acima de limiar).  
  - Compõe mensagem concisa: métrica, valor, limite, contexto temporal, link para BQ console ou Looker.  
  - Publica no Slack via Incoming Webhook ou Slack App token (`chat.postMessage`).  
  - Idempotência: marcar envio com `date` e `run_id` para evitar duplicidade em reprocessamentos.

## Fluxo diário (happy path)
1) Produtor escreve `analytics.outlier_snapshot_YYYYMMDD`.  
2) Cloud Scheduler aciona a função às `HH:MM` (UTC ou horário local definido).  
3) Cloud Function consulta BQ, filtra outliers, formata payload e envia ao Slack.  
4) Logs no Cloud Logging para auditoria; erros geram alerta secundário (p.ex. Slack canal de erro).

## Contratos de dados (sugestão de schema)
- `event_date` (DATE) — partição.  
- Métricas numéricas: `latency_ms`, `error_rate`, `throughput`, …  
- Colunas de detecção: `zscore_latency`, `is_outlier_latency` (BOOL), etc.  
- Campos de contexto: `service`, `region`, `environment`, `observed_at` (TIMESTAMP).  
- Índice/cluster em (`event_date`, `service`).

## Parametrizações úteis
- `OUTLIER_ZSCORE_THRESHOLD` (ex.: 3.0).  
- `MIN_VOLUME_THRESHOLD` para ignorar baixa amostragem.  
- `SLACK_WEBHOOK_URL` ou `SLACK_BOT_TOKEN` + `SLACK_CHANNEL`.  
- `BQ_PROJECT`, `BQ_DATASET`, `TABLE_PREFIX`.  
- `NOTIFY_ONLY_ON_FIRST_OUTLIER=true` para evitar spam.

## Segurança e operação
- Segredos em Secret Manager (Slack token, webhook).  
- Service Account com papéis mínimos: `roles/bigquery.dataViewer` no dataset e `roles/secretmanager.secretAccessor` no secret.  
- Observabilidade: logs estruturados e métrica de contagem de mensagens enviadas; alerta se função falhar N vezes.  
- Testar função localmente com `functions-framework` e um dataset de teste.

## Próximos passos sugeridos
- Definir qual motor gerará a tabela diária (Airflow/Dataform) e padronizar nome de dataset.  
- Criar a Cloud Function inicial com variáveis de ambiente acima e um message template de Slack.  
- Adicionar testes unitários para a lógica de formatação de mensagem e filtragem de outliers.

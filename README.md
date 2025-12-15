# Message in a Bottle 📨

Cloud Run / Cloud Functions (Gen2) job that lê outliers no BigQuery (dia anterior), gera um resumo e **publica o payload no Pub/Sub**. Outra função/worker pode consumir o tópico e postar no Slack ou onde você quiser. Não há endpoint para enviar mensagens personalizadas; só health check.

## Quick start (Docker local)
```bash
docker build -t message-in-a-bottle .
docker run -d -p 8080:8080 \
  -e AUTO_SEND_ENABLED=true \
  -e AUTO_SEND_INTERVAL_SEC=60 \
  -e BQ_VIEW=barber-project-d75f8.teste_slack.calculo_outliers \
  -e PUBSUB_TOPIC=<seu-topico> \
  -e GCP_PROJECT_ID=<seu-projeto> \
  message-in-a-bottle
# health check (não envia nada)
curl http://localhost:8080/
```

## Deploy to Cloud Run (Dockerfile)
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/message-in-a-bottle
gcloud run deploy message-in-a-bottle \
  --image gcr.io/PROJECT_ID/message-in-a-bottle \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars FUNCTION_TARGET=slack_notify,FUNCTION_SIGNATURE_TYPE=http,\
PUBSUB_TOPIC=<seu-topico>,GCP_PROJECT_ID=<seu-projeto>,\
AUTO_SEND_ENABLED=true,AUTO_SEND_INTERVAL_SEC=60,\
BQ_VIEW=barber-project-d75f8.teste_slack.calculo_outliers
```

## Environment variables
- `AUTO_SEND_ENABLED` (default `true`): inicia o loop de publicação.
- `AUTO_SEND_INTERVAL_SEC` (default `60`): intervalo em segundos entre execuções.
- `BQ_VIEW` (default `barber-project-d75f8.teste_slack.calculo_outliers`): view lida; sempre o dia anterior (`CURRENT_DATE() - 1`).
- `PUBSUB_TOPIC` (ou `send-alert-topic-name`): tópico Pub/Sub para publicar o payload.
- `GCP_PROJECT_ID` (ou `gcp-project-id`/`GOOGLE_CLOUD_PROJECT`): projeto para construir o topic path.
- `BQ_LOOKBACK_DAYS` (legacy; não usado).
- `AUTO_SEND_TEXT` (legacy; não usado na mensagem final).

## Formato do payload publicado
```json
{
  "entidade": "Outliers Diario",
  "data_referencia": "dd/mm/aaaa",
  "outliers": [
    {
      "origem": "facebook / cpc",
      "metricas": [
        {"nome": "cpm", "direcao": "up", "ratio": 1.015}
      ]
    }
  ],
  "resumo": "Outliers (dd/mm/aaaa):\n- facebook / cpc:\n    🔺 cpm (ratio 1.015)"
}
```

## HTTP usage
- `GET /` → health/status only.

## Notas
- O loop roda em cada instância. Em produção, prefira Cloud Scheduler chamando apenas uma instância/serviço para evitar mensagens duplicadas.
- Garanta permissões: service account com `roles/bigquery.dataViewer` e `roles/pubsub.publisher` no projeto.

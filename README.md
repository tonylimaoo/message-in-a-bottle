# Message in a Bottle 📨

Cloud Run / Cloud Functions (Gen2) service that sends messages to Slack via webhook.
Messages are sent only by the background loop (no custom messages via HTTP).

## Quick start (Docker local)
```bash
docker build -t message-in-a-bottle .
docker run -d -p 8080:8080 \
  -e SLACK_WEBHOOK=https://hooks.slack.com/services/... \
  -e AUTO_SEND_ENABLED=true \
  message-in-a-bottle
# health check (does not send)
curl http://localhost:8080/
```

Enable periodic sends (every 60s by default):
```bash
docker run -d -p 8080:8080 \
  -e SLACK_WEBHOOK=https://hooks.slack.com/services/... \
  -e AUTO_SEND_ENABLED=true \
  -e AUTO_SEND_INTERVAL_SEC=60 \
  -e AUTO_SEND_TEXT="Ping automático" \
  message-in-a-bottle
```

## Deploy to Cloud Run (Dockerfile)
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/message-in-a-bottle
gcloud run deploy message-in-a-bottle \
  --image gcr.io/PROJECT_ID/message-in-a-bottle \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars SLACK_WEBHOOK=https://hooks.slack.com/services/...,FUNCTION_TARGET=slack_notify,FUNCTION_SIGNATURE_TYPE=http,AUTO_SEND_ENABLED=true
```

## Environment variables
- `SLACK_WEBHOOK` **(required)**: full Slack incoming webhook URL.
- `AUTO_SEND_ENABLED` (default `true`): `true` to start background loop.
- `AUTO_SEND_INTERVAL_SEC` (default `60`): interval in seconds for auto loop.
- `AUTO_SEND_TEXT` (default "Hello from Cloud Run Functions! 🚀 (auto)"): text sent by the loop.

## HTTP usage
- `GET /` → health/status only (no message is sent).

## Notes
- Auto-send loop runs per instance. In production prefer Cloud Scheduler + HTTP trigger to avoid duplicate sends across multiple instances.
- Uses Functions Framework; honors `PORT` env automatically.

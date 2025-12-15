"""
HTTP function for Cloud Run / Cloud Functions (Gen2) that posts a message to Slack.

Entry point (FUNCTION_TARGET): slack_notify
Handles GET (mensagem padrão) e POST with JSON {"text": "..."}.
"""

import os
import json
import requests  # kept for compatibility; no direct Slack send now
import functions_framework
import threading
import time
from google.cloud import bigquery
from google.cloud import pubsub_v1

# Env vars
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")  # not used anymore; kept for compatibility
AUTO_SEND_ENABLED = os.getenv("AUTO_SEND_ENABLED", "true").lower() == "true"
AUTO_SEND_INTERVAL_SEC = int(os.getenv("AUTO_SEND_INTERVAL_SEC", "60"))
AUTO_SEND_TEXT = os.getenv("AUTO_SEND_TEXT", "Hello from Cloud Run Functions! 🚀 (auto)")
BQ_VIEW = os.getenv("BQ_VIEW", "barber-project-d75f8.teste_slack.calculo_outliers")
BQ_LOOKBACK_DAYS = int(os.getenv("BQ_LOOKBACK_DAYS", "10"))  # unused now; kept for compatibility
PUBSUB_TOPIC = os.getenv("PUBSUB_TOPIC") or os.getenv("send-alert-topic-name")
GCP_PROJECT_ID = (
    os.getenv("gcp-project-id")
    or os.getenv("GCP_PROJECT_ID")
    or os.getenv("GOOGLE_CLOUD_PROJECT")
)


def send_slack(text: str):
    # Validate only when called
    if not SLACK_WEBHOOK or not SLACK_WEBHOOK.startswith("https://hooks.slack.com/"):
        raise ValueError("Configure a env SLACK_WEBHOOK com o webhook do Slack.")
    resp = requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    resp.raise_for_status()
    return resp.text


@functions_framework.http
def slack_notify(request):
    """Health endpoint only; sending is driven by the background loop."""
    return {"status": "alive", "auto_send_enabled": AUTO_SEND_ENABLED}, 200


def fetch_outliers():
    """Query BigQuery view for outliers in the lookback window."""
    client = bigquery.Client()
    sql = f"""
    SELECT *
    FROM `{BQ_VIEW}`
    WHERE date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
    ORDER BY date DESC
    """
    rows = client.query(sql).result()
    schema_fields = [f.name for f in rows.schema]
    flag_cols = [c for c in schema_fields if c.startswith("is_outlier_")]
    results = []
    for row in rows:
        metrics = []
        for c in flag_cols:
            if getattr(row, c):
                metric = c.replace("is_outlier_", "")
                ratio_col = f"ratio_{metric}"
                ratio_val = getattr(row, ratio_col, None)
                direction = "up" if ratio_val is not None and ratio_val > 1 else "down"
                metrics.append(
                    {"metric": metric, "ratio": ratio_val, "direction": direction}
                )
        if metrics:
            results.append({"date": row.date, "origem": row.origem, "metrics": metrics})
    return results


def format_outlier_message(outliers):
    if not outliers:
        return "Nenhum outlier no dia anterior."
    # All rows are for yesterday; capture the date from the first item
    ref_date = outliers[0]["date"]
    date_str = ref_date.strftime("%d/%m/%Y") if hasattr(ref_date, "strftime") else str(ref_date)
    # Agrupa métricas por origem para facilitar leitura
    grouped = {}
    for item in outliers:
        grouped.setdefault(item["origem"], []).extend(item["metrics"])

    lines = [f"Outliers ({date_str}):"]
    for origem in sorted(grouped.keys()):
        lines.append(f"- {origem}:")
        for m in grouped[origem]:
            ratio_txt = f"{m['ratio']:.3f}" if isinstance(m["ratio"], (int, float)) else "n/a"
            arrow = "🔺" if m["direction"] == "up" else "🔻"
            lines.append(f"    {arrow} {m['metric']} (ratio {ratio_txt})")
    return "\n".join(lines)


def build_payload(outliers):
    """Builds a JSON-serializable payload to publish to Pub/Sub."""
    if not outliers:
        return {
            "entidade": "Outliers Diario",
            "data_referencia": None,
            "outliers": [],
            "resumo": "Nenhum outlier no dia anterior.",
        }
    ref_date = outliers[0]["date"]
    date_str = ref_date.strftime("%d/%m/%Y") if hasattr(ref_date, "strftime") else str(ref_date)
    payload_outliers = []
    for item in outliers:
        payload_outliers.append(
            {
                "origem": item["origem"],
                "metricas": [
                    {"nome": m["metric"], "direcao": m["direction"], "ratio": m["ratio"]}
                    for m in item["metrics"]
                ],
            }
        )
    resumo = format_outlier_message(outliers)
    return {
        "entidade": "Outliers Diario",
        "data_referencia": date_str,
        "outliers": payload_outliers,
        "resumo": resumo,
    }


def publish_to_pubsub(payload: dict):
    """Publish JSON payload to Pub/Sub topic."""
    if not PUBSUB_TOPIC or not GCP_PROJECT_ID:
        raise ValueError("PUBSUB_TOPIC ou GCP_PROJECT_ID não configurado.")
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GCP_PROJECT_ID, PUBSUB_TOPIC)
    data_bytes = json.dumps(payload).encode("utf-8")
    future = publisher.publish(topic_path, data=data_bytes)
    msg_id = future.result()
    print(f"Payload publicado no Pub/Sub (topic={PUBSUB_TOPIC}, msg_id={msg_id})")
    return msg_id


def _auto_loop():
    """Background loop to send a Slack message periodically."""
    while True:
        try:
            outliers = fetch_outliers()
            payload = build_payload(outliers)
            publish_to_pubsub(payload)
        except Exception as exc:
            # Log to stdout; Cloud Run captures logs
            print(f"[auto-loop] error sending slack: {exc}", flush=True)
        time.sleep(AUTO_SEND_INTERVAL_SEC)


# Start background sender if enabled
if AUTO_SEND_ENABLED:
    t = threading.Thread(target=_auto_loop, name="auto-slack-loop", daemon=True)
    t.start()


if __name__ == "__main__":
    # Local/dev fallback: run the functions framework dev server
    from functions_framework import create_app

    app = create_app("main.slack_notify")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

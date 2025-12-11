"""
HTTP function for Cloud Run / Cloud Functions (Gen2) that posts a message to Slack.

Entry point (FUNCTION_TARGET): slack_notify
Handles GET (mensagem padrão) e POST com JSON {"text": "..."}.
"""

import os
import requests
import functions_framework
import threading
import time
from google.cloud import bigquery

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")
AUTO_SEND_ENABLED = os.getenv("AUTO_SEND_ENABLED", "true").lower() == "true"
AUTO_SEND_INTERVAL_SEC = int(os.getenv("AUTO_SEND_INTERVAL_SEC", "60"))
AUTO_SEND_TEXT = os.getenv("AUTO_SEND_TEXT", "Hello from Cloud Run Functions! 🚀 (auto)")
BQ_VIEW = os.getenv("BQ_VIEW", "barber-project-d75f8.teste_slack.calculo_outliers")
BQ_LOOKBACK_DAYS = int(os.getenv("BQ_LOOKBACK_DAYS", "10"))


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
    WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
    ORDER BY date DESC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", BQ_LOOKBACK_DAYS)
        ]
    )
    rows = client.query(sql, job_config=job_config).result()
    schema_fields = [f.name for f in rows.schema]
    flag_cols = [c for c in schema_fields if c.startswith("is_outlier_")]
    results = []
    for row in rows:
        metrics = [c.replace("is_outlier_", "") for c in flag_cols if getattr(row, c)]
        if metrics:
            results.append({"date": row.date, "metrics": metrics})
    return results


def format_outlier_message(outliers):
    if not outliers:
        return f"Nenhum outlier nos últimos {BQ_LOOKBACK_DAYS} dias."
    lines = [f"Outliers (últimos {BQ_LOOKBACK_DAYS} dias):"]
    for item in outliers:
        metrics_list = ", ".join(item["metrics"])
        lines.append(f"- {item['date']}: {metrics_list}")
    return "\n".join(lines)


def _auto_loop():
    """Background loop to send a Slack message periodically."""
    while True:
        try:
            outliers = fetch_outliers()
            text = format_outlier_message(outliers)
            send_slack(text)
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

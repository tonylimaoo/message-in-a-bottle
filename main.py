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

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")
AUTO_SEND_ENABLED = os.getenv("AUTO_SEND_ENABLED", "false").lower() == "true"
AUTO_SEND_INTERVAL_SEC = int(os.getenv("AUTO_SEND_INTERVAL_SEC", "60"))
AUTO_SEND_TEXT = os.getenv("AUTO_SEND_TEXT", "Hello from Cloud Run Functions! 🚀 (auto)")


def send_slack(text: str):
    # Validate only when called
    if not SLACK_WEBHOOK or not SLACK_WEBHOOK.startswith("https://hooks.slack.com/"):
        raise ValueError("Configure a env SLACK_WEBHOOK com o webhook do Slack.")
    resp = requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    resp.raise_for_status()
    return resp.text


@functions_framework.http
def slack_notify(request):
    body = request.get_json(silent=True) or {}
    custom_text = body.get("text") if isinstance(body, dict) else None
    text = custom_text or "Hello from Cloud Run Functions! 🚀"
    try:
        send_slack(text)
        return {"status": "ok", "sent": text}, 200
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, 500


def _auto_loop():
    """Background loop to send a Slack message periodically."""
    while True:
        try:
            send_slack(AUTO_SEND_TEXT)
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

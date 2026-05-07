import requests

from .settings import normalize_webhook_url


def send_lead(webhook_url, lead):
    webhook_url = normalize_webhook_url(webhook_url)
    if not webhook_url:
        return False, "Falta WEBHOOK_URL."
    try:
        response = requests.post(webhook_url, json=lead, timeout=20)
        response.raise_for_status()
        return True, "Lead enviado."
    except requests.RequestException as exc:
        return False, f"Error enviando lead: {exc}"

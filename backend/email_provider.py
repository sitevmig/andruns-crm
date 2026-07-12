import os
import requests

RESEND_URL = "https://api.resend.com/emails"


class EmailNotConfigured(Exception):
    pass


def email_configured() -> bool:
    provider = os.environ.get("EMAIL_PROVIDER", "resend").lower()
    if provider == "resend":
        return bool(os.environ.get("RESEND_API_KEY"))
    return False


def send_email(to: str, subject: str, html: str, text: str, from_addr: str, reply_to: str = None) -> str:
    """Provider abstraction. Returns provider message id. Raises on failure (no simulation)."""
    provider = os.environ.get("EMAIL_PROVIDER", "resend").lower()
    if provider == "resend":
        return _send_resend(to, subject, html, text, from_addr, reply_to)
    raise EmailNotConfigured(f"Неизвестный email-провайдер: {provider}")


def _send_resend(to, subject, html, text, from_addr, reply_to) -> str:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise EmailNotConfigured("Не задан RESEND_API_KEY в переменных окружения backend.")
    payload = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "html": html or f"<p>{text}</p>",
        "text": text or "",
    }
    if reply_to:
        payload["reply_to"] = reply_to
    resp = requests.post(RESEND_URL, json=payload,
                         headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Resend API error {resp.status_code}: {resp.text}")
    return resp.json().get("id", "")

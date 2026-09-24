import os
import re
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
import requests

RESEND_URL = "https://api.resend.com/emails"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailNotConfigured(Exception):
    pass


class InvalidEmailAddress(Exception):
    pass


def _validate_to(to: str) -> str:
    to = (to or "").strip()
    if not _EMAIL_RE.match(to):
        raise InvalidEmailAddress(f"Некорректный email получателя: {to!r}")
    return to


def email_configured() -> bool:
    provider = os.environ.get("EMAIL_PROVIDER", "resend").lower()
    if provider == "resend":
        return bool(os.environ.get("RESEND_API_KEY"))
    if provider == "smtp":
        return bool(os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))
    return False


def send_email(to: str, subject: str, html: str, text: str, from_addr: str, reply_to: str = None) -> str:
    """Provider abstraction. Returns provider message id. Raises on failure (no simulation)."""
    provider = os.environ.get("EMAIL_PROVIDER", "resend").lower()
    if provider == "resend":
        return _send_resend(to, subject, html, text, from_addr, reply_to)
    if provider == "smtp":
        return _send_smtp(to, subject, html, text, from_addr, reply_to)
    raise EmailNotConfigured(f"Неизвестный email-провайдер: {provider}")


def _send_resend(to, subject, html, text, from_addr, reply_to) -> str:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise EmailNotConfigured("Не задан RESEND_API_KEY в переменных окружения backend.")
    to = _validate_to(to)
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


def _send_smtp(to, subject, html, text, from_addr, reply_to) -> str:
    """Send via a real mailbox's own SMTP server (e.g. mail.ru), authenticating as
    that mailbox. Unlike Resend, this needs no domain verification — it sends as
    the actual account you log in with, so From should be that same address."""
    host = os.environ.get("SMTP_HOST", "smtp.mail.ru")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if not user or not password:
        raise EmailNotConfigured("Не заданы SMTP_USER и SMTP_PASSWORD в переменных окружения backend.")
    to = _validate_to(to)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(text or "", "plain", "utf-8"))
    msg.attach(MIMEText(html or f"<p>{text}</p>", "html", "utf-8"))

    envelope_from = parseaddr(from_addr)[1] or user
    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(user, password)
            server.sendmail(envelope_from, [to], msg.as_string())
    except smtplib.SMTPException as e:
        raise RuntimeError(f"Ошибка SMTP ({host}:{port}): {e}")
    return f"smtp-{uuid.uuid4().hex[:12]}"

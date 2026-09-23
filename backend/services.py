from database import db
from helpers import now_iso


async def log_change(org_id: str, ctype: str, description: str, admin: str = ""):
    await db.changes.insert_one({
        "org_id": org_id, "type": ctype, "description": description,
        "admin": admin, "at": now_iso(),
    })


async def log_message(org_id: str, channel: str, direction: str, text: str,
                      template_id=None, delivery_status="", error="",
                      admin="", external_id=""):
    doc = {
        "org_id": org_id, "channel": channel, "direction": direction, "text": text,
        "template_id": template_id, "delivery_status": delivery_status, "error": error,
        "admin": admin, "external_id": external_id, "at": now_iso(),
    }
    res = await db.messages.insert_one(doc)
    return str(res.inserted_id)


def sender_from_addr(s: dict) -> str:
    """Build the RFC 5322 'From' header value from settings. Raises ValueError if unset."""
    import os
    name = s.get("sender_name") or "CRM Andruns"
    email = s.get("sender_email") or os.environ.get("EMAIL_FROM_ADDRESS", "")
    if not email:
        raise ValueError("Не задан адрес отправителя (Настройки → Email).")
    return f"{name} <{email}>"


async def get_settings() -> dict:
    s = await db.settings.find_one({"_id": "global"})
    if not s:
        s = default_settings()
        await db.settings.insert_one(s)
    return s


def default_settings() -> dict:
    return {
        "_id": "global",
        "crm_name": "CRM Холодных Продаж",
        "timezone": "Europe/Moscow",
        "date_format": "DD.MM.YYYY",
        "email_enabled": True,
        "telegram_enabled": True,
        "sending_stopped": False,
        "default_template_id": None,
        "sender_name": "Отдел продаж",
        "sender_email": "vmig.ai@mail.ru",
        "reply_to": "vmig.ai@mail.ru",
        "signature": "С уважением, команда веб-студии.",
        "email_provider": "mock",
        "retry_max_attempts": 3,
        "telegram_connected": False,
        "telegram_phone": "",
        "telegram_status": "Не подключен",
    }

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from database import db
from security import get_current_user
from services import get_settings
from constants import (
    STATUS_NEW, STATUS_READY, STATUS_SENT, STATUS_REPLIED, STATUS_INTERESTED,
    STATUS_REJECTED, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_DELIVERY_ERROR,
    Q_WAITING, Q_SCHEDULED,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(user: dict = Depends(get_current_user)):
    async def count(q):
        return await db.organizations.count_documents(q)

    total = await count({})
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week = (now - timedelta(days=7)).isoformat()

    sent_today = await db.messages.count_documents({"direction": "outgoing", "delivery_status": "Отправлено", "at": {"$gte": today}})
    sent_week = await db.messages.count_documents({"direction": "outgoing", "delivery_status": "Отправлено", "at": {"$gte": week}})

    settings = await get_settings()
    queue_count = await db.queue.count_documents({"status": {"$in": [Q_WAITING, Q_SCHEDULED]}})

    stats = {
        "total": total,
        "new": await count({"status": STATUS_NEW}),
        "ready": await count({"status": STATUS_READY}),
        "sent_today": sent_today,
        "sent_week": sent_week,
        "replied": await count({"status": STATUS_REPLIED}),
        "interested": await count({"status": STATUS_INTERESTED}),
        "rejected": await count({"status": STATUS_REJECTED}),
        "in_progress": await count({"status": STATUS_IN_PROGRESS}),
        "errors": await count({"status": STATUS_DELIVERY_ERROR}),
        "queue_count": queue_count,
        "telegram_connected": settings.get("telegram_connected", False),
        "telegram_status": settings.get("telegram_status", "Не подключен"),
        "email_enabled": settings.get("email_enabled", True),
        "telegram_enabled": settings.get("telegram_enabled", True),
        "sending_stopped": settings.get("sending_stopped", False),
    }

    imported = total
    funnel = {
        "imported": imported,
        "sent": await db.organizations.count_documents({"last_message_at": {"$nin": [None, ""]}}),
        "replied": await count({"status": STATUS_REPLIED}),
        "interested": await count({"status": STATUS_INTERESTED}),
        "in_progress": await count({"status": STATUS_IN_PROGRESS}),
        "done": await count({"status": STATUS_DONE}),
    }
    return {"stats": stats, "funnel": funnel}

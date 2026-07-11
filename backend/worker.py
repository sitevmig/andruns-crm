import uuid
from bson import ObjectId
from database import db
from helpers import now_iso, render_template
from services import log_message, log_change, get_settings
from constants import (
    CHANNEL_EMAIL, CHANNEL_TELEGRAM, STATUS_SENT, STATUS_DELIVERY_ERROR,
    Q_SENT, Q_ERROR, Q_SENDING, Q_SKIPPED, Q_BLOCKED, Q_WAITING, Q_SCHEDULED,
)


async def process_task(task: dict, settings: dict) -> str:
    """Process a single queue task (mock sending). Returns queue status."""
    tid = task["_id"]
    org = await db.organizations.find_one({"_id": ObjectId(task["org_id"])})
    if not org:
        await db.queue.update_one({"_id": tid}, {"$set": {"status": Q_SKIPPED, "last_error": "Организация удалена"}})
        return Q_SKIPPED
    if org.get("do_not_contact"):
        await db.queue.update_one({"_id": tid}, {"$set": {"status": Q_BLOCKED, "last_error": "Организация в списке «Не связываться»"}})
        return Q_BLOCKED

    channel = task["channel"]
    if channel == CHANNEL_EMAIL and not settings.get("email_enabled"):
        await db.queue.update_one({"_id": tid}, {"$set": {"status": Q_BLOCKED, "last_error": "Email-рассылка отключена"}})
        return Q_BLOCKED
    if channel == CHANNEL_TELEGRAM and not settings.get("telegram_enabled"):
        await db.queue.update_one({"_id": tid}, {"$set": {"status": Q_BLOCKED, "last_error": "Telegram-рассылка отключена"}})
        return Q_BLOCKED

    tpl = await db.templates.find_one({"_id": ObjectId(task["template_id"])}) if task.get("template_id") else None
    if not tpl:
        await db.queue.update_one({"_id": tid}, {"$set": {"status": Q_ERROR, "last_error": "Шаблон не найден", "attempts": task.get("attempts", 0) + 1}})
        return Q_ERROR

    extra = {"manager_name": task.get("created_by", "")}
    text = render_template(tpl.get("body", ""), org, extra)
    subject = render_template(tpl.get("subject", ""), org, extra)

    error = None
    if channel == CHANNEL_EMAIL:
        if not org.get("email"):
            error = "У организации отсутствует email"
    else:
        if not settings.get("telegram_connected"):
            error = "Telegram-аккаунт не подключен"
        elif not org.get("telegram"):
            error = "У организации отсутствует Telegram"

    await db.queue.update_one({"_id": tid}, {"$set": {"status": Q_SENDING}})

    if error:
        await db.queue.update_one({"_id": tid}, {"$set": {
            "status": Q_ERROR, "last_error": error, "attempts": task.get("attempts", 0) + 1}})
        await log_message(task["org_id"], channel, "outgoing", text, tpl.get("_id") and str(tpl["_id"]),
                          "Ошибка", error, task.get("created_by", ""))
        await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"status": STATUS_DELIVERY_ERROR, "updated_at": now_iso()}})
        await log_change(task["org_id"], "delivery_error", f"Ошибка доставки ({channel}): {error}", task.get("created_by", ""))
        return Q_ERROR

    # MOCK SEND — simulated delivery
    ext_id = f"mock-{channel}-{uuid.uuid4().hex[:10]}"
    await log_message(task["org_id"], channel, "outgoing", (subject + "\n\n" + text) if channel == CHANNEL_EMAIL else text,
                      str(tpl["_id"]), "Отправлено", "", task.get("created_by", ""), ext_id)
    await db.queue.update_one({"_id": tid}, {"$set": {"status": Q_SENT, "external_id": ext_id, "sent_at": now_iso(), "last_error": ""}})
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": {
        "status": STATUS_SENT, "last_channel": channel, "last_message_at": now_iso(), "updated_at": now_iso()}})
    await log_change(task["org_id"], "message", f"Отправлено сообщение ({channel})", task.get("created_by", ""))
    return Q_SENT


async def process_queue(limit: int = 100) -> dict:
    settings = await get_settings()
    if settings.get("sending_stopped"):
        return {"processed": 0, "stopped": True}
    now = now_iso()
    query = {"$or": [
        {"status": Q_WAITING},
        {"status": Q_SCHEDULED, "scheduled_at": {"$lte": now}},
    ]}
    tasks = await db.queue.find(query).limit(limit).to_list(limit)
    result = {"processed": 0, "sent": 0, "error": 0, "blocked": 0, "skipped": 0}
    for t in tasks:
        # re-check global stop each iteration
        s = await get_settings()
        if s.get("sending_stopped"):
            break
        status = await process_task(t, s)
        result["processed"] += 1
        if status == Q_SENT:
            result["sent"] += 1
        elif status == Q_ERROR:
            result["error"] += 1
        elif status == Q_BLOCKED:
            result["blocked"] += 1
        elif status == Q_SKIPPED:
            result["skipped"] += 1
    return result

import uuid
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from database import db
from helpers import now_iso, serialize_list
from security import get_current_user
from services import get_settings
from worker import process_queue, start_campaign, stop_campaign, campaign_status
from constants import (
    CHANNEL_EMAIL, CHANNEL_TELEGRAM, Q_WAITING, Q_SCHEDULED, Q_CANCELLED, Q_ERROR,
    STATUS_DNC, STATUS_SCHEDULED,
)

router = APIRouter(prefix="/api/queue", tags=["queue"])

CAMPAIGN_MAX_RECIPIENTS = 10


class EnqueueBody(BaseModel):
    org_ids: List[str]
    channel: str
    template_id: str
    scheduled_at: Optional[str] = None


@router.get("")
async def list_queue(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if status:
        q["status"] = status
    tasks = await db.queue.find(q).sort("created_at", -1).to_list(500)
    # enrich with org name + template name
    out = serialize_list(tasks)
    org_ids = list({t["org_id"] for t in tasks})
    orgs = await db.organizations.find({"_id": {"$in": [ObjectId(i) for i in org_ids]}}).to_list(1000)
    org_map = {str(o["_id"]): o.get("name", "") for o in orgs}
    tpl_ids = list({t.get("template_id") for t in tasks if t.get("template_id")})
    tpls = await db.templates.find({"_id": {"$in": [ObjectId(i) for i in tpl_ids]}}).to_list(500)
    tpl_map = {str(t["_id"]): t.get("name", "") for t in tpls}
    for t in out:
        t["org_name"] = org_map.get(t["org_id"], "—")
        t["template_name"] = tpl_map.get(t.get("template_id"), "—")
    return out


@router.post("/enqueue")
async def enqueue(body: EnqueueBody, user: dict = Depends(get_current_user)):
    if body.channel not in (CHANNEL_EMAIL, CHANNEL_TELEGRAM):
        raise HTTPException(status_code=400, detail="Недопустимый канал")
    tpl = await db.templates.find_one({"_id": ObjectId(body.template_id)})
    if not tpl:
        raise HTTPException(status_code=400, detail="Шаблон не найден")
    added, skipped = 0, 0
    for oid in body.org_ids:
        org = await db.organizations.find_one({"_id": ObjectId(oid)})
        if not org or org.get("do_not_contact"):
            skipped += 1
            continue
        # avoid active duplicate task on same contact+channel
        existing = await db.queue.find_one({"org_id": oid, "channel": body.channel,
                                            "status": {"$in": [Q_WAITING, Q_SCHEDULED]}})
        if existing:
            skipped += 1
            continue
        task = {
            "_id": str(uuid.uuid4()), "org_id": oid, "channel": body.channel,
            "template_id": body.template_id, "scheduled_at": body.scheduled_at,
            "status": Q_SCHEDULED if body.scheduled_at else Q_WAITING,
            "attempts": 0, "last_error": "", "created_by": user["email"], "created_at": now_iso(),
        }
        await db.queue.insert_one(task)
        added += 1
    return {"added": added, "skipped": skipped}


class BulkIds(BaseModel):
    ids: List[str]


@router.post("/remove")
async def remove_from_queue(body: BulkIds, user: dict = Depends(get_current_user)):
    """Cancel queue tasks for given organizations (pending only)."""
    await db.queue.update_many(
        {"org_id": {"$in": body.ids}, "status": {"$in": [Q_WAITING, Q_SCHEDULED]}},
        {"$set": {"status": Q_CANCELLED, "last_error": "Исключено из очереди"}},
    )
    return {"ok": True}


@router.delete("/{task_id}")
async def cancel_task(task_id: str, user: dict = Depends(get_current_user)):
    await db.queue.update_one({"_id": task_id}, {"$set": {"status": Q_CANCELLED}})
    return {"ok": True}


@router.post("/process")
async def process_now(user: dict = Depends(get_current_user)):
    # Iteration 1: no simulated sending and no mass send. Real sending is done
    # per-client via /api/email/send and /api/telegram/send. Queue-based mass
    # dispatch will be wired to the real integrations in iteration 2 (with managers).
    raise HTTPException(
        status_code=400,
        detail="Массовая обработка очереди отключена в этой версии. Отправляйте по одному через карточку клиента (email/Telegram). Массовая рассылка будет включена вместе с ролями менеджеров.",
    )


@router.post("/stop-all")
async def stop_all(user: dict = Depends(get_current_user)):
    await db.settings.update_one({"_id": "global"}, {"$set": {"sending_stopped": True}}, upsert=True)
    return {"ok": True, "sending_stopped": True}


@router.post("/resume")
async def resume(user: dict = Depends(get_current_user)):
    await db.settings.update_one({"_id": "global"}, {"$set": {"sending_stopped": False}}, upsert=True)
    return {"ok": True, "sending_stopped": False}


@router.post("/stop-email")
async def stop_email(user: dict = Depends(get_current_user)):
    await db.settings.update_one({"_id": "global"}, {"$set": {"email_enabled": False}}, upsert=True)
    return {"ok": True}


@router.post("/stop-telegram")
async def stop_telegram(user: dict = Depends(get_current_user)):
    await db.settings.update_one({"_id": "global"}, {"$set": {"telegram_enabled": False}}, upsert=True)
    return {"ok": True}


@router.post("/clear-pending")
async def clear_pending(user: dict = Depends(get_current_user)):
    res = await db.queue.update_many(
        {"status": {"$in": [Q_WAITING, Q_SCHEDULED]}},
        {"$set": {"status": Q_CANCELLED, "last_error": "Очищено вручную"}},
    )
    return {"ok": True, "count": res.modified_count}


@router.post("/retry-errors")
async def retry_errors(user: dict = Depends(get_current_user)):
    res = await db.queue.update_many(
        {"status": Q_ERROR},
        {"$set": {"status": Q_WAITING, "last_error": ""}},
    )
    return {"ok": True, "count": res.modified_count}


class StartCampaignBody(BaseModel):
    org_ids: List[str]
    template_id: str


@router.post("/start-campaign")
async def start_campaign_route(body: StartCampaignBody, user: dict = Depends(get_current_user)):
    """Send an email template to up to CAMPAIGN_MAX_RECIPIENTS clients, one at a
    time, three minutes apart ('Начать рассылку')."""
    if campaign_status()["running"]:
        raise HTTPException(status_code=409, detail="Рассылка уже выполняется. Дождитесь окончания или остановите её.")
    if not body.org_ids:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одного клиента.")
    if len(body.org_ids) > CAMPAIGN_MAX_RECIPIENTS:
        raise HTTPException(status_code=400, detail=f"Можно выбрать не более {CAMPAIGN_MAX_RECIPIENTS} клиентов за один запуск.")
    tpl = await db.templates.find_one({"_id": ObjectId(body.template_id)})
    if not tpl or tpl.get("channel") != CHANNEL_EMAIL:
        raise HTTPException(status_code=400, detail="Выберите email-шаблон в разделе «Шаблоны».")

    task_ids = []
    skipped = 0
    for oid in body.org_ids:
        org = await db.organizations.find_one({"_id": ObjectId(oid)})
        if not org or org.get("do_not_contact") or not org.get("email"):
            skipped += 1
            continue
        existing = await db.queue.find_one({"org_id": oid, "channel": CHANNEL_EMAIL,
                                            "status": {"$in": [Q_WAITING, Q_SCHEDULED]}})
        if existing:
            skipped += 1
            continue
        tid = str(uuid.uuid4())
        await db.queue.insert_one({
            "_id": tid, "org_id": oid, "channel": CHANNEL_EMAIL,
            "template_id": body.template_id, "scheduled_at": None, "status": Q_WAITING,
            "attempts": 0, "last_error": "", "created_by": user["email"], "created_at": now_iso(),
        })
        task_ids.append(tid)

    if not task_ids:
        raise HTTPException(status_code=400, detail="Нет подходящих клиентов для рассылки (проверьте email и список «Не связываться»).")

    await db.settings.update_one({"_id": "global"}, {"$set": {"sending_stopped": False}}, upsert=True)
    start_campaign(task_ids)
    return {"ok": True, "started": len(task_ids), "skipped": skipped}


@router.post("/stop-campaign")
async def stop_campaign_route(user: dict = Depends(get_current_user)):
    stop_campaign()
    await db.queue.update_many(
        {"status": {"$in": [Q_WAITING, Q_SCHEDULED]}},
        {"$set": {"status": Q_CANCELLED, "last_error": "Рассылка остановлена вручную"}},
    )
    await db.settings.update_one({"_id": "global"}, {"$set": {"sending_stopped": True}}, upsert=True)
    return {"ok": True}


@router.get("/campaign-status")
async def campaign_status_route(user: dict = Depends(get_current_user)):
    return campaign_status()

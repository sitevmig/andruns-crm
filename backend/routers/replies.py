from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import db
from helpers import now_iso, serialize_list
from security import get_current_user
from services import log_change
from constants import STATUS_SENT, STATUS_REPLIED, CHANNEL_TELEGRAM

router = APIRouter(prefix="/api/replies", tags=["replies"])


@router.get("")
async def list_replies(user: dict = Depends(get_current_user)):
    docs = await db.messages.find({"direction": "incoming"}).sort("at", -1).to_list(500)
    out = serialize_list(docs)
    org_ids = [ObjectId(m["org_id"]) for m in out if m.get("org_id")]
    orgs = await db.organizations.find({"_id": {"$in": org_ids}}).to_list(1000)
    org_map = {str(o["_id"]): o for o in orgs}
    for m in out:
        o = org_map.get(m.get("org_id"))
        m["org_name"] = o.get("name") if o else "—"
        m["org_status"] = o.get("status") if o else None
    return out


@router.get("/unread-count")
async def unread_count(user: dict = Depends(get_current_user)):
    n = await db.messages.count_documents({"direction": "incoming", "read": {"$ne": True}})
    return {"count": n}


class SimulateReply(BaseModel):
    org_id: str
    text: str
    channel: str = CHANNEL_TELEGRAM


@router.post("/simulate")
async def simulate_reply(body: SimulateReply, user: dict = Depends(get_current_user)):
    """Register an incoming reply (used for Telegram inbound / demo)."""
    org = await db.organizations.find_one({"_id": ObjectId(body.org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    await db.messages.insert_one({
        "org_id": body.org_id, "channel": body.channel, "direction": "incoming",
        "text": body.text, "template_id": None, "delivery_status": "Получено",
        "error": "", "admin": "", "external_id": f"in-{now_iso()}", "at": now_iso(), "read": False,
    })
    upd = {"last_reply_at": now_iso(), "updated_at": now_iso()}
    if org.get("status") == STATUS_SENT:
        upd["status"] = STATUS_REPLIED
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": upd})
    await log_change(body.org_id, "reply", f"Получен входящий ответ ({body.channel})", "")
    return {"ok": True}


@router.post("/{msg_id}/read")
async def mark_read(msg_id: str, user: dict = Depends(get_current_user)):
    await db.messages.update_one({"_id": ObjectId(msg_id)}, {"$set": {"read": True}})
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.messages.update_many({"direction": "incoming"}, {"$set": {"read": True}})
    return {"ok": True}

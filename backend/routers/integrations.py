from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from database import db
from helpers import now_iso
from security import get_current_user
from services import get_settings, log_message
from constants import CHANNEL_EMAIL, CHANNEL_TELEGRAM

router = APIRouter(prefix="/api", tags=["integrations"])


# ---------------- Telegram (MOCK MTProto) ----------------
class TgConnect(BaseModel):
    phone: str
    api_id: Optional[str] = ""
    api_hash: Optional[str] = ""


@router.get("/telegram/status")
async def telegram_status(user: dict = Depends(get_current_user)):
    s = await get_settings()
    errors = await db.telegram_errors.find({}, {"_id": 0}).sort("at", -1).to_list(50)
    return {
        "connected": s.get("telegram_connected", False),
        "status": s.get("telegram_status", "Не подключен"),
        "phone": s.get("telegram_phone", ""),
        "enabled": s.get("telegram_enabled", True),
        "errors": errors,
    }


@router.post("/telegram/connect")
async def telegram_connect(body: TgConnect, user: dict = Depends(get_current_user)):
    # MOCK: real implementation would run MTProto auth in a persistent worker
    await get_settings()
    await db.settings.update_one({"_id": "global"}, {"$set": {
        "telegram_connected": True, "telegram_phone": body.phone,
        "telegram_status": "Подключен (демо-режим)",
    }})
    return {"ok": True, "status": "Подключен (демо-режим)"}


@router.post("/telegram/disconnect")
async def telegram_disconnect(user: dict = Depends(get_current_user)):
    await db.settings.update_one({"_id": "global"}, {"$set": {
        "telegram_connected": False, "telegram_status": "Не подключен",
    }})
    return {"ok": True}


@router.post("/telegram/check")
async def telegram_check(user: dict = Depends(get_current_user)):
    s = await get_settings()
    return {"ok": s.get("telegram_connected", False),
            "status": s.get("telegram_status", "Не подключен")}


class TgTest(BaseModel):
    to: str
    text: str = "Тестовое сообщение из CRM"


@router.post("/telegram/test")
async def telegram_test(body: TgTest, user: dict = Depends(get_current_user)):
    s = await get_settings()
    if not s.get("telegram_connected"):
        raise HTTPException(status_code=400, detail="Telegram-аккаунт не подключен")
    return {"ok": True, "message": f"Тестовое сообщение отправлено на {body.to} (демо-режим)"}


# ---------------- Email (MOCK provider abstraction) ----------------
class EmailTest(BaseModel):
    to: str
    subject: str = "Тестовое письмо CRM"
    text: str = "Это тестовое письмо из CRM."


@router.post("/email/test")
async def email_test(body: EmailTest, user: dict = Depends(get_current_user)):
    s = await get_settings()
    # MOCK: provider abstraction — replace with SMTP/SendGrid/Resend later
    return {"ok": True,
            "message": f"Тестовое письмо отправлено на {body.to} через провайдер «{s.get('email_provider','mock')}» (демо-режим)"}


class EmailSend(BaseModel):
    org_id: str
    subject: str
    text: str


@router.post("/email/send")
async def email_send(body: EmailSend, user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"_id": ObjectId(body.org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    if org.get("do_not_contact"):
        raise HTTPException(status_code=400, detail="Организация в списке «Не связываться»")
    if not org.get("email"):
        raise HTTPException(status_code=400, detail="У организации отсутствует email")
    ext = f"mock-email-{now_iso()}"
    await log_message(body.org_id, CHANNEL_EMAIL, "outgoing", body.subject + "\n\n" + body.text,
                      None, "Отправлено", "", user["email"], ext)
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": {
        "status": "Отправлено", "last_channel": CHANNEL_EMAIL, "last_message_at": now_iso(), "updated_at": now_iso()}})
    return {"ok": True, "external_id": ext}

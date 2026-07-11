from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from database import db
from helpers import now_iso
from security import get_current_user
from services import get_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    crm_name: Optional[str] = None
    timezone: Optional[str] = None
    date_format: Optional[str] = None
    email_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    default_template_id: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    reply_to: Optional[str] = None
    signature: Optional[str] = None
    email_provider: Optional[str] = None
    retry_max_attempts: Optional[int] = None


@router.get("")
async def read_settings(user: dict = Depends(get_current_user)):
    s = await get_settings()
    s["id"] = s.pop("_id")
    return s


@router.put("")
async def update_settings(body: SettingsUpdate, user: dict = Depends(get_current_user)):
    await get_settings()
    upd = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if upd:
        await db.settings.update_one({"_id": "global"}, {"$set": upd}, upsert=True)
    s = await get_settings()
    s["id"] = s.pop("_id")
    return s

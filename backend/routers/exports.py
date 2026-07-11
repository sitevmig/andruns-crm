import pandas as pd
from io import BytesIO
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Dict
from fastapi.responses import StreamingResponse
from database import db
from security import get_current_user
from routers.organizations import build_query
from constants import STATUS_REJECTED, STATUS_DELIVERY_ERROR

router = APIRouter(prefix="/api/export", tags=["export"])

ORG_COLUMNS = [
    ("name", "Организация"), ("category", "Категория"), ("city", "Город"),
    ("address", "Адрес"), ("phone", "Телефон"), ("email", "Email"),
    ("telegram", "Telegram"), ("source_url", "Источник"), ("status", "Статус"),
    ("last_channel", "Канал последнего сообщения"), ("last_message_at", "Дата последнего сообщения"),
    ("next_action_at", "Следующее действие"), ("comment", "Комментарий"),
    ("do_not_contact", "Не связываться"), ("rejection_reason", "Причина отказа"),
    ("last_reply_at", "Дата ответа"), ("first_import_at", "Дата импорта"),
    ("updated_at", "Обновлено"),
]


def _orgs_to_xlsx(docs) -> BytesIO:
    rows = []
    for d in docs:
        rows.append({label: d.get(key) for key, label in ORG_COLUMNS})
    df = pd.DataFrame(rows, columns=[label for _, label in ORG_COLUMNS])
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf


def _xlsx_response(buf, name):
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/all")
async def export_all(user: dict = Depends(get_current_user)):
    docs = await db.organizations.find({}).to_list(100000)
    return _xlsx_response(_orgs_to_xlsx(docs), "crm_all.xlsx")


class FilterBody(BaseModel):
    filters: Dict[str, str] = {}


@router.post("/filtered")
async def export_filtered(body: FilterBody, user: dict = Depends(get_current_user)):
    params = dict(body.filters)
    params["include_archive"] = True
    q = build_query(params)
    docs = await db.organizations.find(q).to_list(100000)
    return _xlsx_response(_orgs_to_xlsx(docs), "crm_filtered.xlsx")


@router.get("/rejections")
async def export_rejections(user: dict = Depends(get_current_user)):
    docs = await db.organizations.find({"status": STATUS_REJECTED}).to_list(100000)
    return _xlsx_response(_orgs_to_xlsx(docs), "crm_rejections.xlsx")


@router.get("/dnc")
async def export_dnc(user: dict = Depends(get_current_user)):
    docs = await db.organizations.find({"do_not_contact": True}).to_list(100000)
    return _xlsx_response(_orgs_to_xlsx(docs), "crm_do_not_contact.xlsx")


@router.get("/errors")
async def export_errors(user: dict = Depends(get_current_user)):
    docs = await db.organizations.find({"status": STATUS_DELIVERY_ERROR}).to_list(100000)
    return _xlsx_response(_orgs_to_xlsx(docs), "crm_delivery_errors.xlsx")


@router.get("/messages")
async def export_messages(user: dict = Depends(get_current_user)):
    msgs = await db.messages.find({}).sort("at", -1).to_list(100000)
    org_ids = list({m["org_id"] for m in msgs if m.get("org_id")})
    from bson import ObjectId
    orgs = await db.organizations.find({"_id": {"$in": [ObjectId(i) for i in org_ids]}}).to_list(100000)
    org_map = {str(o["_id"]): o.get("name", "") for o in orgs}
    rows = [{
        "Дата": m.get("at"), "Организация": org_map.get(m.get("org_id"), ""),
        "Канал": m.get("channel"), "Направление": m.get("direction"),
        "Статус": m.get("delivery_status"), "Ошибка": m.get("error"),
        "Текст": m.get("text"), "Администратор": m.get("admin"),
    } for m in msgs]
    df = pd.DataFrame(rows)
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return _xlsx_response(buf, "crm_messages.xlsx")

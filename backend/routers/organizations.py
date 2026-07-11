from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from database import db
from helpers import now_iso, serialize, serialize_list, normalize_phone, normalize_email, normalize_telegram, clean_str
from security import get_current_user
from services import log_change, log_message
from constants import ORG_STATUSES, STATUS_DNC, STATUS_ARCHIVE, SAVED_FILTERS, CRM_FIELDS

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


class OrgCreate(BaseModel):
    name: str
    category: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    telegram: Optional[str] = None
    source_url: Optional[str] = None
    comment: Optional[str] = None


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    telegram: Optional[str] = None
    source_url: Optional[str] = None
    comment: Optional[str] = None
    next_action_at: Optional[str] = None


class StatusBody(BaseModel):
    status: str
    reason: Optional[str] = None


class BulkStatus(BaseModel):
    ids: List[str]
    status: str


class BulkIds(BaseModel):
    ids: List[str]


class CommentBody(BaseModel):
    comment: str


class NextActionBody(BaseModel):
    next_action_at: str


def build_query(params: dict) -> dict:
    q = {}
    search = params.get("search")
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"telegram": {"$regex": search, "$options": "i"}},
            {"category": {"$regex": search, "$options": "i"}},
        ]
    if params.get("status"):
        q["status"] = params["status"]
    if params.get("category"):
        q["category"] = params["category"]
    if params.get("city"):
        q["city"] = params["city"]
    if params.get("has_email") == "yes":
        q["email"] = {"$nin": [None, ""]}
    elif params.get("has_email") == "no":
        q["email"] = {"$in": [None, ""]}
    if params.get("has_telegram") == "yes":
        q["telegram"] = {"$nin": [None, ""]}
    elif params.get("has_telegram") == "no":
        q["telegram"] = {"$in": [None, ""]}
    if params.get("do_not_contact") == "yes":
        q["do_not_contact"] = True
    elif params.get("do_not_contact") == "no":
        q["do_not_contact"] = False
    if params.get("has_reply") == "yes":
        q["last_reply_at"] = {"$nin": [None, ""]}
    if params.get("has_error") == "yes":
        q["status"] = "Ошибка доставки"
    if not params.get("include_archive"):
        if "status" not in q:
            q["status"] = {"$ne": STATUS_ARCHIVE}
    return q


@router.get("")
async def list_orgs(
    search: Optional[str] = None, status: Optional[str] = None, category: Optional[str] = None,
    city: Optional[str] = None, has_email: Optional[str] = None, has_telegram: Optional[str] = None,
    do_not_contact: Optional[str] = None, has_reply: Optional[str] = None, has_error: Optional[str] = None,
    include_archive: bool = False, sort_by: str = "updated_at", sort_dir: int = -1,
    page: int = 1, page_size: int = 50, user: dict = Depends(get_current_user),
):
    params = locals()
    q = build_query(params)
    total = await db.organizations.count_documents(q)
    cursor = db.organizations.find(q).sort(sort_by, sort_dir).skip((page - 1) * page_size).limit(page_size)
    docs = await cursor.to_list(page_size)
    return {"items": serialize_list(docs), "total": total, "page": page, "page_size": page_size}


@router.get("/meta")
async def meta(user: dict = Depends(get_current_user)):
    categories = await db.organizations.distinct("category")
    cities = await db.organizations.distinct("city")
    return {
        "statuses": ORG_STATUSES,
        "categories": [c for c in categories if c],
        "cities": [c for c in cities if c],
        "saved_filters": SAVED_FILTERS,
        "crm_fields": CRM_FIELDS,
    }


@router.post("")
async def create_org(body: OrgCreate, user: dict = Depends(get_current_user)):
    doc = {
        "external_id": None,
        "name": body.name,
        "category": clean_str(body.category),
        "city": clean_str(body.city),
        "address": clean_str(body.address),
        "phone": normalize_phone(body.phone),
        "phone_raw": clean_str(body.phone),
        "email": normalize_email(body.email),
        "telegram": normalize_telegram(body.telegram),
        "source_url": clean_str(body.source_url),
        "first_import_at": None,
        "last_update_at": now_iso(),
        "status": "Новый",
        "last_channel": None,
        "last_message_at": None,
        "next_action_at": None,
        "comment": clean_str(body.comment),
        "do_not_contact": False,
        "rejection_reason": None,
        "last_reply_at": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    res = await db.organizations.insert_one(doc)
    oid = str(res.inserted_id)
    await log_change(oid, "create", "Организация создана вручную", user["email"])
    doc["id"] = oid
    doc.pop("_id", None)
    return doc


@router.post("/bulk/status")
async def bulk_status(body: BulkStatus, user: dict = Depends(get_current_user)):
    if body.status not in ORG_STATUSES:
        raise HTTPException(status_code=400, detail="Недопустимый статус")
    oids = [ObjectId(i) for i in body.ids]
    await db.organizations.update_many({"_id": {"$in": oids}}, {"$set": {"status": body.status, "updated_at": now_iso()}})
    return {"ok": True, "count": len(body.ids)}


@router.post("/bulk/archive")
async def bulk_archive(body: BulkIds, user: dict = Depends(get_current_user)):
    oids = [ObjectId(i) for i in body.ids]
    await db.organizations.update_many({"_id": {"$in": oids}}, {"$set": {"status": STATUS_ARCHIVE, "updated_at": now_iso()}})
    return {"ok": True}


@router.get("/{org_id}")
async def get_org(org_id: str, user: dict = Depends(get_current_user)):
    doc = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    return serialize(doc)


@router.get("/{org_id}/messages")
async def org_messages(org_id: str, user: dict = Depends(get_current_user)):
    docs = await db.messages.find({"org_id": org_id}).sort("at", -1).to_list(500)
    return serialize_list(docs)


@router.get("/{org_id}/changes")
async def org_changes(org_id: str, user: dict = Depends(get_current_user)):
    docs = await db.changes.find({"org_id": org_id}).sort("at", -1).to_list(500)
    return serialize_list(docs)


@router.put("/{org_id}")
async def update_org(org_id: str, body: OrgUpdate, user: dict = Depends(get_current_user)):
    upd = {}
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "phone":
            upd["phone"] = normalize_phone(v)
            upd["phone_raw"] = clean_str(v)
        elif k == "email":
            upd["email"] = normalize_email(v)
        elif k == "telegram":
            upd["telegram"] = normalize_telegram(v)
        else:
            upd[k] = clean_str(v) if isinstance(v, str) else v
    upd["updated_at"] = now_iso()
    upd["last_update_at"] = now_iso()
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": upd})
    await log_change(org_id, "edit", "Ручное редактирование карточки", user["email"])
    doc = await db.organizations.find_one({"_id": ObjectId(org_id)})
    return serialize(doc)


@router.post("/{org_id}/status")
async def set_status(org_id: str, body: StatusBody, user: dict = Depends(get_current_user)):
    if body.status not in ORG_STATUSES:
        raise HTTPException(status_code=400, detail="Недопустимый статус")
    upd = {"status": body.status, "updated_at": now_iso()}
    if body.status == STATUS_DNC:
        upd["do_not_contact"] = True
        await db.queue.update_many(
            {"org_id": org_id, "status": {"$in": ["Ожидает", "Запланировано"]}},
            {"$set": {"status": "Отменено", "last_error": "Отмечено «Не связываться»"}},
        )
    if body.reason:
        upd["rejection_reason"] = body.reason
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": upd})
    await log_change(org_id, "status", f"Статус изменён на «{body.status}»", user["email"])
    doc = await db.organizations.find_one({"_id": ObjectId(org_id)})
    return serialize(doc)


@router.post("/{org_id}/dnc")
async def mark_dnc(org_id: str, body: StatusBody = None, user: dict = Depends(get_current_user)):
    await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"do_not_contact": True, "status": STATUS_DNC, "updated_at": now_iso(),
                  "rejection_reason": (body.reason if body else None)}},
    )
    await db.queue.update_many(
        {"org_id": org_id, "status": {"$in": ["Ожидает", "Запланировано"]}},
        {"$set": {"status": "Отменено", "last_error": "Отмечено «Не связываться»"}},
    )
    await log_change(org_id, "dnc", "Добавлено в чёрный список «Не связываться»", user["email"])
    doc = await db.organizations.find_one({"_id": ObjectId(org_id)})
    return serialize(doc)


@router.post("/{org_id}/comment")
async def add_comment(org_id: str, body: CommentBody, user: dict = Depends(get_current_user)):
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"comment": body.comment, "updated_at": now_iso()}})
    await log_change(org_id, "comment", "Обновлён комментарий", user["email"])
    return {"ok": True}


@router.post("/{org_id}/next-action")
async def set_next_action(org_id: str, body: NextActionBody, user: dict = Depends(get_current_user)):
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"next_action_at": body.next_action_at, "updated_at": now_iso()}})
    await log_change(org_id, "next_action", f"Назначено следующее действие: {body.next_action_at}", user["email"])
    return {"ok": True}


@router.post("/{org_id}/archive")
async def archive_org(org_id: str, user: dict = Depends(get_current_user)):
    await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {"status": STATUS_ARCHIVE, "updated_at": now_iso()}})
    await log_change(org_id, "archive", "Организация архивирована", user["email"])
    return {"ok": True}


@router.delete("/{org_id}")
async def delete_org(org_id: str, user: dict = Depends(get_current_user)):
    await db.organizations.delete_one({"_id": ObjectId(org_id)})
    await db.queue.delete_many({"org_id": org_id})
    return {"ok": True}


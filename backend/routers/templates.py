from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import db
from helpers import now_iso, serialize, serialize_list, render_template
from security import get_current_user

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateBody(BaseModel):
    name: str
    channel: str  # email | telegram
    subject: Optional[str] = ""
    body: str
    signature: Optional[str] = ""


@router.get("")
async def list_templates(channel: Optional[str] = None, include_archived: bool = False,
                         user: dict = Depends(get_current_user)):
    q = {}
    if channel:
        q["channel"] = channel
    if not include_archived:
        q["archived"] = {"$ne": True}
    docs = await db.templates.find(q).sort("created_at", -1).to_list(200)
    return serialize_list(docs)


@router.post("")
async def create_template(body: TemplateBody, user: dict = Depends(get_current_user)):
    if not body.body.strip():
        raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым")
    doc = body.model_dump()
    doc.update({"archived": False, "created_at": now_iso(), "updated_at": now_iso(), "created_by": user["email"]})
    res = await db.templates.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    return doc


@router.put("/{tid}")
async def update_template(tid: str, body: TemplateBody, user: dict = Depends(get_current_user)):
    if not body.body.strip():
        raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым")
    upd = body.model_dump()
    upd["updated_at"] = now_iso()
    await db.templates.update_one({"_id": ObjectId(tid)}, {"$set": upd})
    doc = await db.templates.find_one({"_id": ObjectId(tid)})
    return serialize(doc)


@router.post("/{tid}/copy")
async def copy_template(tid: str, user: dict = Depends(get_current_user)):
    doc = await db.templates.find_one({"_id": ObjectId(tid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    doc.pop("_id", None)
    doc["name"] = doc["name"] + " (копия)"
    doc["created_at"] = now_iso()
    doc["updated_at"] = now_iso()
    res = await db.templates.insert_one(doc)
    return {"id": str(res.inserted_id)}


@router.post("/{tid}/archive")
async def archive_template(tid: str, user: dict = Depends(get_current_user)):
    await db.templates.update_one({"_id": ObjectId(tid)}, {"$set": {"archived": True}})
    return {"ok": True}


class PreviewBody(BaseModel):
    template_id: str
    org_id: str


@router.post("/preview")
async def preview_template(body: PreviewBody, user: dict = Depends(get_current_user)):
    tpl = await db.templates.find_one({"_id": ObjectId(body.template_id)})
    org = await db.organizations.find_one({"_id": ObjectId(body.org_id)})
    if not tpl or not org:
        raise HTTPException(status_code=404, detail="Шаблон или организация не найдены")
    extra = {"manager_name": user.get("name", "")}
    return {
        "subject": render_template(tpl.get("subject", ""), org, extra),
        "body": render_template(tpl.get("body", ""), org, extra),
        "signature": tpl.get("signature", ""),
        "channel": tpl["channel"],
    }

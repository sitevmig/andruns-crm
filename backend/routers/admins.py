from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from database import db
from helpers import now_iso, serialize_list
from security import get_current_user, hash_password

router = APIRouter(prefix="/api/admins", tags=["admins"])


class AdminCreate(BaseModel):
    email: EmailStr
    name: str
    password: str


class ResetPw(BaseModel):
    password: str


@router.get("")
async def list_admins(user: dict = Depends(get_current_user)):
    docs = await db.users.find({}).sort("created_at", 1).to_list(100)
    out = []
    for d in docs:
        out.append({"id": str(d["_id"]), "email": d["email"], "name": d.get("name", ""), "created_at": d.get("created_at")})
    return out


@router.post("")
async def create_admin(body: AdminCreate, user: dict = Depends(get_current_user)):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Администратор с таким email уже существует")
    doc = {
        "email": email, "name": body.name, "password_hash": hash_password(body.password),
        "role": "admin", "created_at": now_iso(),
    }
    res = await db.users.insert_one(doc)
    return {"id": str(res.inserted_id), "email": email, "name": body.name}


@router.delete("/{admin_id}")
async def delete_admin(admin_id: str, user: dict = Depends(get_current_user)):
    if admin_id == user["id"]:
        raise HTTPException(status_code=400, detail="Нельзя удалить собственную учётную запись")
    count = await db.users.count_documents({})
    if count <= 1:
        raise HTTPException(status_code=400, detail="Нельзя удалить последнего администратора")
    await db.users.delete_one({"_id": ObjectId(admin_id)})
    await db.sessions.delete_many({"user_id": admin_id})
    return {"ok": True}


@router.post("/{admin_id}/reset-password")
async def reset_password(admin_id: str, body: ResetPw, user: dict = Depends(get_current_user)):
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль слишком короткий")
    await db.users.update_one({"_id": ObjectId(admin_id)}, {"$set": {"password_hash": hash_password(body.password)}})
    return {"ok": True}


@router.post("/{admin_id}/terminate-sessions")
async def terminate_sessions(admin_id: str, user: dict = Depends(get_current_user)):
    await db.sessions.delete_many({"user_id": admin_id})
    return {"ok": True}

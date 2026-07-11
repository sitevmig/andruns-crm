import uuid
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from database import db
from helpers import now_iso, serialize_list
from security import (
    get_current_user, hash_password, verify_password, create_access_token,
    check_brute_force, register_failed, clear_attempts,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ChangePwBody(BaseModel):
    old_password: str
    new_password: str


@router.post("/login")
async def login(body: LoginBody, request: Request):
    email = body.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    await check_brute_force(identifier)

    user = await db.users.find_one({"email": email})
    ua = request.headers.get("User-Agent", "")
    if not user or not verify_password(body.password, user["password_hash"]):
        await register_failed(identifier)
        await db.login_events.insert_one({
            "email": email, "ip": ip, "success": False, "at": now_iso(), "user_agent": ua,
        })
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    await clear_attempts(identifier)
    jti = str(uuid.uuid4())
    uid = str(user["_id"])
    await db.sessions.insert_one({
        "_id": jti, "user_id": uid, "email": email, "ip": ip,
        "user_agent": ua, "created_at": now_iso(), "last_seen": now_iso(),
    })
    await db.login_events.insert_one({
        "email": email, "ip": ip, "success": True, "at": now_iso(), "user_agent": ua,
    })
    token = create_access_token(uid, email, jti)
    return {
        "token": token,
        "user": {"id": uid, "email": email, "name": user.get("name", "")},
    }


@router.post("/logout")
async def logout(request: Request, user: dict = Depends(get_current_user)):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    import jwt as _jwt
    from security import get_jwt_secret, JWT_ALGORITHM
    try:
        payload = _jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        await db.sessions.delete_one({"_id": payload.get("jti")})
    except Exception:
        pass
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/change-password")
async def change_password(body: ChangePwBody, user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"_id": ObjectId(user["id"])})
    if not verify_password(body.old_password, full["password_hash"]):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль слишком короткий")
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"ok": True}


@router.get("/sessions")
async def my_sessions(user: dict = Depends(get_current_user)):
    docs = await db.sessions.find({"user_id": user["id"]}).sort("last_seen", -1).to_list(200)
    return serialize_list(docs)


@router.delete("/sessions/{sid}")
async def terminate_session(sid: str, user: dict = Depends(get_current_user)):
    await db.sessions.delete_one({"_id": sid, "user_id": user["id"]})
    return {"ok": True}


@router.post("/logout-all")
async def logout_all(user: dict = Depends(get_current_user)):
    await db.sessions.delete_many({"user_id": user["id"]})
    return {"ok": True}


@router.get("/login-journal")
async def login_journal(user: dict = Depends(get_current_user)):
    docs = await db.login_events.find({}).sort("at", -1).to_list(300)
    return serialize_list(docs)

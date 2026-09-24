import os
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError

from database import db
from helpers import now_iso, render_template
from security import get_current_user
from services import get_settings, log_message, log_change, sender_from_addr
from crypto import encrypt_dict, decrypt_dict
from email_provider import send_email, email_configured, EmailNotConfigured, InvalidEmailAddress
from helpers import is_valid_email
from constants import CHANNEL_EMAIL, CHANNEL_TELEGRAM, STATUS_SENT, STATUS_REPLIED

router = APIRouter(prefix="/api", tags=["integrations"])


def _tg_api():
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        raise HTTPException(status_code=503, detail="Не заданы TELEGRAM_API_ID и TELEGRAM_API_HASH в backend.")
    try:
        return int(api_id), api_hash
    except ValueError:
        raise HTTPException(status_code=503, detail="TELEGRAM_API_ID должен быть числом.")


async def _load_session(user_id: str) -> Optional[str]:
    doc = await db.telegram_sessions.find_one({"user_id": user_id})
    if not doc or not doc.get("enc_session"):
        return None
    return decrypt_dict(doc["enc_session"]).get("session")


async def _log_tg_error(user_id: str, action: str, error: str):
    await db.telegram_errors.insert_one({"user_id": user_id, "action": action, "error": error, "at": now_iso()})


# ---------------- Telegram MTProto (Telethon, no persistent worker) ----------------
class PhoneBody(BaseModel):
    phone: str


class CodeBody(BaseModel):
    code: str
    password: Optional[str] = None


@router.get("/telegram/status")
async def telegram_status(user: dict = Depends(get_current_user)):
    doc = await db.telegram_sessions.find_one({"user_id": user["id"]})
    errors = await db.telegram_errors.find({"user_id": user["id"]}, {"_id": 0}).sort("at", -1).to_list(20)
    configured = bool(os.environ.get("TELEGRAM_API_ID") and os.environ.get("TELEGRAM_API_HASH"))
    return {
        "connected": bool(doc and doc.get("connected")),
        "phone": doc.get("phone") if doc else "",
        "status": doc.get("status", "Не подключен") if doc else "Не подключен",
        "api_configured": configured,
        "errors": errors,
    }


@router.post("/telegram/login/start")
async def telegram_login_start(body: PhoneBody, user: dict = Depends(get_current_user)):
    api_id, api_hash = _tg_api()
    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.connect()
        sent = await client.send_code_request(body.phone)
        temp_session = client.session.save()
        await db.telegram_login.update_one(
            {"user_id": user["id"]},
            {"$set": {"user_id": user["id"], "phone": body.phone,
                      "phone_code_hash": sent.phone_code_hash,
                      "enc_temp": encrypt_dict({"session": temp_session}), "at": now_iso()}},
            upsert=True,
        )
        return {"ok": True, "message": "Код отправлен в Telegram."}
    except FloodWaitError as e:
        await _log_tg_error(user["id"], "login_start", f"FloodWait {e.seconds}s")
        raise HTTPException(status_code=429, detail=f"Слишком часто. Подождите {e.seconds} сек.")
    except Exception as e:
        await _log_tg_error(user["id"], "login_start", str(e))
        raise HTTPException(status_code=400, detail=f"Ошибка подключения к Telegram: {e}")
    finally:
        await client.disconnect()


@router.post("/telegram/login/complete")
async def telegram_login_complete(body: CodeBody, user: dict = Depends(get_current_user)):
    api_id, api_hash = _tg_api()
    login = await db.telegram_login.find_one({"user_id": user["id"]})
    if not login:
        raise HTTPException(status_code=400, detail="Сначала запросите код (login/start).")
    temp_session = decrypt_dict(login["enc_temp"]).get("session")
    client = TelegramClient(StringSession(temp_session), api_id, api_hash)
    try:
        await client.connect()
        try:
            await client.sign_in(login["phone"], body.code, phone_code_hash=login["phone_code_hash"])
        except SessionPasswordNeededError:
            if not body.password:
                raise HTTPException(status_code=400, detail="Требуется пароль двухфакторной аутентификации.")
            await client.sign_in(password=body.password)
        me = await client.get_me()
        session_str = client.session.save()
        await db.telegram_sessions.update_one(
            {"user_id": user["id"]},
            {"$set": {"user_id": user["id"], "phone": login["phone"], "connected": True,
                      "status": f"Подключен: {me.first_name or ''} @{me.username or ''}",
                      "enc_session": encrypt_dict({"session": session_str}), "at": now_iso()}},
            upsert=True,
        )
        await db.telegram_login.delete_one({"user_id": user["id"]})
        return {"ok": True, "status": "Подключен"}
    except PhoneCodeInvalidError:
        raise HTTPException(status_code=400, detail="Неверный код подтверждения.")
    except HTTPException:
        raise
    except Exception as e:
        await _log_tg_error(user["id"], "login_complete", str(e))
        raise HTTPException(status_code=400, detail=f"Ошибка входа: {e}")
    finally:
        await client.disconnect()


@router.post("/telegram/check")
async def telegram_check(user: dict = Depends(get_current_user)):
    session = await _load_session(user["id"])
    if not session:
        raise HTTPException(status_code=400, detail="Telegram не подключен.")
    api_id, api_hash = _tg_api()
    client = TelegramClient(StringSession(session), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise HTTPException(status_code=400, detail="Сессия недействительна, переподключите аккаунт.")
        me = await client.get_me()
        return {"ok": True, "status": f"Соединение активно: @{me.username or me.phone}"}
    except HTTPException:
        raise
    except Exception as e:
        await _log_tg_error(user["id"], "check", str(e))
        raise HTTPException(status_code=400, detail=f"Ошибка соединения: {e}")
    finally:
        await client.disconnect()


@router.post("/telegram/disconnect")
async def telegram_disconnect(user: dict = Depends(get_current_user)):
    await db.telegram_sessions.delete_one({"user_id": user["id"]})
    await db.telegram_login.delete_one({"user_id": user["id"]})
    return {"ok": True}


class TgTestBody(BaseModel):
    to: str
    text: str = "Тестовое сообщение из CRM Andruns"


@router.post("/telegram/test")
async def telegram_test(body: TgTestBody, user: dict = Depends(get_current_user)):
    return await _tg_send(user, body.to, body.text, org_id=None, action="test")


class TgSendBody(BaseModel):
    org_id: str
    text: str


@router.post("/telegram/send")
async def telegram_send(body: TgSendBody, user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"_id": ObjectId(body.org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    if org.get("do_not_contact"):
        raise HTTPException(status_code=400, detail="Организация в списке «Не связываться».")
    if not org.get("telegram"):
        raise HTTPException(status_code=400, detail="У организации нет Telegram.")
    # prevent duplicate first message without explicit confirmation
    already = await db.messages.find_one({"org_id": body.org_id, "channel": CHANNEL_TELEGRAM,
                                          "direction": "outgoing", "delivery_status": "Отправлено"})
    if already:
        raise HTTPException(status_code=409, detail="Первое сообщение уже отправлено. Повтор требует отдельного подтверждения.")
    return await _tg_send(user, org["telegram"], body.text, org_id=body.org_id, action="send")


async def _tg_send(user, to, text, org_id, action):
    session = await _load_session(user["id"])
    if not session:
        raise HTTPException(status_code=400, detail="Telegram не подключен.")
    api_id, api_hash = _tg_api()
    client = TelegramClient(StringSession(session), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise HTTPException(status_code=400, detail="Сессия недействительна, переподключите аккаунт.")
        entity = await client.get_entity(to if str(to).startswith("@") or str(to).startswith("+") else f"@{to}")
        msg = await client.send_message(entity, text)
        ext_id = str(msg.id)
        if org_id:
            await log_message(org_id, CHANNEL_TELEGRAM, "outgoing", text, None, "Отправлено", "", user["email"], ext_id)
            await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$set": {
                "status": STATUS_SENT, "last_channel": CHANNEL_TELEGRAM, "last_message_at": now_iso(), "updated_at": now_iso()}})
            await log_change(org_id, "message", "Отправлено сообщение (Telegram)", user["email"])
        return {"ok": True, "message_id": ext_id}
    except HTTPException:
        raise
    except Exception as e:
        await _log_tg_error(user["id"], action, str(e))
        raise HTTPException(status_code=400, detail=f"Ошибка отправки Telegram: {e}")
    finally:
        await client.disconnect()


@router.post("/telegram/check-replies")
async def telegram_check_replies(user: dict = Depends(get_current_user)):
    session = await _load_session(user["id"])
    if not session:
        raise HTTPException(status_code=400, detail="Telegram не подключен.")
    api_id, api_hash = _tg_api()
    client = TelegramClient(StringSession(session), api_id, api_hash)
    found = 0
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise HTTPException(status_code=400, detail="Сессия недействительна, переподключите аккаунт.")
        async for dialog in client.iter_dialogs(limit=50):
            if not dialog.is_user or dialog.entity.bot:
                continue
            uname = getattr(dialog.entity, "username", None)
            if not uname:
                continue
            org = await db.organizations.find_one({"telegram": uname})
            if not org:
                continue
            async for m in client.iter_messages(dialog.entity, limit=5):
                if m.out or not m.text:
                    continue
                exists = await db.messages.find_one({"org_id": str(org["_id"]), "external_id": f"in-{m.id}"})
                if exists:
                    continue
                await db.messages.insert_one({
                    "org_id": str(org["_id"]), "channel": CHANNEL_TELEGRAM, "direction": "incoming",
                    "text": m.text, "template_id": None, "delivery_status": "Получено", "error": "",
                    "admin": "", "external_id": f"in-{m.id}", "at": now_iso(), "read": False,
                })
                found += 1
                upd = {"last_reply_at": now_iso(), "updated_at": now_iso()}
                if org.get("status") == STATUS_SENT:
                    upd["status"] = STATUS_REPLIED
                await db.organizations.update_one({"_id": org["_id"]}, {"$set": upd})
                break
        return {"ok": True, "new_replies": found}
    except HTTPException:
        raise
    except Exception as e:
        await _log_tg_error(user["id"], "check_replies", str(e))
        raise HTTPException(status_code=400, detail=f"Ошибка проверки ответов: {e}")
    finally:
        await client.disconnect()


# ---------------- Email via HTTPS provider (Resend) ----------------
@router.get("/email/status")
async def email_status(user: dict = Depends(get_current_user)):
    s = await get_settings()
    return {
        "configured": email_configured(),
        "provider": os.environ.get("EMAIL_PROVIDER", "resend"),
        "sender_email": s.get("sender_email", ""),
        "sender_name": s.get("sender_name", ""),
        "reply_to": s.get("reply_to", ""),
    }


class EmailTestBody(BaseModel):
    to: str
    subject: str = "Тестовое письмо CRM Andruns"
    text: str = "Это тестовое письмо из CRM Andruns."


def _from_addr(s):
    try:
        return sender_from_addr(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/email/test")
async def email_test(body: EmailTestBody, user: dict = Depends(get_current_user)):
    to = (body.to or "").strip()
    if not is_valid_email(to):
        raise HTTPException(status_code=400, detail=f"Некорректный email получателя: «{to}». Укажите адрес в формате email@example.com.")
    s = await get_settings()
    try:
        mid = send_email(to, body.subject, f"<p>{body.text}</p>", body.text, _from_addr(s), s.get("reply_to"))
        return {"ok": True, "message_id": mid}
    except EmailNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except InvalidEmailAddress as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка отправки email: {e}")


class EmailSendBody(BaseModel):
    org_id: str
    subject: str
    text: str
    html: Optional[str] = None


@router.post("/email/send")
async def email_send(body: EmailSendBody, user: dict = Depends(get_current_user)):
    org = await db.organizations.find_one({"_id": ObjectId(body.org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    if org.get("do_not_contact"):
        raise HTTPException(status_code=400, detail="Организация в списке «Не связываться».")
    if not org.get("email"):
        raise HTTPException(status_code=400, detail="У организации нет email.")
    if not is_valid_email(org["email"]):
        raise HTTPException(status_code=400, detail=f"У организации некорректный email: «{org['email']}».")
    already = await db.messages.find_one({"org_id": body.org_id, "channel": CHANNEL_EMAIL,
                                          "direction": "outgoing", "delivery_status": "Отправлено"})
    if already:
        raise HTTPException(status_code=409, detail="Первое письмо уже отправлено. Повтор требует отдельного подтверждения.")
    s = await get_settings()
    try:
        mid = send_email(org["email"], body.subject, body.html or f"<p>{body.text}</p>", body.text, _from_addr(s), s.get("reply_to"))
    except EmailNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except InvalidEmailAddress as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка отправки email: {e}")
    await log_message(body.org_id, CHANNEL_EMAIL, "outgoing", body.subject + "\n\n" + body.text, None, "Отправлено", "", user["email"], mid)
    await db.organizations.update_one({"_id": org["_id"]}, {"$set": {
        "status": STATUS_SENT, "last_channel": CHANNEL_EMAIL, "last_message_at": now_iso(), "updated_at": now_iso()}})
    await log_change(body.org_id, "message", "Отправлено письмо (email)", user["email"])
    return {"ok": True, "message_id": mid}


@router.get("/diag/smtp")
async def diag_smtp():
    """Temporary, unauthenticated: walks through TCP connect -> SSL handshake
    -> SMTP login against the configured SMTP host, each with its own short
    timeout, to pinpoint exactly where a hang or failure happens (no mail is
    sent). Safe to remove once mail.ru SMTP sending is confirmed working."""
    import socket
    import time
    import smtplib

    host = os.environ.get("SMTP_HOST", "smtp.mail.ru")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    result = {"host": host, "port": port, "smtp_user_set": bool(user), "smtp_password_set": bool(password)}

    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=8):
            pass
        result["1_tcp_connect"] = {"ok": True, "elapsed_seconds": round(time.time() - start, 2)}
    except Exception as e:
        result["1_tcp_connect"] = {"ok": False, "error": str(e), "elapsed_seconds": round(time.time() - start, 2)}
        return result

    start = time.time()
    try:
        server = smtplib.SMTP_SSL(host, port, timeout=8)
        result["2_ssl_handshake"] = {"ok": True, "elapsed_seconds": round(time.time() - start, 2)}
    except Exception as e:
        result["2_ssl_handshake"] = {"ok": False, "error": str(e), "elapsed_seconds": round(time.time() - start, 2)}
        return result

    if user and password:
        start = time.time()
        try:
            server.login(user, password)
            result["3_login"] = {"ok": True, "elapsed_seconds": round(time.time() - start, 2)}
        except Exception as e:
            result["3_login"] = {"ok": False, "error": str(e), "elapsed_seconds": round(time.time() - start, 2)}
    else:
        result["3_login"] = {"skipped": "SMTP_USER/SMTP_PASSWORD not set"}
    try:
        server.quit()
    except Exception:
        pass
    return result

import os
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from database import db
from helpers import now_iso
from security import get_current_user

router = APIRouter(prefix="/api/backups", tags=["backups"])

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

COLLECTIONS = ["organizations", "messages", "changes", "templates", "queue", "duplicates", "settings", "imports"]


def _serialize_doc(d):
    d = dict(d)
    if "_id" in d and not isinstance(d["_id"], str):
        d["_id"] = {"$oid": str(d["_id"])}
    return d


@router.get("")
async def list_backups(user: dict = Depends(get_current_user)):
    docs = await db.backups.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs


@router.post("")
async def create_backup(user: dict = Depends(get_current_user)):
    backup_id = str(uuid.uuid4())
    data = {}
    for col in COLLECTIONS:
        docs = await db[col].find({}).to_list(1000000)
        data[col] = [_serialize_doc(d) for d in docs]
    path = os.path.join(BACKUP_DIR, f"{backup_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    size = os.path.getsize(path)
    rec = {"backup_id": backup_id, "created_at": now_iso(), "created_by": user["email"],
           "size": size, "collections": {c: len(data[c]) for c in COLLECTIONS}}
    await db.backups.insert_one(dict(rec))
    return rec


@router.get("/{backup_id}/download")
async def download_backup(backup_id: str, user: dict = Depends(get_current_user)):
    path = os.path.join(BACKUP_DIR, f"{backup_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Резервная копия не найдена")
    return FileResponse(path, media_type="application/json", filename=f"backup_{backup_id}.json")


class RestoreBody(BaseModel):
    backup_id: str
    confirm: bool = False


@router.post("/restore")
async def restore_backup(body: RestoreBody, user: dict = Depends(get_current_user)):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Требуется подтверждение восстановления")
    path = os.path.join(BACKUP_DIR, f"{body.backup_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Резервная копия не найдена")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    from bson import ObjectId
    for col in COLLECTIONS:
        docs = data.get(col, [])
        parsed = []
        for d in docs:
            if isinstance(d.get("_id"), dict) and "$oid" in d["_id"]:
                d["_id"] = ObjectId(d["_id"]["$oid"])
            parsed.append(d)
        await db[col].delete_many({})
        if parsed:
            await db[col].insert_many(parsed)
    return {"ok": True}

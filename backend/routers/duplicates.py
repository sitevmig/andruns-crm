from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from database import db
from helpers import now_iso, serialize_list
from security import get_current_user
from services import log_change
from constants import STATUS_DUPLICATE, STATUS_ARCHIVE

router = APIRouter(prefix="/api/duplicates", tags=["duplicates"])


@router.get("")
async def list_duplicates(user: dict = Depends(get_current_user)):
    docs = await db.duplicates.find({"resolved": {"$ne": True}}).sort("created_at", -1).to_list(300)
    out = serialize_list(docs)
    all_ids = set()
    for d in out:
        for cid in d.get("candidate_ids", []):
            all_ids.add(cid)
    orgs = await db.organizations.find({"_id": {"$in": [ObjectId(i) for i in all_ids]}}).to_list(1000)
    org_map = {str(o["_id"]): serialize_list([o])[0] for o in orgs}
    for d in out:
        d["candidates"] = [org_map.get(cid) for cid in d.get("candidate_ids", []) if org_map.get(cid)]
    return out


class MergeBody(BaseModel):
    duplicate_id: str
    keep_id: str
    merge_ids: List[str]


@router.post("/merge")
async def merge(body: MergeBody, user: dict = Depends(get_current_user)):
    keep = await db.organizations.find_one({"_id": ObjectId(body.keep_id)})
    if not keep:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    for mid in body.merge_ids:
        if mid == body.keep_id:
            continue
        # move history to kept org, mark merged org as duplicate/archive
        await db.messages.update_many({"org_id": mid}, {"$set": {"org_id": body.keep_id}})
        await db.changes.update_many({"org_id": mid}, {"$set": {"org_id": body.keep_id}})
        merged = await db.organizations.find_one({"_id": ObjectId(mid)})
        if merged and merged.get("do_not_contact"):
            await db.organizations.update_one({"_id": ObjectId(body.keep_id)}, {"$set": {"do_not_contact": True}})
        await db.organizations.update_one({"_id": ObjectId(mid)}, {"$set": {"status": STATUS_ARCHIVE, "comment": f"Объединена с {body.keep_id}", "updated_at": now_iso()}})
    await db.duplicates.update_one({"_id": ObjectId(body.duplicate_id)}, {"$set": {"resolved": True, "resolved_at": now_iso()}})
    await log_change(body.keep_id, "merge", "Объединены дубликаты", user["email"])
    return {"ok": True}


@router.post("/{dup_id}/dismiss")
async def dismiss(dup_id: str, user: dict = Depends(get_current_user)):
    await db.duplicates.update_one({"_id": ObjectId(dup_id)}, {"$set": {"resolved": True, "dismissed": True, "resolved_at": now_iso()}})
    return {"ok": True}

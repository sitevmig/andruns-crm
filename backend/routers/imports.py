import os
import uuid
import math
import pandas as pd
from io import BytesIO
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, List
from fastapi.responses import StreamingResponse
from database import db
from helpers import now_iso, normalize_phone, normalize_email, normalize_telegram, clean_str, is_valid_email
from security import get_current_user
from services import log_change
from constants import STATUS_NEW

router = APIRouter(prefix="/api/import", tags=["import"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

SYNONYMS = {
    "name": ["наименование", "название", "организация", "компания", "name", "фирма"],
    "category": ["категория", "вид", "сфера", "category", "отрасль"],
    "city": ["город", "city", "нас. пункт"],
    "address": ["адрес", "address"],
    "phone": ["телефон", "тел", "phone", "номер", "моб"],
    "email": ["email", "почта", "e-mail", "мейл", "эл. почта"],
    "telegram": ["telegram", "телеграм", "tg", "тг"],
    "source_url": ["ссылка", "источник", "url", "сайт", "site", "link"],
    "external_id": ["external_id", "внешний id", "ид", "id"],
    "comment": ["комментарий", "заметка", "note", "comment"],
}


def _read_df(path: str) -> pd.DataFrame:
    ext = path.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        try:
            return pd.read_csv(path, dtype=str, sep=None, engine="python").fillna("")
        except Exception:
            return pd.read_csv(path, dtype=str).fillna("")
    if ext == "xls":
        return pd.read_excel(path, dtype=str, engine="xlrd").fillna("")
    return pd.read_excel(path, dtype=str, engine="openpyxl").fillna("")


def _auto_map(columns: List[str]) -> Dict[str, str]:
    mapping = {}
    for field, syns in SYNONYMS.items():
        for col in columns:
            cl = str(col).strip().lower()
            if cl in syns or any(s in cl for s in syns):
                mapping[field] = col
                break
    return mapping


async def _find_matches(norm: dict) -> list:
    ors = []
    if norm.get("external_id"):
        ors.append({"external_id": norm["external_id"]})
    if norm.get("source_url"):
        ors.append({"source_url": norm["source_url"]})
    if norm.get("email"):
        ors.append({"email": norm["email"]})
    if norm.get("phone"):
        ors.append({"phone": norm["phone"]})
    if norm.get("telegram"):
        ors.append({"telegram": norm["telegram"]})
    if norm.get("name") and norm.get("address"):
        ors.append({"name": norm["name"], "address": norm["address"]})
    if not ors:
        return []
    docs = await db.organizations.find({"$or": ors}).to_list(50)
    seen, out = set(), []
    for d in docs:
        if str(d["_id"]) not in seen:
            seen.add(str(d["_id"]))
            out.append(d)
    return out


def _normalize_row(row: dict, mapping: dict) -> dict:
    def val(field):
        col = mapping.get(field)
        return row.get(col) if col else None
    return {
        "external_id": clean_str(val("external_id")),
        "name": clean_str(val("name")),
        "category": clean_str(val("category")),
        "city": clean_str(val("city")),
        "address": clean_str(val("address")),
        "phone": normalize_phone(val("phone")),
        "phone_raw": clean_str(val("phone")),
        "email": normalize_email(val("email")),
        "email_raw": clean_str(val("email")),
        "telegram": normalize_telegram(val("telegram")),
        "source_url": clean_str(val("source_url")),
        "comment": clean_str(val("comment")),
    }


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ("xlsx", "xls", "csv"):
        raise HTTPException(status_code=400, detail="Поддерживаются только .xlsx, .xls, .csv")
    import_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{import_id}.{ext}")
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    try:
        df = _read_df(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать файл: {e}")
    columns = [str(c) for c in df.columns]
    sample = df.head(5).astype(str).to_dict("records")
    await db.imports.insert_one({
        "_id": import_id, "filename": file.filename, "path": path, "ext": ext,
        "columns": columns, "row_count": int(len(df)), "status": "uploaded",
        "created_at": now_iso(), "created_by": user["email"], "mapping": None, "summary": None,
    })
    return {"import_id": import_id, "columns": columns, "sample": sample,
            "row_count": int(len(df)), "suggested_mapping": _auto_map(columns)}


class AnalyzeBody(BaseModel):
    import_id: str
    mapping: Dict[str, str]


@router.post("/analyze")
async def analyze(body: AnalyzeBody, user: dict = Depends(get_current_user)):
    imp = await db.imports.find_one({"_id": body.import_id})
    if not imp:
        raise HTTPException(status_code=404, detail="Импорт не найден")
    if not body.mapping.get("name"):
        raise HTTPException(status_code=400, detail="Обязательно сопоставьте поле «Наименование организации»")
    df = _read_df(imp["path"])
    rows = df.astype(str).to_dict("records")
    counts = {"new": 0, "update": 0, "duplicate": 0, "error": 0}
    results = []
    for idx, row in enumerate(rows):
        norm = _normalize_row(row, body.mapping)
        errors = []
        if not norm["name"]:
            errors.append("Отсутствует наименование")
        if norm["email_raw"] and not is_valid_email(norm["email_raw"]):
            errors.append("Некорректный email")
        if errors:
            counts["error"] += 1
            results.append({"row": idx + 2, "action": "error", "name": norm["name"], "errors": errors})
            continue
        matches = await _find_matches(norm)
        if len(matches) == 0:
            counts["new"] += 1
            results.append({"row": idx + 2, "action": "new", "name": norm["name"]})
        elif len(matches) == 1:
            counts["update"] += 1
            results.append({"row": idx + 2, "action": "update", "name": norm["name"],
                            "match_id": str(matches[0]["_id"]),
                            "dnc": bool(matches[0].get("do_not_contact"))})
        else:
            counts["duplicate"] += 1
            results.append({"row": idx + 2, "action": "duplicate", "name": norm["name"],
                            "match_ids": [str(m["_id"]) for m in matches]})
    await db.imports.update_one({"_id": body.import_id},
        {"$set": {"mapping": body.mapping, "summary": counts, "results": results, "status": "analyzed"}})
    return {"counts": counts, "results": results[:200], "total": len(rows)}


class ConfirmBody(BaseModel):
    import_id: str


@router.post("/confirm")
async def confirm(body: ConfirmBody, user: dict = Depends(get_current_user)):
    imp = await db.imports.find_one({"_id": body.import_id})
    if not imp or imp.get("status") != "analyzed":
        raise HTTPException(status_code=400, detail="Сначала выполните анализ импорта")
    mapping = imp["mapping"]
    df = _read_df(imp["path"])
    rows = df.astype(str).to_dict("records")
    report = {"new": 0, "updated": 0, "duplicates": 0, "errors": 0, "dnc_protected": 0}
    report_rows = []
    for idx, row in enumerate(rows):
        norm = _normalize_row(row, mapping)
        if not norm["name"] or (norm["email_raw"] and not is_valid_email(norm["email_raw"])):
            report["errors"] += 1
            report_rows.append({"row": idx + 2, "name": norm["name"], "result": "Ошибка"})
            continue
        matches = await _find_matches(norm)
        if len(matches) == 0:
            doc = {
                "external_id": norm["external_id"], "name": norm["name"], "category": norm["category"],
                "city": norm["city"], "address": norm["address"], "phone": norm["phone"],
                "phone_raw": norm["phone_raw"], "email": norm["email"], "telegram": norm["telegram"],
                "source_url": norm["source_url"], "first_import_at": now_iso(), "last_update_at": now_iso(),
                "status": STATUS_NEW, "last_channel": None, "last_message_at": None, "next_action_at": None,
                "comment": norm["comment"], "do_not_contact": False, "rejection_reason": None,
                "last_reply_at": None, "created_at": now_iso(), "updated_at": now_iso(),
            }
            res = await db.organizations.insert_one(doc)
            await log_change(str(res.inserted_id), "import", f"Импортирована из «{imp['filename']}»", user["email"])
            report["new"] += 1
            report_rows.append({"row": idx + 2, "name": norm["name"], "result": "Добавлена"})
        elif len(matches) == 1:
            m = matches[0]
            oid = str(m["_id"])
            upd = {"last_update_at": now_iso(), "updated_at": now_iso()}
            for f in ["category", "city", "address", "source_url", "external_id"]:
                if norm[f]:
                    upd[f] = norm[f]
            if norm["phone"]:
                upd["phone"] = norm["phone"]; upd["phone_raw"] = norm["phone_raw"]
            if norm["email"]:
                upd["email"] = norm["email"]
            if norm["telegram"]:
                upd["telegram"] = norm["telegram"]
            # DNC and status are preserved (never overwritten)
            await db.organizations.update_one({"_id": m["_id"]}, {"$set": upd})
            await log_change(oid, "import", f"Обновлена из «{imp['filename']}» (статус сохранён)", user["email"])
            report["updated"] += 1
            if m.get("do_not_contact"):
                report["dnc_protected"] += 1
            report_rows.append({"row": idx + 2, "name": norm["name"],
                                "result": "Обновлена (защита «Не связываться»)" if m.get("do_not_contact") else "Обновлена"})
        else:
            await db.duplicates.insert_one({
                "name": norm["name"], "norm": {k: norm[k] for k in ("email", "phone", "telegram", "source_url", "external_id", "address")},
                "candidate_ids": [str(m["_id"]) for m in matches],
                "import_id": body.import_id, "resolved": False, "created_at": now_iso(),
            })
            report["duplicates"] += 1
            report_rows.append({"row": idx + 2, "name": norm["name"], "result": "Возможный дубль — на проверку"})
    await db.imports.update_one({"_id": body.import_id},
        {"$set": {"status": "done", "report": report, "report_rows": report_rows, "finished_at": now_iso()}})
    return {"report": report}


@router.get("/history")
async def history(user: dict = Depends(get_current_user)):
    docs = await db.imports.find({}, {"results": 0, "report_rows": 0}).sort("created_at", -1).to_list(100)
    out = []
    for d in docs:
        d["id"] = d.pop("_id")
        d.pop("path", None)
        out.append(d)
    return out


@router.get("/{import_id}/report")
async def download_report(import_id: str, token: str = "", user: dict = Depends(get_current_user)):
    imp = await db.imports.find_one({"_id": import_id})
    if not imp or "report_rows" not in imp:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    df = pd.DataFrame(imp["report_rows"])
    df.columns = ["Строка", "Организация", "Результат"] if len(df.columns) == 3 else df.columns
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="import_report_{import_id}.xlsx"'})

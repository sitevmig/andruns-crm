import re
from datetime import datetime, timezone
from bson import ObjectId

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def serialize_list(docs):
    return [serialize(d) for d in docs]


def normalize_phone(raw) -> str | None:
    """Normalize Russian phone numbers to +7XXXXXXXXXX."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    if len(digits) == 11 and digits[0] in ("8", "7"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "9":
        # unlikely, keep last 10
        digits = "7" + digits[-10:]
    else:
        # keep as-is if not a standard RU number
        if len(digits) < 10:
            return None
        digits = "7" + digits[-10:]
    return "+" + digits


def is_valid_email(email) -> bool:
    if email is None:
        return False
    return bool(EMAIL_RE.match(str(email).strip()))


def normalize_email(email) -> str | None:
    if email is None:
        return None
    s = str(email).strip().lower()
    if not s or s == "nan":
        return None
    return s


def normalize_telegram(tg) -> str | None:
    if tg is None:
        return None
    s = str(tg).strip()
    if not s or s.lower() == "nan":
        return None
    s = s.lstrip("@")
    s = s.replace("https://t.me/", "").replace("t.me/", "")
    return s or None


def clean_str(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def render_template(text: str, org: dict, extra: dict | None = None) -> str:
    if text is None:
        return ""
    extra = extra or {}
    values = {
        "organization_name": org.get("name") or "",
        "category": org.get("category") or "",
        "city": org.get("city") or "",
        "contact_name": org.get("contact_name") or "",
        "website_offer": extra.get("website_offer", "новый современный сайт"),
        "manager_name": extra.get("manager_name", ""),
    }
    result = text
    for k, v in values.items():
        result = result.replace("{" + k + "}", str(v))
    return result

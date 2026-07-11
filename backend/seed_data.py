import os
from datetime import datetime, timezone, timedelta
from database import db
from security import hash_password, verify_password
from helpers import now_iso, normalize_phone
from services import get_settings
from constants import (
    STATUS_NEW, STATUS_READY, STATUS_SENT, STATUS_REPLIED, STATUS_INTERESTED,
    STATUS_REJECTED, STATUS_DNC, STATUS_DELIVERY_ERROR,
)

DEFAULT_ADMINS = [
    {"email": "admin@crm.ru", "name": "Администратор 1", "password": "Admin123!"},
    {"email": "manager2@crm.ru", "name": "Администратор 2", "password": "Admin123!"},
    {"email": "manager3@crm.ru", "name": "Администратор 3", "password": "Admin123!"},
]


async def seed_admins():
    admins = DEFAULT_ADMINS
    for a in admins:
        existing = await db.users.find_one({"email": a["email"]})
        if not existing:
            await db.users.insert_one({
                "email": a["email"], "name": a["name"],
                "password_hash": hash_password(a["password"]),
                "role": "admin", "created_at": now_iso(),
            })
        elif not verify_password(a["password"], existing["password_hash"]):
            await db.users.update_one({"email": a["email"]}, {"$set": {"password_hash": hash_password(a["password"])}})
    _write_credentials()


def _write_credentials():
    lines = ["# Test Credentials\n", "\n## Администраторы CRM (JWT auth)\n"]
    for a in DEFAULT_ADMINS:
        lines.append(f"- Email: `{a['email']}` | Пароль: `{a['password']}` | Роль: admin\n")
    lines.append("\n## Auth endpoints\n")
    lines.append("- POST /api/auth/login (body: {email, password}) -> {token, user}\n")
    lines.append("- GET /api/auth/me (Authorization: Bearer <token>)\n")
    lines.append("- POST /api/auth/logout\n")
    try:
        with open("/app/memory/test_credentials.md", "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass


DEMO_ORGS = [
    {"name": "Кофейня «Утро»", "category": "Общепит", "city": "Москва", "address": "ул. Тверская, 12",
     "phone": "8 999 123-45-67", "email": "hello@utrocafe.ru", "telegram": "utrocafe", "status": STATUS_NEW},
    {"name": "Автосервис «Мотор»", "category": "Авто", "city": "Санкт-Петербург", "address": "пр. Ленина, 45",
     "phone": "+7 (812) 555-11-22", "email": "info@motor-spb.ru", "telegram": "", "status": STATUS_READY},
    {"name": "Стоматология «Улыбка»", "category": "Медицина", "city": "Казань", "address": "ул. Баумана, 3",
     "phone": "89170001122", "email": "", "telegram": "smileclinic", "status": STATUS_READY},
    {"name": "Юридическое бюро «Право»", "category": "Услуги", "city": "Москва", "address": "ул. Арбат, 9",
     "phone": "8 495 777-88-99", "email": "office@pravo-buro.ru", "telegram": "", "status": STATUS_SENT},
    {"name": "Салон красоты «Шарм»", "category": "Красота", "city": "Новосибирск", "address": "Красный пр., 100",
     "phone": "+7 383 222-33-44", "email": "charm@beauty.ru", "telegram": "charmsalon", "status": STATUS_REPLIED},
    {"name": "Фитнес-клуб «Энергия»", "category": "Спорт", "city": "Екатеринбург", "address": "ул. Малышева, 51",
     "phone": "8 343 111-22-33", "email": "info@energy-fit.ru", "telegram": "", "status": STATUS_INTERESTED},
    {"name": "Магазин цветов «Флора»", "category": "Розница", "city": "Москва", "address": "ул. Ленина, 5",
     "phone": "8 916 444-55-66", "email": "flora@shop.ru", "telegram": "florashop", "status": STATUS_REJECTED},
    {"name": "Ресторан «Восток»", "category": "Общепит", "city": "Сочи", "address": "ул. Приморская, 22",
     "phone": "8 862 333-44-55", "email": "vostok@rest.ru", "telegram": "", "status": STATUS_DNC},
    {"name": "Клиника «Здоровье+»", "category": "Медицина", "city": "Самара", "address": "ул. Победы, 14",
     "phone": "8 846 999-00-11", "email": "invalid-email", "telegram": "", "status": STATUS_DELIVERY_ERROR},
    {"name": "IT-студия «Байт»", "category": "IT", "city": "Санкт-Петербург", "address": "Невский пр., 30",
     "phone": "8 812 000-11-22", "email": "hi@byte-studio.ru", "telegram": "bytestudio", "status": STATUS_NEW},
]


async def seed_demo():
    if await db.organizations.count_documents({}) > 0:
        return
    for o in DEMO_ORGS:
        doc = {
            "external_id": None, "name": o["name"], "category": o["category"], "city": o["city"],
            "address": o["address"], "phone": normalize_phone(o["phone"]), "phone_raw": o["phone"],
            "email": (o["email"] or None), "telegram": (o["telegram"] or None), "source_url": None,
            "first_import_at": now_iso(), "last_update_at": now_iso(), "status": o["status"],
            "last_channel": ("email" if o["status"] in (STATUS_SENT, STATUS_REPLIED) else None),
            "last_message_at": (now_iso() if o["status"] in (STATUS_SENT, STATUS_REPLIED) else None),
            "next_action_at": None, "comment": None,
            "do_not_contact": o["status"] == STATUS_DNC, "rejection_reason": ("Нет бюджета" if o["status"] == STATUS_REJECTED else None),
            "last_reply_at": (now_iso() if o["status"] == STATUS_REPLIED else None),
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        await db.organizations.insert_one(doc)

    if await db.templates.count_documents({}) == 0:
        await db.templates.insert_many([
            {"name": "Первое касание (email)", "channel": "email",
             "subject": "Сайт для «{organization_name}»",
             "body": "Здравствуйте!\n\nМы заметили, что у компании «{organization_name}» в городе {city} нет современного сайта. Предлагаем {website_offer}.\n\nБудет удобно обсудить?",
             "signature": "С уважением, {manager_name}", "archived": False,
             "created_at": now_iso(), "updated_at": now_iso(), "created_by": "system"},
            {"name": "Первое касание (Telegram)", "channel": "telegram", "subject": "",
             "body": "Здравствуйте! Мы делаем сайты для бизнеса в сфере «{category}». Для «{organization_name}» подготовим {website_offer}. Интересно?",
             "signature": "", "archived": False,
             "created_at": now_iso(), "updated_at": now_iso(), "created_by": "system"},
        ])

    await get_settings()

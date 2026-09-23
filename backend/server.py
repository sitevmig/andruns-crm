import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from database import db, client
from seed_data import seed_admins, seed_demo
from worker import process_queue

from routers import (
    auth, admins, organizations, imports, templates, queue,
    dashboard, settings, integrations, exports, backups,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("crm")

app = FastAPI(title="CRM Холодных Продаж")

app.include_router(auth.router)
app.include_router(admins.router)
app.include_router(organizations.router)
app.include_router(imports.router)
app.include_router(templates.router)
app.include_router(queue.router)
app.include_router(dashboard.router)
app.include_router(settings.router)
app.include_router(integrations.router)
app.include_router(exports.router)
app.include_router(backups.router)


@app.get("/api/")
async def root():
    return {"message": "CRM API", "status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

_worker_task = None


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.organizations.create_index("email")
    await db.organizations.create_index("phone")
    await db.organizations.create_index("telegram")
    await db.organizations.create_index("external_id")
    await db.organizations.create_index("status")
    await db.login_attempts.create_index("_id")
    await seed_admins()
    await seed_demo()
    # Background queue worker disabled: real sending is triggered explicitly
    # per manager action (no simulation, no mass auto-send).
    logger.info("CRM backend started")


@app.on_event("shutdown")
async def shutdown():
    client.close()

import logging

from fastapi import FastAPI
from sqlalchemy import text

from .api.routes import router
from .api.alstyle_routes import router as alstyle_router
from .database import engine
from .models.alstyle import Base as AlStyleBase
from .models.user import Base as UserBase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

app = FastAPI(
    title="dshopWB API",
    description="Backend для синхронизации с WB и Al-Style.kz",
    version="1.0.0",
)

# ── Регистрация роутеров ──────────────────────────────────────────────────────
app.include_router(router)
app.include_router(alstyle_router)


# ── Создание таблиц при старте ────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    # Создаём все таблицы (безопасно при повторных запусках — IF NOT EXISTS)
    UserBase.metadata.create_all(bind=engine)
    AlStyleBase.metadata.create_all(bind=engine)
    logging.getLogger(__name__).info("Таблицы БД готовы")


# ── Health-check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}

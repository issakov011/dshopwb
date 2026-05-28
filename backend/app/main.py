import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router
from .api.alstyle_routes import router as alstyle_router
from .api.sync_routes import router as sync_router
from .database import engine
from .models.alstyle import Base as AlStyleBase
from .models.sync_log import Base as SyncLogBase
from .models.user import Base as UserBase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    UserBase.metadata.create_all(bind=engine)
    AlStyleBase.metadata.create_all(bind=engine)
    SyncLogBase.metadata.create_all(bind=engine)
    logging.getLogger(__name__).info("Таблицы БД готовы")
    yield


app = FastAPI(
    title="dshopWB API",
    description="Backend для синхронизации с WB и Al-Style.kz",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
app.include_router(sync_router)       # /api/sync/*
app.include_router(alstyle_router)    # /api/alstyle/* (legacy)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}

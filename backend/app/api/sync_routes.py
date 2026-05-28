"""
Роутер управления синхронизациями.

Endpoints:
  POST /api/sync/start       — запустить полную синхронизацию al-style.kz
  POST /api/sync/categories  — только категории
  POST /api/sync/products    — только товары
  GET  /api/sync/status      — статус текущей (или последней) сессии
  GET  /api/sync/history     — история сессий из БД
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models.sync_log import SyncLog
from ..schemas.alstyle import SyncSessionOut, SyncStatsOut
from ..services.alstyle_sync import AlStyleSyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["Sync"])


# ── In-memory состояние (заменить Redis в продакшне) ──────────────────────────

_state: Dict[str, Any] = {
    "session_id": None,
    "status":     "idle",   # idle | running | done | error
    "message":    None,
    "started_at": None,
}


# ── Фоновая задача ────────────────────────────────────────────────────────────

async def _run_sync(session_id: str, mode: str) -> None:
    _state.update({
        "session_id": session_id,
        "status":     "running",
        "message":    f"Выполняется синхронизация: {mode}",
        "started_at": datetime.utcnow().isoformat(),
    })

    started = datetime.utcnow()
    db = SessionLocal()
    stats: Optional[SyncStatsOut] = None

    try:
        async with AlStyleSyncService() as svc:
            if mode == "categories":
                await svc.sync_categories()
            elif mode == "products":
                await svc.sync_products()
            else:
                await svc.sync_all()
            stats = svc.stats

        finished = datetime.utcnow()
        duration = (finished - started).total_seconds()

        log = db.query(SyncLog).filter(SyncLog.session_id == session_id).first()
        if log:
            log.status           = "done"
            log.finished_at      = finished
            log.duration_seconds = duration
            log.stats            = stats.model_dump() if stats else None
            db.commit()

        _state.update({
            "status":  "done",
            "message": f"Завершено за {duration:.1f} сек.",
        })
        logger.info("Синхронизация %s завершена за %.1f сек.", session_id, duration)

    except Exception as exc:
        finished = datetime.utcnow()
        duration = (finished - started).total_seconds()
        logger.exception("Ошибка синхронизации session=%s", session_id)

        log = db.query(SyncLog).filter(SyncLog.session_id == session_id).first()
        if log:
            log.status           = "error"
            log.finished_at      = finished
            log.duration_seconds = duration
            log.error_message    = str(exc)
            db.commit()

        _state.update({
            "status":  "error",
            "message": str(exc),
        })
    finally:
        db.close()


# ── Вспомогательная функция запуска ──────────────────────────────────────────

def _start_session(mode: str, db: Session, background_tasks: BackgroundTasks) -> SyncSessionOut:
    if _state["status"] == "running":
        raise HTTPException(409, detail="Синхронизация уже выполняется")

    session_id = str(uuid.uuid4())
    now = datetime.utcnow()

    log = SyncLog(
        session_id=session_id,
        component="alstyle",
        mode=mode,
        status="running",
        started_at=now,
    )
    db.add(log)
    db.commit()

    background_tasks.add_task(_run_sync, session_id, mode)

    return SyncSessionOut(
        session_id=session_id,
        component="alstyle",
        mode=mode,
        status="running",
        message="Синхронизация запущена в фоне",
        started_at=now.isoformat(),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints запуска
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/start",
    response_model=SyncSessionOut,
    summary="Запустить полную синхронизацию al-style.kz",
    description=(
        "Запускает синхронизацию в фоне: категории → товары (с характеристиками, "
        "ценами, остатками, изображениями). Возвращает session_id для отслеживания."
    ),
)
async def sync_start(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _start_session("all", db, background_tasks)


@router.post(
    "/categories",
    response_model=SyncSessionOut,
    summary="Синхронизировать только категории",
)
async def sync_categories(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _start_session("categories", db, background_tasks)


@router.post(
    "/products",
    response_model=SyncSessionOut,
    summary="Синхронизировать только товары (нужны актуальные категории в БД)",
)
async def sync_products(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _start_session("products", db, background_tasks)


# ═════════════════════════════════════════════════════════════════════════════
# Статус и история
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/status",
    response_model=SyncSessionOut,
    summary="Статус текущей (или последней) сессии синхронизации",
)
async def sync_status(db: Session = Depends(get_db)):
    session_id = _state.get("session_id")
    if not session_id:
        return SyncSessionOut(
            session_id="",
            component="alstyle",
            mode="",
            status="idle",
            message="Синхронизация ещё не запускалась",
            started_at="",
        )

    log = db.query(SyncLog).filter(SyncLog.session_id == session_id).first()
    if not log:
        return SyncSessionOut(
            session_id=session_id,
            component="alstyle",
            mode="",
            status=_state["status"],
            message=_state.get("message"),
            started_at=_state.get("started_at") or "",
        )

    return _log_to_schema(log, message=_state.get("message"))


@router.get(
    "/history",
    response_model=List[SyncSessionOut],
    summary="История сессий синхронизации из БД",
)
def sync_history(
    db: Session = Depends(get_db),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):
    logs = (
        db.query(SyncLog)
        .order_by(SyncLog.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_log_to_schema(log) for log in logs]


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _log_to_schema(log: SyncLog, message: Optional[str] = None) -> SyncSessionOut:
    stats: Optional[SyncStatsOut] = None
    if log.stats:
        try:
            stats = SyncStatsOut(**log.stats)
        except Exception:
            pass

    return SyncSessionOut(
        session_id=log.session_id,
        component=log.component,
        mode=log.mode,
        status=log.status,
        message=message or log.error_message,
        started_at=log.started_at.isoformat() if log.started_at else "",
        finished_at=log.finished_at.isoformat() if log.finished_at else None,
        duration_seconds=log.duration_seconds,
        stats=stats,
        error_message=log.error_message,
    )

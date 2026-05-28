"""
FastAPI-маршруты для управления синхронизацией al-style.kz.

Endpoints:
  POST /api/alstyle/sync/all        — полная синхронизация (фоновая задача)
  POST /api/alstyle/sync/categories — только категории
  POST /api/alstyle/sync/products   — только товары
  GET  /api/alstyle/sync/status     — статус последней синхронизации
  GET  /api/alstyle/categories      — список категорий из БД
  GET  /api/alstyle/products        — список товаров из БД
  GET  /api/alstyle/products/{id}   — детали товара
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.alstyle import (
    AlStyleCategory,
    AlStyleProduct,
    AlStyleProductAttribute,
    AlStyleProductImage,
    AlStyleProductStock,
)
from ..schemas.alstyle import SyncStatsOut, SyncStatusOut
from ..services.alstyle_sync import AlStyleSyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alstyle", tags=["AlStyle"])


# ── Глобальное состояние синхронизации ────────────────────────────────────────
# (в продакшне заменить на Redis/Celery/etc.)
_sync_state: Dict[str, Any] = {
    "status":  "idle",   # idle | running | done | error
    "message": None,
    "stats":   None,
}


# ═════════════════════════════════════════════════════════════════════════════
# Синхронизация
# ═════════════════════════════════════════════════════════════════════════════

async def _run_sync_task(mode: str) -> None:
    """Фоновая задача синхронизации."""
    _sync_state["status"]  = "running"
    _sync_state["message"] = f"Выполняется: {mode}"
    _sync_state["stats"]   = None

    try:
        async with AlStyleSyncService() as svc:
            if mode == "categories":
                await svc.sync_categories()
            elif mode == "products":
                await svc.sync_products()
            else:
                await svc.sync_all()

            _sync_state["stats"]   = svc.stats.dict()
            _sync_state["status"]  = "done"
            _sync_state["message"] = "Завершено успешно"

    except Exception as exc:
        logger.exception("Ошибка синхронизации al-style.kz")
        _sync_state["status"]  = "error"
        _sync_state["message"] = str(exc)


@router.post(
    "/sync/all",
    response_model=SyncStatusOut,
    summary="Полная синхронизация (категории + товары + изображения)",
)
async def sync_all(background_tasks: BackgroundTasks):
    if _sync_state["status"] == "running":
        raise HTTPException(409, detail="Синхронизация уже выполняется")
    background_tasks.add_task(_run_sync_task, "all")
    return SyncStatusOut(status="running", message="Синхронизация запущена в фоне")


@router.post(
    "/sync/categories",
    response_model=SyncStatusOut,
    summary="Синхронизировать только категории",
)
async def sync_categories(background_tasks: BackgroundTasks):
    if _sync_state["status"] == "running":
        raise HTTPException(409, detail="Синхронизация уже выполняется")
    background_tasks.add_task(_run_sync_task, "categories")
    return SyncStatusOut(status="running", message="Синхронизация категорий запущена")


@router.post(
    "/sync/products",
    response_model=SyncStatusOut,
    summary="Синхронизировать только товары",
)
async def sync_products(background_tasks: BackgroundTasks):
    if _sync_state["status"] == "running":
        raise HTTPException(409, detail="Синхронизация уже выполняется")
    background_tasks.add_task(_run_sync_task, "products")
    return SyncStatusOut(status="running", message="Синхронизация товаров запущена")


@router.get(
    "/sync/status",
    response_model=SyncStatusOut,
    summary="Статус последней синхронизации",
)
async def sync_status():
    stats = None
    if _sync_state.get("stats"):
        stats = SyncStatsOut(**_sync_state["stats"])
    return SyncStatusOut(
        status=_sync_state["status"],
        message=_sync_state["message"],
        stats=stats,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Чтение данных из БД
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/categories",
    summary="Список категорий из БД",
)
def list_categories(
    db: Session = Depends(get_db),
    parent_id: Optional[str] = Query(None, description="Фильтр по parent_id"),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
):
    q = db.query(AlStyleCategory).filter(AlStyleCategory.is_active == True)
    if parent_id is not None:
        q = q.filter(AlStyleCategory.parent_id == parent_id)
    total = q.count()
    items = q.order_by(AlStyleCategory.sort_order, AlStyleCategory.name) \
             .offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id":          c.id,
                "external_id": c.external_id,
                "parent_id":   c.parent_id,
                "name":        c.name,
                "sort_order":  c.sort_order,
            }
            for c in items
        ],
    }


@router.get(
    "/products",
    summary="Список товаров из БД",
)
def list_products(
    db: Session = Depends(get_db),
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None, description="Поиск по названию / артикулу"),
    in_stock: Optional[bool] = Query(None, description="Только товары с остатком > 0"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    q = db.query(AlStyleProduct).filter(AlStyleProduct.is_active == True)

    if category_id is not None:
        q = q.filter(AlStyleProduct.category_id == category_id)

    if search:
        like = f"%{search}%"
        q = q.filter(
            AlStyleProduct.name.ilike(like) | AlStyleProduct.sku.ilike(like)
        )

    if in_stock:
        q = q.filter(
            AlStyleProduct.stocks.any(AlStyleProductStock.quantity > 0)
        )

    total = q.count()
    products = q.order_by(AlStyleProduct.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [_product_to_dict(p) for p in products],
    }


@router.get(
    "/products/{product_id}",
    summary="Детали одного товара",
)
def get_product(product_id: int, db: Session = Depends(get_db)):
    prod = db.query(AlStyleProduct).filter(AlStyleProduct.id == product_id).first()
    if not prod:
        raise HTTPException(404, detail="Товар не найден")
    return _product_to_dict(prod, full=True)


# ── Вспомогательные функции ──────────────────────────────────────────────────

def _product_to_dict(p: AlStyleProduct, full: bool = False) -> dict:
    base = {
        "id":           p.id,
        "external_id":  p.external_id,
        "category_id":  p.category_id,
        "sku":          p.sku,
        "name":         p.name,
        "price":        float(p.price) if p.price is not None else None,
        "price_retail": float(p.price_retail) if p.price_retail is not None else None,
        "currency":     p.currency,
        "is_active":    p.is_active,
        "synced_at":    p.synced_at.isoformat() if p.synced_at else None,
        # Суммарный остаток
        "total_stock":  sum(s.quantity for s in p.stocks),
        # Основное изображение
        "main_image": next(
            (img.local_path or img.url for img in p.images if img.is_main),
            (p.images[0].local_path or p.images[0].url) if p.images else None,
        ),
    }

    if full:
        base.update({
            "barcode":     p.barcode,
            "description": p.description,
            "weight":      p.weight,
            "attributes":  [{"name": a.name, "value": a.value} for a in p.attributes],
            "images":      [
                {
                    "url":        img.local_path or img.url,
                    "sort_order": img.sort_order,
                    "is_main":    img.is_main,
                }
                for img in sorted(p.images, key=lambda x: x.sort_order)
            ],
            "stocks": [
                {"warehouse": s.warehouse, "quantity": s.quantity}
                for s in p.stocks
            ],
        })

    return base

"""
Pydantic v2 схемы для парсинга ответов al-style.kz API.

Схемы намеренно сделаны мягкими (все поля Optional) —
разные версии API могут возвращать разные наборы полей.
"""

from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Вспомогательные ───────────────────────────────────────────────────────────

class AlStyleAttribute(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    value: Optional[str] = None


class AlStyleImage(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    url: str
    sort_order: Optional[int] = Field(None, alias="sort")
    is_main: Optional[bool] = False


class AlStyleStock(BaseModel):
    model_config = ConfigDict(extra="allow")

    warehouse: Optional[str] = "default"
    quantity: int = 0


# ── Категория ─────────────────────────────────────────────────────────────────

class AlStyleCategoryItem(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    parent_id: Optional[str] = None
    name: str
    sort_order: Optional[int] = 0
    is_active: Optional[bool] = True

    @field_validator("id", "parent_id", mode="before")
    @classmethod
    def coerce_to_str(cls, v: Any) -> Optional[str]:
        return None if v is None else str(v)


class AlStyleCategoriesResponse(BaseModel):
    categories: List[AlStyleCategoryItem] = []


# ── Товар ─────────────────────────────────────────────────────────────────────

class AlStyleProductItem(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    category_id: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    name: str
    description: Optional[str] = None

    price: Optional[Decimal] = None
    price_retail: Optional[Decimal] = None
    currency: Optional[str] = "KZT"

    weight: Optional[float] = None
    volume: Optional[float] = None
    is_active: Optional[bool] = True

    attributes: List[AlStyleAttribute] = []
    images: List[AlStyleImage] = []
    stocks: List[AlStyleStock] = []

    @field_validator("id", "category_id", mode="before")
    @classmethod
    def coerce_to_str(cls, v: Any) -> Optional[str]:
        return None if v is None else str(v)

    @field_validator("price", "price_retail", mode="before")
    @classmethod
    def coerce_decimal(cls, v: Any) -> Optional[Decimal]:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None


class AlStyleProductsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    products: List[AlStyleProductItem] = []
    total: Optional[int] = None
    page: Optional[int] = 1
    pages: Optional[int] = None
    per_page: Optional[int] = None


# ── Ответы синхронизации ──────────────────────────────────────────────────────

class SyncStatsOut(BaseModel):
    categories_created: int = 0
    categories_updated: int = 0
    products_created:   int = 0
    products_updated:   int = 0
    images_saved:       int = 0
    stocks_updated:     int = 0
    errors:             List[str] = []


class SyncStatusOut(BaseModel):
    status:  str
    message: Optional[str] = None
    stats:   Optional[SyncStatsOut] = None


class SyncSessionOut(BaseModel):
    """Полная информация о сессии синхронизации."""
    session_id:       str
    component:        str
    mode:             str
    status:           str
    message:          Optional[str] = None
    started_at:       str
    finished_at:      Optional[str] = None
    duration_seconds: Optional[float] = None
    stats:            Optional[SyncStatsOut] = None
    error_message:    Optional[str] = None

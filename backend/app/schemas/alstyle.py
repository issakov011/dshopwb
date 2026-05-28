"""
Pydantic-схемы для парсинга ответов al-style.kz API.

Схемы намеренно сделаны мягкими (все поля Optional) —
разные версии API могут возвращать разные наборы полей.
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal

from pydantic import BaseModel, Field, validator


# ─── Вспомогательные ───────────────────────────────────────────────────────────

class AlStyleAttribute(BaseModel):
    name:  str
    value: Optional[str] = None

    class Config:
        extra = "allow"


class AlStyleImage(BaseModel):
    url:        str
    sort_order: Optional[int] = Field(None, alias="sort")
    is_main:    Optional[bool] = False

    class Config:
        extra = "allow"
        allow_population_by_field_name = True


class AlStyleStock(BaseModel):
    warehouse: Optional[str] = "default"
    quantity:  int = 0

    class Config:
        extra = "allow"


# ─── Категория ─────────────────────────────────────────────────────────────────

class AlStyleCategoryItem(BaseModel):
    """Одна запись из /api/categories."""
    id:         str = Field(..., alias="id")
    parent_id:  Optional[str] = Field(None, alias="parent_id")
    name:       str
    sort_order: Optional[int] = 0
    is_active:  Optional[bool] = True

    @validator("id", "parent_id", pre=True)
    def coerce_to_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    class Config:
        extra = "allow"
        allow_population_by_field_name = True


class AlStyleCategoriesResponse(BaseModel):
    """Корневой объект ответа /api/categories."""
    categories: List[AlStyleCategoryItem] = []

    # Некоторые API возвращают список напрямую — обрабатываем в клиенте


# ─── Товар ─────────────────────────────────────────────────────────────────────

class AlStyleProductItem(BaseModel):
    """Одна запись из /products или /api/products."""
    id:           str = Field(..., alias="id")
    category_id:  Optional[str] = Field(None, alias="category_id")
    sku:          Optional[str] = None
    barcode:      Optional[str] = None
    name:         str
    description:  Optional[str] = None

    # Цены
    price:        Optional[Decimal] = None
    price_retail: Optional[Decimal] = Field(None, alias="price_retail")
    currency:     Optional[str] = "KZT"

    # Физ. свойства
    weight:       Optional[float] = None
    volume:       Optional[float] = None

    is_active:    Optional[bool] = True

    # Вложенные коллекции
    attributes:   List[AlStyleAttribute] = []
    images:       List[AlStyleImage] = []
    stocks:       List[AlStyleStock] = []

    @validator("id", "category_id", pre=True)
    def coerce_to_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    @validator("price", "price_retail", pre=True)
    def coerce_decimal(cls, v: Any) -> Optional[Decimal]:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    class Config:
        extra = "allow"
        allow_population_by_field_name = True


class AlStyleProductsResponse(BaseModel):
    """Корневой объект ответа /products."""
    products: List[AlStyleProductItem] = []
    total:    Optional[int] = None
    page:     Optional[int] = 1
    pages:    Optional[int] = None
    per_page: Optional[int] = None

    class Config:
        extra = "allow"


# ─── Ответы синхронизации (для FastAPI эндпоинтов) ─────────────────────────────

class SyncStatsOut(BaseModel):
    categories_created:  int = 0
    categories_updated:  int = 0
    products_created:    int = 0
    products_updated:    int = 0
    images_saved:        int = 0
    stocks_updated:      int = 0
    errors:              List[str] = []


class SyncStatusOut(BaseModel):
    status:   str          # "idle" | "running" | "done" | "error"
    message:  Optional[str] = None
    stats:    Optional[SyncStatsOut] = None

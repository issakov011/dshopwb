"""
Модели для хранения данных от al-style.kz API.

Схема:
  alstyle_categories        — дерево категорий поставщика
  alstyle_products          — товары (цены, артикул, описание)
  alstyle_product_attributes — характеристики товара (ключ-значение)
  alstyle_product_images     — изображения товара
  alstyle_product_stocks     — остатки по складам
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class AlStyleCategory(Base):
    __tablename__ = "alstyle_categories"

    id          = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), unique=True, nullable=False, index=True,
                         comment="ID категории на стороне al-style.kz")
    parent_id   = Column(String(64), nullable=True, index=True,
                         comment="external_id родительской категории (NULL = корень)")
    name        = Column(String(512), nullable=False)
    sort_order  = Column(Integer, default=0)
    is_active   = Column(Boolean, default=True)
    synced_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = relationship("AlStyleProduct", back_populates="category",
                            lazy="dynamic")

    def __repr__(self) -> str:
        return f"<AlStyleCategory id={self.external_id!r} name={self.name!r}>"


class AlStyleProduct(Base):
    __tablename__ = "alstyle_products"

    id          = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(64), unique=True, nullable=False, index=True,
                         comment="ID товара на стороне al-style.kz")
    category_id = Column(Integer, ForeignKey("alstyle_categories.id",
                                             ondelete="SET NULL"), nullable=True, index=True)

    # Идентификаторы
    sku         = Column(String(128), nullable=True, index=True,
                         comment="Артикул поставщика")
    barcode     = Column(String(64),  nullable=True, index=True)

    # Описание
    name        = Column(String(1024), nullable=False)
    description = Column(Text, nullable=True)

    # Цены (хранятся в тенге)
    price           = Column(Numeric(14, 2), nullable=True,
                             comment="Закупочная / дилерская цена")
    price_retail    = Column(Numeric(14, 2), nullable=True,
                             comment="Рекомендуемая розничная цена")
    currency        = Column(String(8), default="KZT")

    # Физические свойства
    weight      = Column(Float, nullable=True, comment="Вес, кг")
    volume      = Column(Float, nullable=True, comment="Объём, м³")

    # Флаги
    is_active   = Column(Boolean, default=True)

    # Временны́е метки
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    category   = relationship("AlStyleCategory", back_populates="products")
    attributes = relationship("AlStyleProductAttribute", back_populates="product",
                              cascade="all, delete-orphan")
    images     = relationship("AlStyleProductImage", back_populates="product",
                              cascade="all, delete-orphan",
                              order_by="AlStyleProductImage.sort_order")
    stocks     = relationship("AlStyleProductStock", back_populates="product",
                              cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AlStyleProduct sku={self.sku!r} name={self.name!r}>"


class AlStyleProductAttribute(Base):
    """Характеристика товара (процессор, ОЗУ, диагональ, …)."""
    __tablename__ = "alstyle_product_attributes"
    __table_args__ = (
        UniqueConstraint("product_id", "name", name="uq_attr_product_name"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("alstyle_products.id",
                                            ondelete="CASCADE"), nullable=False, index=True)
    name       = Column(String(256), nullable=False)
    value      = Column(Text, nullable=True)

    product = relationship("AlStyleProduct", back_populates="attributes")

    def __repr__(self) -> str:
        return f"<Attr {self.name!r}={self.value!r}>"


class AlStyleProductImage(Base):
    """Изображение товара."""
    __tablename__ = "alstyle_product_images"

    id          = Column(Integer, primary_key=True, index=True)
    product_id  = Column(Integer, ForeignKey("alstyle_products.id",
                                             ondelete="CASCADE"), nullable=False, index=True)
    url         = Column(String(2048), nullable=False,
                         comment="Оригинальный URL изображения на al-style.kz")
    local_path  = Column(String(512), nullable=True,
                         comment="Локальный путь, если изображение скачано")
    sort_order  = Column(Integer, default=0)
    is_main     = Column(Boolean, default=False)

    product = relationship("AlStyleProduct", back_populates="images")

    def __repr__(self) -> str:
        return f"<Image product_id={self.product_id} sort={self.sort_order}>"


class AlStyleProductStock(Base):
    """Остаток товара на конкретном складе."""
    __tablename__ = "alstyle_product_stocks"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse", name="uq_stock_product_warehouse"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("alstyle_products.id",
                                            ondelete="CASCADE"), nullable=False, index=True)
    warehouse  = Column(String(256), nullable=False, default="default",
                        comment="Название склада / города")
    quantity   = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("AlStyleProduct", back_populates="stocks")

    def __repr__(self) -> str:
        return f"<Stock warehouse={self.warehouse!r} qty={self.quantity}>"

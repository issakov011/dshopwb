"""
Сервис синхронизации данных из al-style.kz → PostgreSQL.

Логика upsert (insert-or-update) построена через external_id,
поэтому повторный запуск безопасен — дублей не будет.

Порядок шагов:
  1. Категории  — sync_categories()
  2. Товары      — sync_products()  (с характеристиками, ценами, остатками)
  3. Изображения — sync_images()   (опционально скачивает файлы)
  4. Полный цикл — sync_all()
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..core.config import settings
from ..database import SessionLocal
from ..models.alstyle import (
    AlStyleCategory,
    AlStyleProduct,
    AlStyleProductAttribute,
    AlStyleProductImage,
    AlStyleProductStock,
)
from ..schemas.alstyle import (
    AlStyleCategoryItem,
    AlStyleProductItem,
    AlStyleAttribute,
    AlStyleImage,
    AlStyleStock,
    SyncStatsOut,
)
from .alstyle_client import AlStyleClient, AlStyleAPIError

logger = logging.getLogger(__name__)

# Куда сохранять изображения (если ALSTYLE_DOWNLOAD_IMAGES=True)
IMAGES_DIR = Path("/app/media/alstyle")


class AlStyleSyncService:
    """
    Синхронизирует каталог al-style.kz с локальной базой данных.

    Пример использования:
        async with AlStyleSyncService() as svc:
            stats = await svc.sync_all()
            print(stats)
    """

    def __init__(self, db: Optional[Session] = None):
        self._owns_db = db is None
        self.db = db or SessionLocal()
        self.stats = SyncStatsOut()

    # ── Жизненный цикл ────────────────────────────────────────────────────────

    async def __aenter__(self) -> "AlStyleSyncService":
        return self

    async def __aexit__(self, *_) -> None:
        if self._owns_db:
            self.db.close()

    # ═════════════════════════════════════════════════════════════════════════
    # 1. КАТЕГОРИИ
    # ═════════════════════════════════════════════════════════════════════════

    async def sync_categories(self) -> None:
        """Загружает и сохраняет все категории."""
        logger.info("=== Синхронизация категорий ===")

        async with AlStyleClient() as client:
            raw_list = await client.get_categories()

        logger.info("Получено %d категорий от API", len(raw_list))

        for raw in raw_list:
            try:
                item = AlStyleCategoryItem(**raw)
                self._upsert_category(item)
            except Exception as exc:
                msg = f"Ошибка обработки категории {raw}: {exc}"
                logger.error(msg)
                self.stats.errors.append(msg)

        self.db.commit()
        logger.info("Категории сохранены: создано=%d, обновлено=%d",
                    self.stats.categories_created, self.stats.categories_updated)

    def _upsert_category(self, item: AlStyleCategoryItem) -> AlStyleCategory:
        cat = (
            self.db.query(AlStyleCategory)
            .filter(AlStyleCategory.external_id == item.id)
            .first()
        )
        if cat is None:
            cat = AlStyleCategory(external_id=item.id)
            self.db.add(cat)
            self.stats.categories_created += 1
        else:
            self.stats.categories_updated += 1

        cat.parent_id  = item.parent_id
        cat.name       = item.name
        cat.sort_order = item.sort_order or 0
        cat.is_active  = item.is_active if item.is_active is not None else True
        cat.synced_at  = datetime.utcnow()
        return cat

    # ═════════════════════════════════════════════════════════════════════════
    # 2. ТОВАРЫ (+ характеристики, цены, остатки)
    # ═════════════════════════════════════════════════════════════════════════

    async def sync_products(self) -> None:
        """
        Загружает и сохраняет все товары постранично.
        Для каждого товара сохраняет:
          - основные поля (цена, артикул, описание)
          - характеристики (attributes)
          - изображения (ссылки)
          - остатки (stocks)
        """
        logger.info("=== Синхронизация товаров ===")

        # Кэш category external_id → internal id
        cat_map: Dict[str, int] = {
            c.external_id: c.id
            for c in self.db.query(AlStyleCategory.external_id, AlStyleCategory.id).all()
        }

        page_num = 0
        async with AlStyleClient() as client:
            async for batch in client.iter_products(
                per_page=settings.ALSTYLE_PAGE_SIZE
            ):
                page_num += 1
                logger.info("Обрабатываю страницу %d (%d товаров)", page_num, len(batch))

                for raw in batch:
                    try:
                        item = AlStyleProductItem(**raw)
                        self._upsert_product(item, cat_map)
                    except Exception as exc:
                        pid = raw.get("id", "?")
                        msg = f"Ошибка товара id={pid}: {exc}"
                        logger.error(msg)
                        self.stats.errors.append(msg)

                # Коммитим каждую страницу — не держим всё в памяти
                self.db.commit()
                logger.info("Страница %d сохранена. Итого: создано=%d, обновлено=%d",
                            page_num,
                            self.stats.products_created,
                            self.stats.products_updated)

        logger.info("Товары синхронизированы: создано=%d, обновлено=%d, ошибок=%d",
                    self.stats.products_created, self.stats.products_updated,
                    len(self.stats.errors))

    def _upsert_product(
        self,
        item: AlStyleProductItem,
        cat_map: Dict[str, int],
    ) -> AlStyleProduct:
        prod = (
            self.db.query(AlStyleProduct)
            .filter(AlStyleProduct.external_id == item.id)
            .first()
        )
        if prod is None:
            prod = AlStyleProduct(external_id=item.id)
            self.db.add(prod)
            self.stats.products_created += 1
        else:
            self.stats.products_updated += 1

        # Основные поля
        prod.category_id  = cat_map.get(item.category_id) if item.category_id else None
        prod.sku          = item.sku
        prod.barcode      = item.barcode
        prod.name         = item.name
        prod.description  = item.description
        prod.price        = item.price
        prod.price_retail = item.price_retail
        prod.currency     = item.currency or "KZT"
        prod.weight       = item.weight
        prod.volume       = item.volume
        prod.is_active    = item.is_active if item.is_active is not None else True
        prod.updated_at   = datetime.utcnow()
        prod.synced_at    = datetime.utcnow()

        # Нужно flush, чтобы получить prod.id для вложенных таблиц
        self.db.flush()

        # Характеристики
        self._sync_attributes(prod, item.attributes)

        # Изображения
        self._sync_images(prod, item.images)

        # Остатки
        self._sync_stocks(prod, item.stocks)

        return prod

    # ── Характеристики ────────────────────────────────────────────────────────

    def _sync_attributes(
        self,
        prod: AlStyleProduct,
        attrs: List[AlStyleAttribute],
    ) -> None:
        if not attrs:
            return

        # Удаляем старые
        self.db.query(AlStyleProductAttribute).filter(
            AlStyleProductAttribute.product_id == prod.id
        ).delete(synchronize_session=False)

        for a in attrs:
            self.db.add(AlStyleProductAttribute(
                product_id=prod.id,
                name=str(a.name).strip(),
                value=str(a.value).strip() if a.value is not None else None,
            ))

    # ── Изображения ───────────────────────────────────────────────────────────

    def _sync_images(
        self,
        prod: AlStyleProduct,
        images: List[AlStyleImage],
    ) -> None:
        if not images:
            return

        # Текущий набор URL-ов из БД
        existing: Dict[str, AlStyleProductImage] = {
            img.url: img
            for img in self.db.query(AlStyleProductImage).filter(
                AlStyleProductImage.product_id == prod.id
            ).all()
        }

        new_urls = {img.url for img in images}

        # Удаляем исчезнувшие
        for url, db_img in existing.items():
            if url not in new_urls:
                self.db.delete(db_img)

        # Добавляем / обновляем
        for i, img in enumerate(images):
            if not img.url:
                continue
            sort = img.sort_order if img.sort_order is not None else i
            is_main = bool(img.is_main) or (i == 0)

            if img.url in existing:
                db_img = existing[img.url]
                db_img.sort_order = sort
                db_img.is_main    = is_main
            else:
                self.db.add(AlStyleProductImage(
                    product_id=prod.id,
                    url=img.url,
                    sort_order=sort,
                    is_main=is_main,
                ))
                self.stats.images_saved += 1

    # ── Остатки ───────────────────────────────────────────────────────────────

    def _sync_stocks(
        self,
        prod: AlStyleProduct,
        stocks: List[AlStyleStock],
    ) -> None:
        if not stocks:
            return

        existing: Dict[str, AlStyleProductStock] = {
            s.warehouse: s
            for s in self.db.query(AlStyleProductStock).filter(
                AlStyleProductStock.product_id == prod.id
            ).all()
        }

        new_warehouses = {s.warehouse or "default" for s in stocks}

        # Удаляем исчезнувшие склады
        for wh, db_s in existing.items():
            if wh not in new_warehouses:
                self.db.delete(db_s)

        for s in stocks:
            wh = s.warehouse or "default"
            if wh in existing:
                existing[wh].quantity   = s.quantity
                existing[wh].updated_at = datetime.utcnow()
            else:
                self.db.add(AlStyleProductStock(
                    product_id=prod.id,
                    warehouse=wh,
                    quantity=s.quantity,
                ))
            self.stats.stocks_updated += 1

    # ═════════════════════════════════════════════════════════════════════════
    # 3. СКАЧИВАНИЕ ИЗОБРАЖЕНИЙ
    # ═════════════════════════════════════════════════════════════════════════

    async def sync_images(self, limit: Optional[int] = None) -> None:
        """
        Скачивает изображения, у которых ещё нет local_path.
        Запускается только если ALSTYLE_DOWNLOAD_IMAGES=True.
        """
        if not settings.ALSTYLE_DOWNLOAD_IMAGES:
            logger.info("Скачивание изображений отключено (ALSTYLE_DOWNLOAD_IMAGES=False)")
            return

        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        query = (
            self.db.query(AlStyleProductImage)
            .filter(AlStyleProductImage.local_path.is_(None))
            .filter(AlStyleProductImage.url.isnot(None))
        )
        if limit:
            query = query.limit(limit)

        to_download = query.all()
        if not to_download:
            logger.info("Нет новых изображений для скачивания")
            return

        logger.info("Скачиваю %d изображений…", len(to_download))

        async with AlStyleClient() as client:
            for img in to_download:
                try:
                    data = await client.download_image(img.url)
                    if not data:
                        continue

                    # Имя файла = id_sort.ext
                    ext = img.url.rsplit(".", 1)[-1].split("?")[0][:4] or "jpg"
                    fname = f"{img.product_id}_{img.sort_order}.{ext}"
                    fpath = IMAGES_DIR / fname
                    fpath.write_bytes(data)

                    img.local_path = str(fpath)
                    self.stats.images_saved += 1
                    logger.debug("Сохранено: %s", fpath)

                except Exception as exc:
                    msg = f"Ошибка при скачивании {img.url}: {exc}"
                    logger.error(msg)
                    self.stats.errors.append(msg)

        self.db.commit()
        logger.info("Скачано изображений: %d", self.stats.images_saved)

    # ═════════════════════════════════════════════════════════════════════════
    # 4. ПОЛНЫЙ ЦИКЛ
    # ═════════════════════════════════════════════════════════════════════════

    async def sync_all(self) -> SyncStatsOut:
        """
        Полная синхронизация:
          1. Категории
          2. Товары (с характеристиками, ценами, остатками, изображениями-ссылками)
          3. Скачивание изображений (если включено)

        Возвращает статистику.
        """
        logger.info("▶ Начало полной синхронизации al-style.kz")
        start = datetime.utcnow()

        try:
            await self.sync_categories()
            await self.sync_products()
            await self.sync_images()
        except AlStyleAPIError as exc:
            msg = f"API ошибка: {exc}"
            logger.error(msg)
            self.stats.errors.append(msg)
        except Exception as exc:
            msg = f"Неожиданная ошибка: {exc}"
            logger.exception(msg)
            self.stats.errors.append(msg)

        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.info(
            "■ Синхронизация завершена за %.1f сек. | "
            "кат: +%d/~%d | товары: +%d/~%d | изобр: %d | ошибок: %d",
            elapsed,
            self.stats.categories_created, self.stats.categories_updated,
            self.stats.products_created,   self.stats.products_updated,
            self.stats.images_saved,
            len(self.stats.errors),
        )
        return self.stats


# ── Standalone-запуск ────────────────────────────────────────────────────────

async def run_sync() -> SyncStatsOut:
    """Точка входа для запуска синхронизации напрямую (python -m ...)."""
    async with AlStyleSyncService() as svc:
        return await svc.sync_all()


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    stats = asyncio.run(run_sync())
    sys.exit(1 if stats.errors else 0)

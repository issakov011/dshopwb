"""
HTTP-клиент для al-style.kz API.

Особенности:
- Асинхронный (httpx.AsyncClient)
- Авторизация через Bearer-токен
- Автоматический retry (3 попытки с экспоненциальной задержкой)
- Пагинация: итератор get_products_pages()
- Поддержка скачивания изображений

Обнаруженные endpoint-ы (api.al-style.kz):
  GET /api/categories   — список категорий
  GET /products         — список товаров (пагинация)

Все пути задаются через константы ENDPOINTS — легко поправить,
когда получите актуальную документацию от менеджера al-style.kz.
"""

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


# ── Endpoint-ы ──────────────────────────────────────────────────────────────────
ENDPOINTS = {
    "categories":      "/api/categories",
    "products":        "/products",
    # Если API имеет отдельный endpoint для характеристик/изображений — добавь сюда:
    # "product_detail":  "/products/{product_id}",
    # "stocks":          "/api/stocks",
}

# Параметры пагинации (имена query-параметров могут отличаться у разных версий API)
PARAM_PAGE     = "page"
PARAM_PER_PAGE = "limit"  # или "per_page" — поправьте если нужно


class AlStyleAPIError(Exception):
    """Базовое исключение клиента."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class AlStyleClient:
    """Асинхронный клиент al-style.kz API."""

    def __init__(
        self,
        token: Optional[str]  = None,
        base_url: Optional[str] = None,
        timeout: Optional[int]  = None,
    ):
        self.token    = token    or settings.ALSTYLE_TOKEN
        self.base_url = (base_url or settings.ALSTYLE_BASE_URL).rstrip("/")
        self.timeout  = timeout  or settings.ALSTYLE_TIMEOUT
        self._client: Optional[httpx.AsyncClient] = None

    # ── Жизненный цикл ────────────────────────────────────────────────────────

    async def __aenter__(self) -> "AlStyleClient":
        await self._open()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._close()

    async def _open(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._build_headers(),
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )

    async def _close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Авторизация ───────────────────────────────────────────────────────────

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Accept":     "application/json",
            "User-Agent": "dshopWB/1.0 (integration)",
        }
        if self.token:
            # Стандарт Bearer — самый распространённый вариант.
            # Если API требует другой заголовок, поменяй здесь:
            #   "X-Token": self.token
            #   "X-Api-Key": self.token
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # ── Низкоуровневый запрос с retry ─────────────────────────────────────────

    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 3,
    ) -> Any:
        """
        Выполняет GET-запрос с автоматическим retry.
        Возвращает распарсенный JSON (dict или list).
        """
        assert self._client, "Клиент не открыт — используй `async with AlStyleClient()`"

        url = path  # httpx использует base_url + path
        last_exc: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                logger.debug("→ GET %s params=%s (attempt %d/%d)",
                             url, params, attempt, retries)
                resp = await self._client.get(url, params=params)

                if resp.status_code == 401:
                    raise AlStyleAPIError("Неверный токен (401 Unauthorized)",
                                          status_code=401)
                if resp.status_code == 403:
                    raise AlStyleAPIError(
                        "Доступ запрещён (403 Forbidden). "
                        "Проверьте токен и IP-адрес сервера — "
                        "API al-style.kz может быть доступно только из Казахстана.",
                        status_code=403,
                    )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 10))
                    logger.warning("Rate limit (429). Жду %d сек.", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                resp.raise_for_status()

                data = resp.json()
                logger.debug("← %d bytes от %s", len(resp.content), url)
                return data

            except AlStyleAPIError:
                raise  # Не ретраим авторизационные ошибки
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning("Сеть/таймаут (попытка %d/%d): %s. Жду %d сек.",
                                attempt, retries, exc, wait)
                if attempt < retries:
                    await asyncio.sleep(wait)
            except httpx.HTTPStatusError as exc:
                raise AlStyleAPIError(
                    f"HTTP {exc.response.status_code} от {url}",
                    status_code=exc.response.status_code,
                ) from exc

        raise AlStyleAPIError(
            f"Не удалось получить {url} после {retries} попыток: {last_exc}"
        ) from last_exc

    # ── Методы API ────────────────────────────────────────────────────────────

    async def get_categories(self) -> List[Dict[str, Any]]:
        """
        Возвращает плоский список категорий.
        Нормализует оба формата ответа:
          {"categories": [...]}  или  [...]
        """
        data = await self._get(ENDPOINTS["categories"])

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # {"categories": [...]} или {"data": [...]}
            return data.get("categories") or data.get("data") or []

        logger.warning("Неожиданный формат ответа /categories: %s", type(data))
        return []

    async def get_products_page(
        self,
        page: int = 1,
        per_page: int = 100,
        category_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Возвращает одну страницу товаров.
        Нормализует ответ к виду:
          {"products": [...], "total": N, "page": N, "pages": N}
        """
        params: Dict[str, Any] = {
            PARAM_PAGE:     page,
            PARAM_PER_PAGE: per_page,
        }
        if category_id is not None:
            params["category_id"] = category_id

        data = await self._get(ENDPOINTS["products"], params=params)

        if isinstance(data, list):
            # API вернул список напрямую (нет пагинации)
            return {"products": data, "total": len(data), "page": 1, "pages": 1}
        if isinstance(data, dict):
            # Приводим разные ключи к единому виду
            products = (
                data.get("products")
                or data.get("items")
                or data.get("data")
                or []
            )
            return {
                "products": products,
                "total":    data.get("total") or data.get("count") or len(products),
                "page":     data.get("page", page),
                "pages":    data.get("pages") or data.get("total_pages") or 1,
            }

        return {"products": [], "total": 0, "page": 1, "pages": 1}

    async def iter_products(
        self,
        per_page: int = 100,
        category_id: Optional[str] = None,
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """
        Асинхронный итератор по всем страницам товаров.

        Пример использования:
            async for batch in client.iter_products():
                process(batch)
        """
        page = 1
        while True:
            result = await self.get_products_page(
                page=page, per_page=per_page, category_id=category_id
            )
            products = result.get("products", [])
            total_pages = result.get("pages", 1)

            if not products:
                break

            logger.info("Страница %d/%d — %d товаров", page, total_pages, len(products))
            yield products

            if page >= total_pages:
                break
            page += 1

    async def download_image(self, url: str) -> Optional[bytes]:
        """
        Скачивает изображение по URL.
        Используется, если ALSTYLE_DOWNLOAD_IMAGES=True.
        """
        assert self._client, "Клиент не открыт"
        try:
            resp = await self._client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            logger.warning("Не удалось скачать изображение %s: %s", url, exc)
            return None

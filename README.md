# dshopWB — Дропшиппинг: Al-Style.kz → Wildberries

Автоматизация выгрузки товаров поставщика [al-style.kz](https://al-style.kz) на маркетплейс [Wildberries](https://wildberries.ru).

## Стек

| Компонент | Технологии |
|---|---|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy, Alembic, httpx |
| **База данных** | PostgreSQL 15 |
| **Frontend** | React 18 (admin-панель) |
| **Telegram Bot** | aiogram |
| **Деплой** | Docker + docker-compose |

## Возможности

- 📦 **Синхронизация каталога** — категории, товары, характеристики, цены, остатки
- 🖼️ **Изображения** — сохранение ссылок (опционально скачивание локально)
- 🔄 **Upsert-логика** — повторный запуск безопасен, дублей не создаёт
- 🤖 **Telegram-уведомления** — о новых заказах, ошибках, статусах
- 📊 **REST API** — полный CRUD + эндпоинты синхронизации
- 🐳 **Docker-ready** — один `docker-compose up` для локального запуска

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/<ваш-username>/dshopWB.git
cd dshopWB
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
```

Открыть `.env` и заполнить:

```env
# Postgres
POSTGRES_PASSWORD=ваш_надёжный_пароль
DATABASE_URL=postgresql://postgres:ваш_надёжный_пароль@db:5432/dshop

# Безопасность
SECRET_KEY=длинная_случайная_строка

# Telegram бот (от @BotFather)
TELEGRAM_TOKEN=1234567890:AABBccDD...

# Wildberries API
WB_API_KEY=eyJhbGciOi...

# Al-Style.kz API (получить у менеджера al-style.kz)
ALSTYLE_TOKEN=ваш_токен
```

### 3. Запустить

```bash
docker-compose up --build
```

| Сервис | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |

## Структура проекта

```
dshopWB/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py              # Основные маршруты
│   │   │   └── alstyle_routes.py      # Маршруты al-style.kz
│   │   ├── core/
│   │   │   └── config.py              # Настройки (pydantic BaseSettings)
│   │   ├── models/
│   │   │   ├── user.py                # Модель пользователя
│   │   │   └── alstyle.py             # Модели каталога al-style.kz
│   │   ├── schemas/
│   │   │   └── alstyle.py             # Pydantic-схемы ответов API
│   │   ├── services/
│   │   │   ├── alstyle_client.py      # HTTP-клиент al-style.kz
│   │   │   └── alstyle_sync.py        # Сервис синхронизации
│   │   ├── database.py                # Подключение к PostgreSQL
│   │   └── main.py                    # FastAPI app
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                          # React admin-панель
├── bot/                               # Telegram бот (aiogram)
├── deploy/                            # Конфигурация деплоя
├── docker-compose.yml
├── .env.example                       # Шаблон переменных окружения
└── CLAUDE.md                          # Техническая документация
```

## API Документация

После запуска доступна Swagger UI: **http://localhost:8000/docs**

### Синхронизация Al-Style.kz

```http
# Запустить полную синхронизацию
POST /api/alstyle/sync/all

# Только категории
POST /api/alstyle/sync/categories

# Только товары
POST /api/alstyle/sync/products

# Статус последнего запуска
GET  /api/alstyle/sync/status

# Данные из БД
GET  /api/alstyle/categories
GET  /api/alstyle/products?search=asus&in_stock=true
GET  /api/alstyle/products/{id}
```

### Схема БД (Al-Style)

```
alstyle_categories          — дерево категорий поставщика
alstyle_products            — товары (SKU, цены, описание)
alstyle_product_attributes  — характеристики (ключ-значение)
alstyle_product_images      — ссылки на изображения
alstyle_product_stocks      — остатки по складам
```

## Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `DATABASE_URL` | ✅ | URL подключения к PostgreSQL |
| `SECRET_KEY` | ✅ | Секрет для JWT |
| `ALSTYLE_TOKEN` | ✅ | Токен API al-style.kz |
| `WB_API_KEY` | ✅ | API-ключ Wildberries |
| `TELEGRAM_TOKEN` | ⬜ | Токен Telegram-бота |
| `ALSTYLE_BASE_URL` | ⬜ | Базовый URL API (по умолчанию `https://api.al-style.kz`) |
| `ALSTYLE_PAGE_SIZE` | ⬜ | Товаров на страницу (по умолчанию `100`) |
| `ALSTYLE_DOWNLOAD_IMAGES` | ⬜ | Скачивать изображения локально (`false`) |

## Разработка

```bash
# Только backend + БД (без frontend)
docker-compose up db backend

# Запуск миграций
docker-compose exec backend alembic upgrade head

# Запустить синхронизацию вручную (из контейнера)
docker-compose exec backend python -m app.services.alstyle_sync

# Логи
docker-compose logs -f backend
```

## Лицензия

MIT

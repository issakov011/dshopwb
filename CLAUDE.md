Проект: dshopWB — интеграция дропшиппинга al-style.kz → Wildberries

Цель
- Автоматизировать выгрузку товаров и управление заказами между поставщиком (al-style.kz) и маркетплейсом Wildberries.
- Предоставить админ-панель для управления товарами, синхронизацией, логами и ручной корректировки.
- Реализовать чат-бота в Telegram для уведомлений и быстрых команд администратора.

Компоненты
1) Backend (FastAPI)
- REST API для управления товарами, каталогом, заказами, синхронизацией и авторизацией.
- Модуль импорта/экспорта (parsers) для interaction с al-style.kz (CSV/Excel/API).
- Сервис интеграции с Wildberries (формирование прайс-листов, выгрузка остатков, приём статусов заказов).
- Планировщик задач (cron/ Celery / APScheduler) для периодической синхронизации.
- Подключение к PostgreSQL.

2) Frontend (React)
- Админ-панель: авторизация, список товаров, карточка товара, лог синхронизаций, ручные операции (push/pull), настройки интеграций.
- Отдельные страницы: Dashboard, Products, Orders, Sync Log, Settings, Users.

3) Telegram Bot (aiogram)
- Уведомления о критических ошибках, новых заказах, успешной загрузке.
- Команды для админа: /status, /sync_now, /last_errors, /orders_today.

4) Деплой (Docker)
- docker-compose для локальной разработки: services: backend, frontend, bot, db (Postgres).
- В production: рекомендую использовать Kubernetes или Docker Swarm + CI (GitHub Actions/GitLab CI) с секрктами и автомасштабированием.

Архитектура данных (кратко)
- users (id, email, hashed_password, role)
- products (id, sku, title, description, price, stock, metadata JSON)
- wb_products (id, product_id, wb_sku, wb_status, last_sync)
- orders (id, wb_order_id, product_id, quantity, price, status, created_at)
- sync_logs (id, component, level, message, meta JSON, created_at)

Ключевые API endpoints (пример)
- POST /auth/login — получить JWT
- GET /health — проверка статуса
- GET /products — список товаров (фильтры)
- POST /products — создать товар
- POST /sync/wb — запустить синхронизацию с WB
- GET /orders — заказы

Авторизация
- JWT с ролью пользователя (admin/ops).
- Рефреш-токены (опционально).

Env переменные (минимум)
- POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
- DATABASE_URL
- TELEGRAM_TOKEN
- SECRET_KEY
- WB_API_KEY (если требуется)

Локальный запуск (пример)
1) Наличие Docker и docker-compose
2) Копировать `.env.example` → `.env` и заполнить
3) В корне: `docker-compose up --build`

CI/CD рекомендации
- Сборка образов для backend и frontend, запуск тестов, сканирование уязвимостей.
- Миграции БД (alembic) перед релизом.

Мониторинг и логирование
- Логи сохранять в файл/stdout и агрегировать (ELK/Promtail+Loki).
- Метрики: Prometheus + Grafana.

Безопасность
- Защищать секреты через секрет-хранилище (Vault/Azure KeyVault/Secrets Manager).
- Ограничить доступ к админ-панели по IP (optionally) и включить MFA.

Дальнейшие шаги
- Добавить модуль тестов (unit + integration)
- Настроить миграции (alembic)
- Реализовать обработчики ошибок и ретраи для внешних запросов

Контакты и примечания
- Этот файл — техническое описание и стартовая документация для разработчиков и девопс-инженеров.
- При необходимости могу сгенерировать примеры OpenAPI, ER-диаграмму и шаблоны CI/CD.

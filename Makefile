.PHONY: up down build logs ps migrate sync-alstyle help

## ── Docker ────────────────────────────────────────────
up:                    ## Запустить все сервисы
	docker-compose up --build

down:                  ## Остановить все сервисы
	docker-compose down -v

build:                 ## Только пересобрать образы
	docker-compose build

logs:                  ## Логи backend
	docker-compose logs -f backend

ps:                    ## Статус контейнеров
	docker-compose ps

## ── База данных ───────────────────────────────────────
migrate:               ## Применить миграции alembic
	docker-compose exec backend alembic upgrade head

migrate-create:        ## Создать новую миграцию (make migrate-create MSG="add table")
	docker-compose exec backend alembic revision --autogenerate -m "$(MSG)"

## ── Синхронизация ─────────────────────────────────────
sync-alstyle:          ## Запустить синхронизацию al-style.kz вручную
	docker-compose exec backend python -m app.services.alstyle_sync

## ── Git ───────────────────────────────────────────────
init-repo:             ## Инициализировать git-репозиторий (требует git)
	powershell -ExecutionPolicy Bypass -File init-git.ps1

## ── Помощь ────────────────────────────────────────────
help:                  ## Показать список команд
	@powershell -Command "Get-Content Makefile | Select-String '##' | ForEach-Object { $$_.Line }"

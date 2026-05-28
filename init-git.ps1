# ============================================================
# init-git.ps1 — Инициализация git-репозитория для dshopWB
# Запускать из корня проекта: .\init-git.ps1
# ============================================================

param(
    [string]$GitHubUser   = "",        # ваш username на GitHub
    [string]$RepoName     = "dshopWB", # название репозитория
    [string]$Branch       = "main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }

# ── Проверка git ──────────────────────────────────────────────
Write-Step "Проверяем git"
try {
    $v = & git --version 2>&1
    Write-OK $v
} catch {
    Write-Host "`n❌ Git не найден. Установи его с https://git-scm.com/download/win`n" -ForegroundColor Red
    exit 1
}

# ── Инициализация ─────────────────────────────────────────────
Write-Step "Инициализация репозитория"
if (Test-Path ".git") {
    Write-Warn "Репозиторий уже инициализирован — пропускаем git init"
} else {
    git init -b $Branch
    Write-OK "git init -b $Branch"
}

# ── Проверка .env ─────────────────────────────────────────────
Write-Step "Проверяем безопасность"
if (Test-Path ".env") {
    # Убеждаемся, что .env НЕ попадёт в индекс
    $tracked = git ls-files .env 2>$null
    if ($tracked) {
        Write-Warn ".env уже трекается! Удаляем из индекса..."
        git rm --cached .env
    }
    Write-OK ".env не будет закоммичен"
} else {
    Write-Warn ".env не найден — создай его из .env.example"
}

# ── Git config (если не задан) ────────────────────────────────
Write-Step "Проверяем git config"
$name  = git config --global user.name  2>$null
$email = git config --global user.email 2>$null

if (-not $name) {
    $name = Read-Host "  Введи имя для git config (например: Ivan Ivanov)"
    git config --global user.name $name
}
if (-not $email) {
    $email = Read-Host "  Введи email для git config"
    git config --global user.email $email
}
Write-OK "Автор: $name <$email>"

# ── Первый коммит ─────────────────────────────────────────────
Write-Step "Создаём первый коммит"
git add .

$status = git status --short
if (-not $status) {
    Write-Warn "Нечего коммитить — репозиторий уже актуален"
} else {
    git commit -m "feat: initial project setup — dshopWB (al-style.kz → WB integration)"
    Write-OK "Коммит создан"
}

# ── Подключение к GitHub ──────────────────────────────────────
Write-Step "Подключение к GitHub"

if (-not $GitHubUser) {
    $GitHubUser = Read-Host "  Введи твой GitHub username (или Enter чтобы пропустить)"
}

if ($GitHubUser) {
    $remoteUrl = "https://github.com/$GitHubUser/$RepoName.git"
    $existing  = git remote get-url origin 2>$null

    if ($existing) {
        Write-Warn "Remote origin уже настроен: $existing"
    } else {
        git remote add origin $remoteUrl
        Write-OK "Remote: $remoteUrl"
    }

    Write-Host @"

─────────────────────────────────────────────────
  Следующие шаги:

  1. Создай репозиторий на GitHub:
     https://github.com/new
     Название: $RepoName   (НЕ инициализируй README/gitignore там)

  2. Отправь код:
     git push -u origin $Branch

─────────────────────────────────────────────────
"@ -ForegroundColor Cyan
} else {
    Write-Host @"

─────────────────────────────────────────────────
  Репозиторий готов локально.
  Чтобы загрузить на GitHub:

  1. Создай репозиторий: https://github.com/new
  2. Выполни:
     git remote add origin https://github.com/<username>/$RepoName.git
     git push -u origin $Branch
─────────────────────────────────────────────────
"@ -ForegroundColor Cyan
}

Write-Host "`n✅ Готово!`n" -ForegroundColor Green

# Freelance Radar AI

Автономный Python-агент: ищет цифровые фриланс-заказы, оценивает их через ИИ и (где разрешено) отправляет первое сообщение автору. Управление — через Telegram-бота владельца.

## Что реализовано (MVP)

| Компонент | Статус |
|-----------|--------|
| SQLite + SQLAlchemy 2 модели, Alembic | ✅ |
| Конвейер: сбор → нормализация → дедуп → префильтр → LLM → рейтинг → уведомления | ✅ |
| Источник `fixture` (локальный JSON) | ✅ полный цикл |
| Источник `rss` (публичные RSS/Atom) | ✅ при наличии URL |
| Источник `telegram` (Telethon user session) | ✅ при API ID/HASH + сессии + каналах |
| Kwork / FL.ru / Freelance.ru | ⚠️ только probe: без обхода защиты, без фейковых заказов |
| ИИ: OpenAI-compatible + MockLLM | ✅ |
| Автоконтакт (mock / Telegram DM) с лимитами, FloodWait, без ложных «успехов» | ✅ |
| Telegram control bot (aiogram 3), только OWNER_TELEGRAM_ID | ✅ |
| Docker Compose, pytest | ✅ |

## Быстрый старт (локально)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# минимум для офлайн-демо:
# LLM_USE_MOCK=true
# SOURCE_FIXTURE_ENABLED=true
# OUTREACH_ENABLED=false
# OUTREACH_DRY_RUN=true

mkdir -p data
alembic upgrade head   # или таблицы создадутся при старте
python -m freelance_radar.main
# либо один прогон без бота:
python scripts/run_pipeline_once.py
```

Тесты:

```bash
pytest -q
```

## Docker / VPS

```bash
cp .env.example .env
# заполните TELEGRAM_BOT_TOKEN, OWNER_TELEGRAM_ID и при необходимости LLM_*
docker compose up -d --build
```

Данные и сессии монтируются в `./data`. Для PostgreSQL раскомментируйте сервис `db` в `docker-compose.yml` и смените `DATABASE_URL`.

## Telegram: control-бот

1. Создайте бота у [@BotFather](https://t.me/BotFather), получите токен → `TELEGRAM_BOT_TOKEN`.
2. Узнайте свой ID (например `@userinfobot`) → `OWNER_TELEGRAM_ID`.
3. Запустите приложение; бот принимает команды только от владельца:

`/start` `/orders` `/outreach` `/sources` `/settings` `/stats` `/pause` `/resume` `/stop_outreach` `/start_outreach`

## Telegram: чтение каналов (Telethon)

Бот **не** может читать чужие чаты. Нужна пользовательская сессия:

1. Получите `api_id` / `api_hash` на https://my.telegram.org  
2. Пропишите `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SOURCE_CHANNELS`  
3. Один раз интерактивно: `python scripts/telethon_login.py`  
4. `SOURCE_TELEGRAM_ENABLED=true`  

Авто-DM включается только при `OUTREACH_ENABLED=true` и `OUTREACH_DRY_RUN=false`. При FloodWait/429 отправка останавливается; успех сообщается **только** после подтверждённого message id.

## ИИ-провайдер

Любой OpenAI-compatible endpoint:

```env
LLM_USE_MOCK=false
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

Без ключа автоматически используется `MockLLM` (правила + эвристики).

## Источники: фактические возможности

| Ключ | Чтение | Автоконтакт | Примечание |
|------|--------|-------------|------------|
| fixture | да | нет | демо/тесты |
| rss | да (публичные URL) | нет → `manual_contact_required` | не обходит login/CAPTCHA |
| telegram | да (свои каналы) | да (DM, с лимитами) | нужна user-сессия |
| kwork | нет | нет | нет публичного API заказов |
| flru / freelance_ru | нет | нет | stubs + альтернативы (RSS/TG) |

Если площадка недоступна для легальной автоматизации, адаптер **не имитирует** ленту заказов — пишет причину и альтернативы (`/sources`).

## Безопасность

- Секреты только в `.env` / переменных окружения  
- Логи редактируют token/password/api_key  
- Сессии Telethon в `data/`, в git не коммитятся  
- Массовый спам и обход антибота запрещены архитектурой  

## Ограничения и следующие шаги

1. Подключать новые источники **по одному** после проверки ToS/API.  
2. Официальные API Kwork/FL при появлении доступа — заменить stubs.  
3. Трекинг ответов заказчиков в Telegram (read replies) без автопереговоров.  
4. PostgreSQL + бэкапы для прод.  
5. Расширить семантический дедуп (эмбеддинги) при росте объёма.  

Подробнее: `docs/ARCHITECTURE.md`, `docs/SOURCES.md`, `docs/DEPLOY.md`.

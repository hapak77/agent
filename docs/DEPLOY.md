# Развёртывание

## Локально

См. корневой `README.md`.

## VPS (кратко)

1. Установите Docker + Compose.  
2. Скопируйте репозиторий, создайте `.env` из `.env.example`.  
3. Выставьте `TELEGRAM_BOT_TOKEN`, `OWNER_TELEGRAM_ID`, LLM-ключи.  
4. Для Telegram-источника создайте сессию на машине с TTY (`scripts/telethon_login.py`), положите файл в `data/`.  
5. `docker compose up -d --build`.  
6. Проверьте `/stats` и `/sources` в боте.  

## Переменные критичные для продакшена

- `OUTREACH_DRY_RUN=false` только после ручной проверки шаблона и лимитов  
- `OUTREACH_ENABLED=true` осознанно  
- `OUTREACH_MAX_PER_HOUR` / `OUTREACH_MAX_PER_DAY`  
- `LLM_USE_MOCK=false` + валидный ключ  

## Миграции

```bash
alembic upgrade head
```

При первом запуске `init_db()` также создаёт таблицы (`create_all`) — удобно для SQLite MVP.

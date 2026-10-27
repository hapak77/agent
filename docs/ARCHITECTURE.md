# Архитектура Freelance Radar AI

## Поток данных

```
Sources (adapters)
    → ingest (normalize, hash, exact/semantic dedupe)
    → prefilter (cheap rules)
    → LLM analyze (structured JSON via Pydantic)
    → priority score
    → DB (orders, analysis, contacts)
    → Outreach (rate-limited first message) OR manual_contact_required
    → Owner notifications (Telegram bot)
```

## Пакеты

- `db` — модели SQLAlchemy 2, сессии, репозитории  
- `sources` — адаптеры с `probe()` + `collect()`  
- `pipeline` — ingest / analyze / score / runner  
- `llm` — единый интерфейс + mock + OpenAI-compatible  
- `outreach` — решения, лимиты, адаптеры каналов  
- `bot` — aiogram 3 control plane  
- `scheduler` — APScheduler interval jobs  

## Принципы

1. Не обходить CAPTCHA/auth/антибот.  
2. Не заявлять об успешной отправке без `confirmed=True`.  
3. Бюджет неизвестен → `budget_unknown=true`, значение не выдумывать.  
4. Источники независимы; сбой одного не останавливает остальные.  
5. Состояние `pipeline_paused` / `outreach_stopped` переживает рестарт (таблица `app_state`).

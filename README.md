# parser_avito_3

Python-парсер с обходом антибот-защит (Cloudflare) на базе curl-cffi и Playwright.

## Установка

1) Установите зависимости:

```bash
pip install -r requirements.txt
```

2) Установите браузер для Playwright (однократно):

```bash
playwright install chromium
```

## Конфигурация (.env)

Создайте файл `.env` в корне проекта и задайте переменные:

```bash
TARGET_URL=https://example.com
# Необязательно:
BASE_URL=https://example.com
USE_PLAYWRIGHT=0   # 1/true/yes для включения Playwright
```

Список `User-Agent` хранится в `config/user_agent_pc.txt`. Куки сохраняются в `config/cookie.json`.

## Запуск

```bash
python -m src.main
```

Скрипт прочитает `TARGET_URL` из `.env`, выполнит запрос (curl-cffi или Playwright) и выведет результат (текст страницы) в консоль. В дальнейшем вывод может перенаправляться в другой модуль через `OutputDispatcher`.

## Структура проекта

- `config/` — `.env`, `user_agent_pc.txt`, `cookie.json`
- `core/` — ядро парсера (`parser.py`)
- `database/` — база/миграции (плейсхолдер)
- `logs/` — логи
- `services/` — вспомогательные сервисы (`curl_fetcher.py`, `playwright_fetcher.py`, `output_dispatcher.py`)
- `src/` — точка входа (`main.py`)
- `tests/` — тесты
- `utils/` — утилиты (`headers.py`)

## Примечания по антиботу

- curl-cffi использует impersonation (Chrome) и HTTP/2.
- Playwright запускается с твиками (stealth-like) и сохраняет `storage_state` в `config/cookie.json`.
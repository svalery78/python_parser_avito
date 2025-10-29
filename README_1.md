# parser_avito_3

Python-парсер с обходом антибот-защит (Cloudflare) на базе curl-cffi и Playwright.

## Запуск проекта

### Шаг 1: Установка зависимостей

1. Установите Python-библиотеки:
```bash
pip install -r requirements.txt
```

2. Установите браузер для Playwright (требуется выполнить один раз):
```bash
playwright install chromium
```

### Шаг 2: Конфигурация

Создайте файл `.env` в корневой директории проекта. Этот файл будет содержать переменные окружения.

**Пример содержимого `.env`:**
```
# Обязательная переменная: URL для парсинга
TARGET_URL="https://www.avito.ru/moskva/kvartiry/sdam/na_dlitelnyy_srok-ASgBAgICAkSSA8gQ8AeQUg"

# Требуется только для запуска Telegram-бота
TELEGRAM_BOT_TOKEN="12345:your_bot_token_here"

# Необязательная переменная: 1 для принудительного использования Playwright
USE_PLAYWRIGHT=0
```

### Шаг 3: Варианты запуска

#### Способ 1: Запуск Telegram-бота (Рекомендуемый)

Этот способ запускает пользовательский интерфейс, через который вы можете управлять парсером.

1.  Убедитесь, что в файле `.env` указаны и `TARGET_URL`, и `TELEGRAM_BOT_TOKEN`.
2.  Запустите бота командой:
    ```bash
    python -m telegramBot.bot
    ```
3.  Найдите вашего бота в Telegram, отправьте ему команду `/start` и используйте кнопки для взаимодействия.

---

#### Способ 2: Прямой запуск скрипта парсера

Этот способ выполняет парсинг один раз и выводит результат в консоль и базу данных. Полезен для быстрой проверки или отладки.

1.  Убедитесь, что в файле `.env` указан `TARGET_URL`.
2.  Запустите главный скрипт:
    ```bash
    python -m src.main
    ```

---

#### Способ 3: Запуск с помощью Docker

Этот способ использует Docker для запуска приложения в изолированном контейнере. Требует установленного Docker и Docker Compose.

1.  Создайте файл `.env` как описано в Шаге 2.

2.  **Для запуска парсера один раз** (аналогично Способу 2):
    ```bash
    docker-compose up --build
    ```
    Контейнер запустится, выполнит парсинг и остановится.

3.  **Для запуска Telegram-бота** (аналогично Способу 1):
    Поскольку `docker-compose.yml` по умолчанию запускает парсер, для старта бота нужно переопределить команду:
    ```bash
    docker-compose run --rm --build parser python -m telegramBot.bot
    ```

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

- `curl-cffi` использует impersonation (Chrome) и HTTP/2.
- `Playwright` запускается с твиками (stealth-like) и сохраняет `storage_state` в `config/cookie.json`.

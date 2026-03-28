# Технический дизайн: BankBot с Bridge-модулем

## 1. Обзор архитектуры

BankBot — единый процесс на базе **aiogram** (asyncio event loop), в который встроен Bridge-модуль. VK Long Poll работает в отдельном потоке (`threading.Thread`), взаимодействуя с aiogram через `asyncio.run_coroutine_threadsafe`. Единая база данных (SQLite / PostgreSQL) хранит как банковские данные, так и состояние Bridge. Единый модуль конфигурации на базе Pydantic Settings управляет всеми параметрами.

```
┌─────────────────────────────────────────────────────────┐
│                    Процесс BankBot                       │
│                                                          │
│  ┌──────────────────────┐   ┌────────────────────────┐  │
│  │   aiogram event loop  │   │  VK Long Poll Thread   │  │
│  │                       │   │  (threading.Thread)    │  │
│  │  Handlers / Routers   │◄──┤  vk_listener.py        │  │
│  │  Bridge Handlers      │   │  → run_coroutine_       │  │
│  │  Middleware           │   │    threadsafe()         │  │
│  └──────────┬────────────┘   └────────────────────────┘  │
│             │                                             │
│  ┌──────────▼────────────────────────────────────────┐   │
│  │              Единая БД (SQLite / PostgreSQL)       │   │
│  │   users | balances | transactions | bridge_state  │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Структура модулей

```
BankBot/
├── bot/
│   ├── main.py                    # точка входа: запуск aiogram + VK thread
│   ├── bot.py                     # инициализация Bot и Dispatcher
│   ├── router.py                  # регистрация всех роутеров
│   ├── commands/                  # существующие команды BankBot
│   │   ├── balance.py
│   │   ├── admin.py
│   │   └── shop.py
│   └── bridge/                    # Bridge-модуль
│       ├── __init__.py
│       ├── config.py              # Bridge-параметры из Pydantic Settings
│       ├── telegram_forwarder.py  # aiogram handler: TG → VK
│       ├── vk_listener.py         # Long Poll VK → TG (отдельный поток)
│       ├── vk_sender.py           # отправка сообщений в VK через vk_api
│       ├── media_handler.py       # скачивание и загрузка медиафайлов
│       ├── loop_guard.py          # фильтрация циклов пересылки
│       └── message_queue.py       # очередь исходящих сообщений + воркер
├── core/
│   ├── services/                  # Service Layer (бизнес-логика)
│   ├── repositories/              # Repository Layer (доступ к БД)
│   ├── middleware.py              # централизованная обработка ошибок
│   └── di.py                      # DI-контейнер
├── database/
│   ├── models.py                  # ORM-модели (SQLAlchemy)
│   ├── migrations/                # Alembic миграции
│   └── connection.py              # Connection Pool
├── config/
│   └── settings.py                # Pydantic Settings (единая конфигурация)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

---

## 3. Поток данных

### Направление TG → VK

```
Telegram message
      │
      ▼
aiogram Handler (telegram_forwarder.py)
      │
      ▼
loop_guard.check(message)  ──► [BOT] метка? → отклонить
      │ нет метки
      ▼
message_queue.put(OutboundMessage(platform=VK, ...))
      │
      ▼
Worker Thread (message_queue.py)
      │  задержка 0.5–1 сек
      ▼
vk_sender.send(text="[TG] Имя: текст", peer_id=VK_PEER_ID)
```

### Направление VK → TG

```
VK Long Poll event (vk_listener.py, отдельный поток)
      │
      ▼
loop_guard.check(event)  ──► [BOT] метка? → отклонить
      │ нет метки
      ▼
asyncio.run_coroutine_threadsafe(
    bot.send_message(chat_id=TG_CHAT_ID, text="[VK] Имя: текст"),
    loop
)
```

---

## 4. Модель данных

### Таблица `bridge_state`

```sql
CREATE TABLE bridge_state (
    id               INTEGER PRIMARY KEY DEFAULT 1,
    last_tg_msg_id   INTEGER NOT NULL DEFAULT 0,
    last_vk_msg_id   INTEGER NOT NULL DEFAULT 0,
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Таблица содержит ровно одну строку (id=1). Обновляется после каждой успешной пересылки.

### Существующие таблицы BankBot (без изменений)

- `users` — пользователи, алиасы
- `balances` — текущие балансы
- `transactions` — история операций
- `parser_registry` — конфигурации парсеров

---

## 5. Конфигурация

Все параметры — через Pydantic Settings (`config/settings.py`):

```python
class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    APP_ENV: Literal["dev", "prod", "test"] = "dev"

    # Bridge
    BRIDGE_ENABLED: bool = False
    BRIDGE_TG_CHAT_ID: int = 0
    VK_TOKEN: str = ""
    VK_PEER_ID: int = 0
    BRIDGE_ADMIN_CHAT_ID: int | None = None  # опционально

    # Database
    DATABASE_URL: str = "sqlite:///bankbot.db"
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Admin
    ADMIN_CHAT_ID: int | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

Валидация при старте: если `BRIDGE_ENABLED=true` и `VK_TOKEN` пуст — `ValidationError` с описанием.

---

## 6. Управление потоками

### Запуск

```python
# bot/main.py
async def main():
    settings = get_settings()
    bot, dp = create_bot(settings)

    vk_thread = None
    if settings.BRIDGE_ENABLED:
        vk_thread = VKListenerThread(bot=bot, loop=asyncio.get_event_loop(), settings=settings)
        vk_thread.daemon = True
        vk_thread.start()

    try:
        await dp.start_polling(bot)
    finally:
        if vk_thread:
            vk_thread.stop()
            vk_thread.join(timeout=5)
```

### Graceful Shutdown

`VKListenerThread` содержит флаг `_stop_event = threading.Event()`. При вызове `stop()` флаг устанавливается, Long Poll прерывается на следующей итерации. `join(timeout=5)` гарантирует завершение потока до выхода процесса.

---

## 7. Обработка медиафайлов

### TG → VK

| Тип | Скачивание | Загрузка в VK |
|-----|-----------|---------------|
| Фото | `bot.get_file` + `download_file` | `photos.getMessagesUploadServer` → POST → `photos.saveMessagesPhoto` |
| Видео | `bot.get_file` + `download_file` | `video.getUploadServer` → POST → attach как `video{owner_id}_{video_id}` |
| Документ | `bot.get_file` + `download_file` | `docs.getMessagesUploadServer` → POST → `docs.save` |

Временные файлы сохраняются в `tempfile.NamedTemporaryFile` и удаляются после загрузки.

### VK → TG

| Тип | Получение URL | Отправка в TG |
|-----|--------------|---------------|
| Фото | `attachment.photo.sizes[-1].url` | `bot.send_photo(url)` |
| Видео | прямой URL недоступен → отправить ссылку `vk.com/video...` | `bot.send_message(link)` |
| Документ | `attachment.doc.url` | `bot.send_document(url)` |

Повторные попытки: экспоненциальная задержка `1s → 2s → 4s`, максимум 3 попытки.

---

## 8. Rate Limiting и Message Queue

```
┌─────────────────────────────────────────────┐
│              message_queue.py                │
│                                              │
│  queue.Queue(maxsize=0)  ← put() из handlers │
│                                              │
│  Worker Thread:                              │
│    while not stop_event:                     │
│      msg = queue.get(timeout=1)              │
│      try:                                    │
│        send(msg)                             │
│      except RateLimitError as e:             │
│        sleep(e.retry_after)                  │
│        queue.put(msg)  # вернуть в очередь  │
│      except APIError:                        │
│        retry с exponential backoff           │
│      sleep(0.5)  # базовая задержка для VK  │
└─────────────────────────────────────────────┘
```

Воркер запускается как `daemon=True` поток при инициализации Bridge-модуля. При получении ошибки 429 сообщение возвращается в начало очереди, воркер засыпает на `Retry-After` секунд.

---

## 9. Свойства корректности (Correctness Properties)

Используются для Property-Based Testing (pytest + hypothesis).

**Свойство 1 — Однократная пересылка (Loop Guard):**
Для любого текстового сообщения из TG без метки `[BOT]` — оно должно появиться в VK ровно один раз.
```
∀ msg ∈ TG_messages: "[BOT]" ∉ msg.text → count(forwarded_to_vk(msg)) == 1
```

**Свойство 2 — Фильтрация меток:**
Для любого сообщения с меткой `[BOT]` — оно не должно пересылаться ни в одном направлении.
```
∀ msg: "[BOT]" ∈ msg.text → forwarded(msg) == False
```

**Свойство 3 — Атомарность баланса:**
Баланс пользователя после N конкурентных операций должен равняться начальному балансу плюс алгебраическая сумма всех операций.
```
∀ ops: balance_after(ops) == balance_before + sum(op.amount for op in ops)
```

**Свойство 4 — Round-trip парсера:**
Объединённый парсер для любых входных данных, которые парсились до объединения, возвращает эквивалентный результат после цикла parse → format → parse.
```
∀ input ∈ valid_inputs: parse(format(parse(input))) == parse(input)
```

---

## 10. Технологический стек

| Компонент | Библиотека | Версия |
|-----------|-----------|--------|
| Telegram Bot | aiogram | ~=3.x |
| VK API | vk_api | ~=11.x |
| Конфигурация | pydantic-settings | ~=2.x |
| ORM | SQLAlchemy | ~=2.x |
| Миграции | alembic | ~=1.x |
| Тестирование | pytest, pytest-asyncio | latest |
| PBT | hypothesis | latest |
| Покрытие | pytest-cov | latest |
| Линтер | ruff | latest |
| Docstrings | pydocstyle (через ruff) | latest |
| Контейнер | Docker, docker-compose | latest |
| Вебхуки (опц.) | Flask | ~=3.x |
| Прокси (опц.) | Nginx + Let's Encrypt | — |

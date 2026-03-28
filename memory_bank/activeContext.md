# Active Context

## Текущий фокус
**Реструктуризация проекта под целевую архитектуру из AGENTS.md.**

Целевая структура:
```
BankBot/
├── bridge_bot/      # BridgeBot (пересылка постов TG → VK)
├── bank_bot/        # BankBot (банковская система)
├── vk_bot/          # VK Bot (публикация в канал VK)
├── common/          # общие модули (config, database, models, logging)
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

## План миграции (поэтапный)

### Этап 0: Подготовка ✅
- Зафиксировать план в memory_bank
- Убедиться что тесты проходят до начала

### Этап 1: Создать common/ [СЛЕДУЮЩИЙ]
- `common/__init__.py`
- `common/config.py` — перенести из `config/settings.py` (добавить re-export в старом месте)
- `common/database.py` — re-export из `database/database.py`
- `common/models.py` — re-export из `database/database.py` (модели)
- `common/logging.py` — новый модуль логирования
- Старые пути (`config/settings.py`, `database/`) оставить как shim-обёртки

### Этап 2: Создать bridge_bot/ [ПОСЛЕ ЭТАПА 1]
- Переместить `bot/bridge/` → `bridge_bot/`
- `bridge_bot/main.py` ← `bot/bridge/main_bridge.py`
- `bridge_bot/bot.py` ← инициализация
- `bridge_bot/handlers.py` ← `bot/bridge/telegram_forwarder.py`
- `bridge_bot/vk_publisher.py` ← `bot/bridge/vk_sender.py`
- `bridge_bot/media.py` ← `bot/bridge/media_handler.py`
- `bridge_bot/queue.py` ← `bot/bridge/message_queue.py`
- `bridge_bot/config.py` ← `bot/bridge/config.py`
- Обновить все импорты внутри bridge_bot/
- Оставить `bot/bridge/` как shim с re-export

### Этап 3: Создать bank_bot/ [ПОСЛЕ ЭТАПА 2]
- `bank_bot/main.py` ← `bot/main.py`
- `bank_bot/bot.py` ← `bot/bot.py`
- `bank_bot/handlers/` ← `bot/handlers/` + `bot/commands/`
- `bank_bot/services/` ← `core/services/`
- `bank_bot/repositories/` ← `core/repositories/`
- `bank_bot/middleware.py` ← `core/middleware/error_handling.py`
- `bank_bot/di.py` ← `core/di.py`
- Оставить `bot/`, `core/` как shim с re-export

### Этап 4: Создать vk_bot/ [ПОСЛЕ ЭТАПА 3]
- `vk_bot/main.py` — точка входа VK Long Poll
- `vk_bot/bot.py` — инициализация
- `vk_bot/handlers.py` — обработка входящих
- `vk_bot/config.py` — конфигурация

### Этап 5: Обновить run_bot.py и корень [ПОСЛЕ ЭТАПА 4]
- `run_bot.py` → запуск bank_bot
- Убрать лишние файлы из корня (оставить только разрешённые AGENTS.md)

### Этап 6: Финальная проверка
- Запустить тесты
- Проверить ruff
- Обновить docs/README.md

## Принципы безопасной миграции
1. **Shim-файлы**: старые пути остаются рабочими через re-export
2. **Один этап за раз**: после каждого этапа — проверка импортов
3. **Сохранение в memory_bank** после каждого этапа
4. **Тесты не трогать** — они используют старые пути через shim

## Текущий статус этапов
- Этап 0: ✅ Готов
- Этап 1: ✅ common/ создан (config, database, logging, utils) — импорты OK
- Этап 2: ✅ bridge_bot/ создан (config, loop_guard, queue, vk_publisher, media, handlers, main) — импорты OK
- Этап 3: ✅ bank_bot/ создан (repositories, services, di, middleware, handlers, bot, main) — импорты OK
- Этап 4: ✅ vk_bot/ создан (config, bot, handlers, main) — импорты OK
- Этап 5: ✅ run_bot.py и корень проверены — соответствуют AGENTS.md
- Этап 6: ✅ Финальная проверка пройдена (ruff OK, импорты OK)

## Новые точки входа (после миграции)
- `python run_bot.py` → `bot/main.py` — основной бот (python-telegram-bot)
- `python -m bot.bridge.main_bridge` — Bridge-модуль (aiogram)
- `python -m bridge_bot.main` — BridgeBot (новый путь)
- `python -m vk_bot.main` — VK Bot

## Завершённые задачи (предыдущие сессии)
- 1.1–1.3 Инфраструктура и конфигурация
- 2.1, 2.3, 2.5–2.8 Bridge-модуль ядро
- 4.1–4.3 Bridge медиа и надёжность
- 7.1–7.4 Рефакторинг банковской системы: основа
- 8.1–8.4 Рефакторинг банковской системы: безопасность
- Очистка корня проекта
- Исправление merge-конфликта utils/compat.py
- Удаление stub-файлов bot/commands/admin.py, shop.py
- Документирование legacy-слоёв src/, utils/
- Этапы 4-6: Создание vk_bot/, проверка корня, финальная проверка

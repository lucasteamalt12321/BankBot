# Active Context

## Текущий фокус
Bridge-модуль (ядро) — реализован и прошёл чекпоинт 3. Следующий этап: рефакторинг банковской системы (задачи 7.x, 8.x).

## Завершённые задачи (текущая сессия)
- 1.1 config/settings.py с Pydantic Settings + Bridge-поля + валидация
- 1.2 requirements.txt / requirements-dev.txt — конфликты разрешены, vk_api добавлен
- 1.3 Миграция bridge_state (SQL + Python)
- 2.1 bot/bridge/ структура + loop_guard.py
- 2.3 message_queue.py (FIFO, rate limiting, exponential backoff)
- 2.5 vk_sender.py (отправка в VK с префиксом [TG] и меткой [BOT])
- 2.6 telegram_forwarder.py (aiogram handler TG → VK)
- 2.7 vk_listener.py (VKListenerThread, Long Poll, медиа VK → TG)
- 2.8 bot/bridge/main_bridge.py (точка входа aiogram + graceful shutdown)
- 4.1 media_handler.py (фото/видео/документы TG → VK)
- 4.2 Медиа VK → TG (реализовано в vk_listener.py)

## Чекпоинт 3 — Bridge ядро: ПРОЙДЕН
- loop_guard: импорт OK, логика has_bot_mark/add_bot_mark OK
- message_queue: импорт OK
- config/settings: BRIDGE_ENABLED=false — OK; BRIDGE_ENABLED=true без VK_TOKEN — ValidationError OK
- ruff: только E501 (длина строк), критических ошибок нет

## Активные задачи (следующий этап)
- 7.1 core/repositories/ — слой репозиториев
- 7.2 core/services/ — Service Layer
- 7.3 core/di.py — DI-контейнер
- 7.4 Разбить bot.py на модули
- 8.1 Unit of Work
- 8.2 Connection Pooling
- 8.3 core/middleware.py
- 8.4 Аудит SQL-запросов

## Точка входа Bridge
`python -m bot.bridge.main_bridge` (aiogram, отдельно от основного bot/main.py)
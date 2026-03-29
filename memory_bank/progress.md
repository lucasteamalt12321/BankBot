# Progress

## Статус проекта
**Процент выполнения:** 95%
**Текущая фаза:** Фаза 4 — Исправление проблем, очистка legacy-кода
**Следующие задачи:**
1. [ ] Исправить merge conflict markers в README.md
2. [ ] Добавить BotApplication в bot/main.py или удалить тесты
3. [ ] Исправить тесты с отсутствующей колонкой alias
4. [ ] Очистить ruff errors в legacy коде (опционально)

## Known Issues

### Критические проблемы
- **Merge conflicts**: Конфликты слияния в README.md, test_task_9_verification.py, test_auto_registration_pbt.py
- **test_shutdown_resource_cleanup**: Импорт `BotApplication` из `bot.main` не найден (18 тестов падают)
- **test_user_manager**: Таблица `users` не содержит колонку `alias` в in-memory тестах (3 теста падают)

### Высокий приоритет
- Исправить merge conflict markers в README.md (строки 260-307)
- Исправить или удалить тесты с устаревшими импортами

### Средний приоритет
- ruff: 354 ошибки остаются (в legacy коде bot/, core/, utils/, tests/)
- Тесты покрытия: 706 passed, 89 failed

### Решённые проблемы
- ✅ Connection pooling подключен
- ✅ SQL injection аудит пройден
- ✅ E2E тесты написаны
- ✅ Система алиасов реализована
- ✅ SimpleShmalalaParser deprecated

## Changelog

### 2026-03-29 (ревизия проекта)
- **Ruff**: 370 автоисправлено, 354 осталось (в legacy коде)
- **Тесты**: 706 passed, 89 failed
  - Провалы: импорт BotApplication, отсутствие колонки alias, merge conflicts
- **Merge conflicts**: найдены в README.md, test_task_9_verification.py, test_auto_registration_pbt.py
- **Core service tests**: 53 passed (shop, transaction, user services)
- **Docker**: Dockerfile и docker-compose.yml базовые, работающие

### 2026-03-28 (продолжение)
- **Этапы 4-6 завершены**: vk_bot/ создан, корень проверен, финальная проверка пройдена
  - `vk_bot/config.py`, `bot.py`, `handlers.py`, `main.py` — импорты OK
  - ruff check: предупреждения только в legacy-коде (bot/bot.py)
  - Все модули (bank_bot, bridge_bot, vk_bot) импортируются корректно

### 2026-03-28 (доп.)
- **D12 (Connection Pooling)**: Подключен `get_pooled_engine()` в `database/database.py`
- **D13 (SQL Injection Audit)**: Аудит завершён — параметризация используется везде
- **D16 (Очистка неиспользуемого кода)**: Исправлены unused imports в bot/bot.py (6 шт)
- **TransactionService fix**: Добавлен `session` параметр для тестов, исправлены методы для использования `get(id)` вместо `get_by_telegram_id`
- **UserRepository fix**: Добавлен метод `get_all()` в `core/repositories/user_repository.py`
- **Unit tests**: 713 passed, прогресс в стабильности
- **D19 (Security tests)**: Созданы тесты SQL injection и race conditions
- **D20 (Coverage)**: TransactionService 96%, ShopService 95%, UserService 94%, AliasService 91%
- **D21 (Documentation)**: Обновлена архитектура README.md, добавлены точки входа
- **D22 (Docstrings)**: Google style docstrings добавлены во все ключевые модули:
  - core/repositories/ (BaseRepository, BalanceRepository, TransactionRepository, UnitOfWork)
  - core/services/ (BalanceService, TransactionService)
  - bridge_bot/, vk_bot/, bank_bot/ (re-exports + entry points)

### 2026-03-29 (реструктуризация)
- bridge_bot/ получил реальный код (queue, loop_guard, media, vk_publisher, handlers)
- bot/bridge/ стал shim-обёртками на bridge_bot/
- bank_bot/repositories/ получил реальный код из core/repositories/
- bank_bot/services/ получил реальный код из core/services/
- core/repositories/ стал shim-обёртками на bank_bot/repositories/
- core/services/__init__.py стал shim на bank_bot/services/
- Dockerfile и docker-compose.yml созданы
- ruff: 0 ошибок в целевых модулях
- Тесты: 991 passed, 168 failed (все провалы pre-existing)
  - SimpleShmalalaParser отмечен как deprecated
  - Рекомендуется использовать BaseParser из core/parsers/shmalala.py, gdcards.py

### 2026-03-28
- Реализован Bridge-модуль (ядро + медиа):
  - `config/settings.py` — BotSettings с Bridge-полями и валидацией
  - `requirements.txt` / `requirements-dev.txt` — конфликты разрешены, добавлен `vk_api~=11.9`
  - `database/migrations/004_add_bridge_state.sql` + `add_bridge_state.py`
  - `bot/bridge/__init__.py`, `config.py`, `loop_guard.py`
  - `bot/bridge/message_queue.py` — FIFO очередь с rate limiting
  - `bot/bridge/vk_sender.py` — отправка в VK с префиксом [TG] и меткой [BOT]
  - `bot/bridge/telegram_forwarder.py` — aiogram handler TG → VK
  - `bot/bridge/vk_listener.py` — VKListenerThread, Long Poll, медиа VK → TG
  - `bot/bridge/media_handler.py` — загрузка фото/видео/документов TG → VK
  - `bot/bridge/main_bridge.py` — точка входа aiogram + graceful shutdown
- Чекпоинт 3 (Bridge ядро) пройден: импорты OK, логика loop_guard OK, валидация конфига OK

### 2026-03-27
- Обновлена документация в memory_bank
- Исправлен конфликт импортов в src/balance_manager.py
- Выявлены проблемы с типизацией в ParsingConfigManager

### Предыдущие изменения
- Реализован ParserRegistry для централизованного парсинга
- Создан ParsingConfigManager для управления правилами в БД
- Добавлена таблица parsing_rules в БД
- Реализован BalanceManager для обработки балансов
- Добавлен Unit of Work для атомарных транзакций

## last_checked_commit
2026-03-29
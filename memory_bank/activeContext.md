# Active Context

## Текущий фокус

Фаза 3 — Безопасность и качество. Исправлены merge конфликты, создан Unit of Work. Следующий приоритет: DI контейнер (D15), аудит SQL injection (D13), система алиасов (D14).

## Что сделано (эта сессия — 2026-03-24)

- [x] Исправлены merge конфликты в `src/repository/base.py`
- [x] Исправлены merge конфликты в `src/repository/user_repository.py`
- [x] Исправлен merge конфликт в `src/config.py`
- [x] Исправлен merge конфликт в `src/repository/__init__.py`
- [x] Создан `src/repository/unit_of_work.py` (Unit of Work pattern)
- [x] Добавлен `C:\Users\admin\.bun\bin` в PATH пользователя
- [x] Обновлён AGENTS.md из актуального источника

## Ранее завершено

- [x] Централизованная конфигурация (src/config.py, Pydantic Settings)
- [x] Вынос конфиденциальных данных в переменные окружения
- [x] Разделение requirements на prod/dev/docs
- [x] Исправление импортов (scripts/fix_imports.py)
- [x] Слой репозиториев (src/repository/)
- [x] Middleware для обработки ошибок (bot/middleware/error_handler.py)
- [x] Конфигурация парсинга в БД (ParsingConfigManager)
- [x] StartupValidator (src/startup_validator.py)
- [x] Graceful shutdown (src/process_manager.py)
- [x] Рефакторинг bot.py → bot/commands/
- [x] Service layer (user_service, transaction_service, shop_service)
- [x] ParserRegistry (core/parsers/registry.py)

## В работе

- [ ] DI контейнер зависимостей (D15) — задача 11.3
- [ ] Unit of Work — интеграция в TransactionService (D11)
- [ ] Аудит SQL injection (D13) — задача 15.1
- [ ] Система алиасов (D14) — задача 16.1

## Следующие задачи (по приоритету)

1. DI контейнер — создать `src/container.py` с wire-up сервисов
2. Интегрировать UnitOfWork в TransactionService
3. Аудит SQL injection в handlers и старых модулях
4. Система алиасов пользователей

## Активные файлы

- `AGENTS.md` — правила и план разработки
- `memory_bank/` — Memory Bank проекта
- `src/repository/unit_of_work.py` — новый UoW
- `src/repository/base.py` — исправлен (merge конфликты)
- `src/repository/user_repository.py` — исправлен (merge конфликты)
- `src/config.py` — исправлен (merge конфликт в validator)

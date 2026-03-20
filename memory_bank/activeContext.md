# Active Context

## Текущий фокус

Инициализация Memory Bank. Фазы 1-2 плана разработки в основном завершены, идёт работа над Фазой 2-3.

## Что сделано

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

## В работе

- [ ] DI контейнер зависимостей (D15)
- [ ] ParserRegistry (D10)
- [ ] Обновление тестов с моками для service layer (D06)

## Следующие задачи (по приоритету)

1. Завершить service layer — вынести оставшуюся бизнес-логику из handlers (D06)
2. Завершить ParserRegistry (D10)
3. Блокировки балансов + Unit of Work (D11)
4. Аудит SQL injection (D13)
5. Система алиасов пользователей (D14)

## Активные файлы

- `AGENTS.md` — правила и план разработки
- `memory_bank/` — Memory Bank проекта
- `.kiro/specs/project-critical-fixes/tasks.md` — детальный чеклист
- `src/config.py` — централизованная конфигурация
- `bot/commands/` — команды бота после рефакторинга
- `core/services/` — service layer

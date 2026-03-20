# Active Context

## Текущий фокус

Выполняется рефакторинг по плану из AGENTS.md. Фазы 1-2 в основном завершены, идёт работа над Фазой 2-3.

## Что уже сделано (из tasks.md)

- [x] Централизованная конфигурация (src/config.py, Pydantic Settings)
- [x] Вынос конфиденциальных данных в переменные окружения
- [x] Разделение requirements на prod/dev/docs
- [x] Исправление импортов в тестах
- [x] Слой репозиториев (src/repository/)
- [x] Middleware для обработки ошибок (bot/middleware/error_handler.py)
- [x] Конфигурация парсинга в БД (ParsingConfigManager)
- [x] StartupValidator
- [x] Graceful shutdown (ProcessManager)
- [x] Рефакторинг bot.py → bot/commands/
- [x] Service layer (user_service, transaction_service, shop_service)

## В работе

- [ ] DI контейнер зависимостей (11.3)
- [ ] ParserRegistry (12.1)
- [ ] Обновление тестов с моками (11.4)

## Следующие задачи

- Фаза 3: race conditions, SQL injection аудит, алиасы пользователей
- Фаза 4: очистка неиспользуемого кода (D&D, кланы, таблицы БД)
- Фаза 5: E2E тесты, документация

## Активные файлы

- `AGENTS.md` — план разработки (правило для ИИ)
- `.kiro/specs/project-critical-fixes/tasks.md` — детальный чеклист задач
- `src/config.py` — централизованная конфигурация
- `bot/commands/` — команды бота после рефакторинга
- `core/services/` — service layer

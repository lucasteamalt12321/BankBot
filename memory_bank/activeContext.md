# Active Context

## Текущий фокус

Синхронизация Memory Bank с актуальным AGENTS.md. Фазы 1-2 плана разработки завершены на 40%, идёт работа над Фазой 2-3.

## Что сделано (2026-03-24)

- [x] Синхронизирован Memory Bank с актуальным AGENTS.md из репозитория
- [x] Исправлены веса в Project Deliverables (сумма = 100)
- [x] Обновлён формат таблицы deliverables (английские заголовки)
- [x] Пересчитан процент выполнения проекта: 40%
- [x] Обновлён last_checked_commit в progress.md

## Завершённые deliverables (40%)

- [x] D01: Централизованная конфигурация (src/config.py, Pydantic Settings)
- [x] D02: Вынос конфиденциальных данных в переменные окружения
- [x] D03: Разделение requirements на prod/dev/docs
- [x] D04: Исправление импортов (scripts/fix_imports.py)
- [x] D05: Слой репозиториев (src/repository/)
- [x] D07: Рефакторинг bot.py → bot/commands/
- [x] D08: Middleware для обработки ошибок (bot/middleware/error_handler.py)
- [x] D09: Graceful shutdown (src/process_manager.py)

## В работе

- [ ] D06: Service layer — вынести оставшуюся бизнес-логику из handlers
- [ ] D10: ParserRegistry + конфигурация парсинга в БД

## Следующие задачи (по приоритету)

1. Завершить service layer (D06)
2. Завершить ParserRegistry (D10)
3. Блокировки балансов + Unit of Work (D11)
4. Аудит SQL injection (D13)
5. Система алиасов пользователей (D14)
6. DI контейнер зависимостей (D15)

## Активные файлы

- `AGENTS.md` — правила и план разработки
- `memory_bank/` — Memory Bank проекта
- `memory_bank/projectbrief.md` — канонический источник процента выполнения
- `src/config.py` — централизованная конфигурация
- `bot/commands/` — команды бота после рефакторинга
- `core/services/` — service layer
- `src/repository/` — слой репозиториев

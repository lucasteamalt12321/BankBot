# Progress

## Статус по deliverables

| ID | Название | Статус |
|----|----------|--------|
| D01 | Централизованная конфигурация (Pydantic Settings) | completed |
| D02 | Вынос конфиденциальных данных в env | completed |
| D03 | Разделение зависимостей (requirements) | completed |
| D04 | Исправление импортов | completed |
| D05 | Слой репозиториев (Repository pattern) | completed |
| D06 | Service layer (бизнес-логика из handlers) | in_progress |
| D07 | Рефакторинг bot.py на модули | completed |
| D08 | Middleware обработки ошибок | completed |
| D09 | Graceful shutdown | completed |
| D10 | ParserRegistry + конфигурация парсинга в БД | in_progress |
| D11 | Блокировки балансов + Unit of Work | in_progress |
| D12 | Connection pooling | pending |
| D13 | Аудит SQL injection | pending |
| D14 | Система алиасов пользователей | pending |
| D15 | DI контейнер зависимостей | pending |
| D16 | Аудит и очистка неиспользуемого кода | pending |
| D17 | Объединение дублирующихся парсеров | pending |
| D18 | E2E тесты основных сценариев | pending |
| D19 | Тесты безопасности | pending |
| D20 | Coverage 80%+ | pending |
| D21 | Документация (README, DEPLOYMENT.md, диаграммы) | pending |
| D22 | Docstrings Google style | pending |

**Процент выполнения: 40%**
(completed: D01-D05, D07-D09 = 40/100)

## Known Issues

- Часть handlers содержит бизнес-логику (не вынесена в services)
- DI не настроен — зависимости создаются вручную
- Дублирующиеся парсеры не объединены
- Unit of Work не реализован — транзакции не атомарны
- Временные тестовые БД создаются в корне проекта (мусор)
- `docs/memory-bank/` — устаревший Memory Bank, заменён на `memory_bank/`

## Changelog

### 2026-03-24
- Синхронизация Memory Bank с актуальным AGENTS.md
- Исправлены веса в Project Deliverables (сумма теперь ровно 100)
- Обновлён формат таблицы deliverables (Status вместо Статус, Deliverable вместо Название)
- Пересчитан процент выполнения: 40%

### 2026-03-24
- Исправлены merge конфликты в `src/repository/base.py` и `src/repository/user_repository.py`
- Исправлен merge конфликт в `src/config.py` (validator ADMIN_TELEGRAM_ID)
- Исправлен merge конфликт в `src/repository/__init__.py`
- Создан `src/repository/unit_of_work.py` — Unit of Work pattern (D11 → in_progress)
- Обновлён AGENTS.md из актуального источника (github.com/Ravva/projects-tracker)
- Добавлен `C:\Users\admin\.bun\bin` в PATH пользователя

### 2026-03-20
- Инициализирован Memory Bank (`memory_bank/`)
- Созданы все 6 обязательных файлов: projectbrief, productContext, activeContext, systemPatterns, techContext, progress
- Обновлён AGENTS.md — добавлена полная инструкция Memory Bank
- Восстановлен git HEAD на ветку main после detached HEAD

## Контроль изменений

```
last_checked_commit: 410cd446ca726bc26becf372e81fe71509d9ec55
```

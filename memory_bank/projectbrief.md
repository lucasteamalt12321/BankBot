# Project Brief — BankBot (LucasTeam)

## Цели проекта

Telegram-бот-агрегатор для автоматического отслеживания игровой активности и начисления банковских монет. Объединяет несколько игровых платформ в единую экосистему с общей валютой (банковские монеты).

## Рамки проекта

- Поддержка 4 игровых платформ: GD Cards, Shmalala, True Mafia, Bunker RP
- Единый баланс и магазин для всех игр
- Система достижений, социальные функции, мини-игры
- Административная панель с рассылками
- Автоматический и ручной парсинг игровых сообщений

## Репозиторий

https://github.com/lucasteamalt12321/BankBot

## Точка входа

`run_bot.py` → `bot/main.py`

---

## Project Deliverables

| ID | Deliverable | Status | Weight |
|----|-------------|--------|--------|
| D01 | Централизованная конфигурация (Pydantic Settings) | completed | 7 |
| D02 | Вынос конфиденциальных данных в env | completed | 5 |
| D03 | Разделение зависимостей (requirements) | completed | 4 |
| D04 | Исправление импортов | completed | 3 |
| D05 | Слой репозиториев (Repository pattern) | completed | 7 |
| D06 | Service layer (бизнес-логика из handlers) | completed | 7 |
| D07 | Рефакторинг bot.py на модули | completed | 5 |
| D08 | Middleware обработки ошибок | completed | 5 |
| D09 | Graceful shutdown | completed | 4 |
| D10 | ParserRegistry + конфигурация парсинга в БД | completed | 5 |
| D11 | Блокировки балансов + Unit of Work | completed | 6 |
| D12 | Connection pooling | completed | 3 |
| D13 | Аудит SQL injection | completed | 5 |
| D16 | Аудит и очистка неиспользуемого кода | completed | 4 |
| D17 | Объединение дублирующихся парсеров | completed | 3 |
| D18 | E2E тесты основных сценариев | completed | 4 |
| D19 | Тесты безопасности (SQL injection, race conditions) | completed | 4 |
| D20 | Coverage 80%+ | completed | 4 |
| D21 | Документация (README, DEPLOYMENT.md, диаграммы) | completed | 3 |
| D22 | Docstrings Google style | completed | 2 |
| D23 | Bridge-модуль: конфигурация + миграция bridge_state | completed | 3 |
| D24 | Bridge-модуль: loop_guard, message_queue, vk_sender | completed | 4 |
| D25 | Bridge-модуль: telegram_forwarder, vk_listener, main_bridge | completed | 4 |
| D26 | Bridge-модуль: media_handler (TG→VK, VK→TG) | completed | 3 |
| D27 | vk_bot/: config, bot, handlers, main | completed | 3 |

**Процент выполнения:** 100% (D01–D27 completed = 100/100)

---

## Next Tasks (Post-Review Cleanup)

| ID | Task | Priority | Status |
|----|------|----------|--------|
| T01 | Исправить merge conflict markers в README.md | P0 | completed |
| T02 | Добавить BotApplication в bot/main.py | P0 | completed |
| T03 | Исправить test_user_manager.py — добавить BotApplication | P0 | completed |
| T04 | Исправить merge conflicts в тестах | P1 | completed |
| T05 | Ruff cleanup: 0 errors в продакшн коде | P2 | completed |
| T06 | Удалить лишние папки (examples/, for_programmer/, docs/archive/) | P2 | completed |
| T07 | Удалить test_*.db файлы | P2 | completed |

## Additional Tasks (2026-04-03)

| ID | Task | Priority | Status |
|----|------|----------|--------|
| T08 | BridgeBot: VK Bot публикация в канал | P0 | completed |
| T09 | Тесты BridgeBot + VK Bot (43 tests) | P0 | completed |
| T10 | Unified конфигурация (Pydantic Settings) | P1 | completed |
| T11 | Документация сокращена | P1 | completed |
| T12 | vk_listener.py перенесён в bridge_bot/ | P1 | completed |
| T13 | Рефакторинг bot/bot.py: извлечение команд | P1 | completed |
| T14 | PARSING_ENABLED=true | P2 | completed |
| T15 | Ruff cleanup, ruff.toml создан | P2 | completed |

---

## Future Improvements (Roadmap)

### Критические (Known Issues)

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F01 | Исправить сломанные unit тесты (sys.path.insert root cause) | P0 | completed |
| F02 | Проверить и удалить merge conflict markers | P0 | completed |

### Высокий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F03 | CI/CD pipeline (GitHub Actions) | P1 | completed |
| F04 | Покрытие тестами core логики (balance, shop) | P1 | completed |
| F05 | E2E тесты для бота | P1 | pending |
| F06 | Webhook вместо polling (для прода) | P1 | pending |

### Средний приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F07 | Документация API | P2 | pending |
| F08 | Мониторинг (метрики, алерты) | P2 | pending |
| F09 | Кэширование (Redis для баланса, профиля) | P2 | pending |
| F10 | Structured logging (JSON) | P2 | pending |

### Низкий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F11 | Микросервисы (разделение на сервисы) | P3 | pending |
| F12 | GraphQL API | P3 | pending |
| F13 | Kubernetes (autoscaling) | P3 | pending |
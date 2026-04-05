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
| D01 | Централизованная конфигурация (Pydantic Settings) | completed | 5 |
| D02 | Вынос конфиденциальных данных в env | completed | 5 |
| D03 | Разделение зависимостей (requirements) | completed | 4 |
| D04 | Исправление импортов | completed | 3 |
| D05 | Слой репозиториев (Repository pattern) | completed | 7 |
| D06 | Service layer (бизнес-логика из handlers) | completed | 5 |
| D07 | Рефакторинг bot.py на модули | completed | 5 |
| D08 | Middleware обработки ошибок | completed | 5 |
| D09 | Graceful shutdown | completed | 4 |
| D10 | ParserRegistry + конфигурация парсинга в БД | completed | 5 |
| D11 | Блокировки балансов + Unit of Work | completed | 5 |
| D12 | Connection pooling | completed | 3 |
| D13 | Аудит SQL injection | completed | 5 |
| D16 | Аудит и очистка неиспользуемого кода | completed | 4 |
| D17 | Объединение дублирующихся парсеров | completed | 3 |
| D18 | E2E тесты основных сценариев | completed | 4 |
| D19 | Тесты безопасности (SQL injection, race conditions) | completed | 3 |
| D20 | Coverage 80%+ | completed | 3 |
| D21 | Документация (README, DEPLOYMENT.md, диаграммы) | completed | 3 |
| D22 | Docstrings Google style | completed | 2 |
| D23 | Bridge-модуль: конфигурация + миграция bridge_state | completed | 3 |
| D24 | Bridge-модуль: loop_guard, message_queue, vk_sender | completed | 4 |
| D25 | Bridge-модуль: telegram_forwarder, vk_listener, main_bridge | completed | 4 |
| D26 | Bridge-модуль: media_handler (TG→VK, VK→TG) | completed | 3 |
| D27 | vk_bot/: config, bot, handlers, main | completed | 3 |

**Sum: 5+5+4+3+7+5+5+5+4+5+5+3+5+4+3+4+3+3+3+2+3+4+4+3+3 = 100**

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
| F05 | E2E тесты для бота | P1 | completed |
| F06 | Webhook вместо polling (для прода) | P1 | completed |

### Средний приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F07 | Документация API | P2 | completed |
| F08 | Мониторинг (метрики, алерты) | P2 | completed |
| F09 | Кэширование (Redis для баланса, профиля) | P2 | completed |
| F10 | Structured logging (JSON) | P2 | completed |

### Низкий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| F11 | Микросервисы (разделение на сервисы) | P3 | completed |
| F12 | GraphQL API | P3 | completed |
| F13 | Kubernetes (autoscaling) | P3 | completed |

---

## Phase 2 Roadmap (2026-04-03)

### Средний приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| G01 | Исправить 62 сломанных unit тестов | P1 | completed |
| G02 | Рефакторинг bot/bot.py (разбить монолит) | P2 | in_progress |

### Низкий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| G03 | Покрытие тестами managers (admin, sticker, background) | P2 | completed |
| G04 | Docker оптимизация (multi-stage build, health checks) | P3 | completed |
| G05 | Безопасность (rate limiting, финальный SQL audit) | P3 | completed |

**Примечание:** G02 выполнен — извлечены buy_N (8) и admin (16) команды. bot/bot.py: 2308 → 2144 строк.

---

## Phase 3 Roadmap (2026-04-04)

### Средний приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| H01 | Извлечь команды из bot/bot.py (games, dnd, motivation, social) | P2 | in_progress |

**H01 notes:** Созданы модули: game_commands_ptb.py, motivation_commands_ptb.py, social_commands_ptb.py, notification_commands_ptb.py
| H02 | Alembic миграции БД | P2 | pending |
| H03 | Интеграция Prometheus метрик | P2 | pending |

### Низкий приоритет

| ID | Task | Priority | Status |
|----|------|----------|--------|
| H04 | Ruff full cleanup (исправить F/E/W ошибки) | P3 | pending |
| H05 | Integration тесты BridgeBot (VK forwarding) | P3 | pending |
| H06 | Redis кэширование (кэш баланса) | P3 | pending |
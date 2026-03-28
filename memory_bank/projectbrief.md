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
| D12 | Connection pooling | pending | 3 |
| D13 | Аудит SQL injection | pending | 5 |
| D14 | Система алиасов пользователей | pending | 5 |
| D15 | DI контейнер зависимостей | completed | 5 |
| D16 | Аудит и очистка неиспользуемого кода | pending | 4 |
| D17 | Объединение дублирующихся парсеров | pending | 3 |
| D18 | E2E тесты основных сценариев | pending | 4 |
| D19 | Тесты безопасности (SQL injection, race conditions) | pending | 4 |
| D20 | Coverage 80%+ | pending | 4 |
| D21 | Документация (README, DEPLOYMENT.md, диаграммы) | pending | 3 |
| D22 | Docstrings Google style | pending | 2 |
| D23 | Bridge-модуль: конфигурация + миграция bridge_state | completed | 3 |
| D24 | Bridge-модуль: loop_guard, message_queue, vk_sender | completed | 4 |
| D25 | Bridge-модуль: telegram_forwarder, vk_listener, main_bridge | completed | 4 |
| D26 | Bridge-модуль: media_handler (TG→VK, VK→TG) | completed | 3 |

**Процент выполнения:** 65% (D01–D11, D15, D23–D26 completed = 65/100)
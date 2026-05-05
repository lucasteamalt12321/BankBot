# Project Brief — BankBot (LucasTeam)

## Что это

Telegram-бот-агрегатор для автоматического отслеживания игровой активности и начисления банковских монет. Объединяет несколько игровых платформ в единую экосистему с общей валютой.

## Поддерживаемые игры

- GD Cards (коэффициент 1:1)
- Shmalala (коэффициент 1:1)
- True Mafia (коэффициент 15:1)
- Bunker RP (коэффициент 20:1)

## Ключевые функции

- Автоматический и ручной парсинг игровых сообщений
- Единый баланс для всех игр
- Магазин товаров и услуг
- Система достижений
- Социальные функции (друзья, подарки, кланы)
- Мини-игры (Города, Убийственные слова, GD Levels)
- D&D система
- Административная панель с рассылками

## Технологии

- Python 3.x
- python-telegram-bot 20.7
- SQLAlchemy 2.x (SQLite)
- Pydantic Settings
- apscheduler
- pytest + hypothesis (property-based tests)

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
| D10 | ParserRegistry + конфигурация парсинга в БД | in_progress | 5 |
| D11 | Блокировки балансов + Unit of Work | in_progress | 6 |
| D12 | Connection pooling | pending | 3 |
| D13 | Аудит SQL injection | pending | 5 |
| D14 | Система алиасов пользователей | pending | 5 |
| D15 | DI контейнер зависимостей | pending | 5 |
| D16 | Аудит и очистка неиспользуемого кода | pending | 4 |
| D17 | Объединение дублирующихся парсеров | pending | 3 |
| D18 | E2E тесты основных сценариев | pending | 4 |
| D19 | Тесты безопасности (SQL injection, race conditions) | pending | 4 |
| D20 | Coverage 80%+ | pending | 4 |
| D21 | Документация (README, DEPLOYMENT.md, диаграммы) | pending | 3 |
| D22 | Docstrings Google style | pending | 2 |

**Сумма весов:** 100

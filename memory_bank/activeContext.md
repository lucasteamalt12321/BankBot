# Active Context

## Текущий фокус
**Приведение структуры проекта к целевой по AGENTS.md: удаление лишних папок из корня, перенос реального кода в bank_bot/, bridge_bot/, vk_bot/, common/.**

## Целевая структура (AGENTS.md)
```
BankBot/
├── bridge_bot/    # BridgeBot — реальный код (уже готов)
├── bank_bot/      # BankBot — нужно перенести реальный код из bot/, core/, database/
├── vk_bot/        # VK Bot — реальный код (уже готов)
├── common/        # общие модули — нужно перенести из config/, database/, src/
├── tests/         # тесты (оставить)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── run_bot.py
```

## Разрешённые файлы/папки в корне (AGENTS.md)
.gitignore, AGENTS.md, bot.db, README.md, requirements.txt, run_bot.py
+ Dockerfile, docker-compose.yml, requirements-dev.txt, tests/, docs/, for_programmer/, scripts/

## Лишние папки в корне (нужно убрать)
- bot/           → код переносится в bank_bot/
- core/          → код переносится в bank_bot/ и common/
- database/      → код переносится в common/
- config/        → код переносится в common/
- src/           → код переносится в common/ или bank_bot/
- utils/         → код переносится в bank_bot/ или common/
- backups/       → убрать
- data/          → убрать (bot.db в корне)
- examples/      → убрать
- test_*.db      → удалить (мусор)
- __pycache__/   → удалить

## Стратегия (безопасная миграция)
1. Перенести реальный код из bot/main.py → bank_bot/main.py
2. Перенести bot/bot.py → bank_bot/bot.py
3. Перенести bot/handlers/ → bank_bot/handlers/
4. Перенести core/di.py → bank_bot/di.py
5. Перенести core/middleware/ → bank_bot/middleware.py
6. Перенести database/database.py → common/database.py
7. Перенести config/settings.py → common/config.py
8. Обновить все импорты
9. Удалить лишние папки из корня

## Статус этапов
- [ ] Этап 1: bank_bot/ — реальный код (main, bot, handlers, di, middleware)
- [ ] Этап 2: common/ — реальный код (config, database, models, logging)
- [ ] Этап 3: Обновить импорты во всех модулях
- [ ] Этап 4: Удалить лишние папки из корня
- [ ] Этап 5: Проверка ruff + импортов
- [ ] Этап 6: Обновить memory_bank

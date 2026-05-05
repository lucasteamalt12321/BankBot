# Progress

## Статус по фазам (AGENTS.md)

### Фаза 1 — Основа ✅ ЗАВЕРШЕНА
- [x] Конфиденциальные данные вынесены в переменные окружения
- [x] Централизованная конфигурация (src/config.py, Pydantic Settings)
- [x] requirements.txt / requirements-dev.txt / requirements-docs.txt
- [x] Импорты исправлены (scripts/fix_imports.py)

### Фаза 2 — Архитектура ✅ В ОСНОВНОМ ЗАВЕРШЕНА
- [x] Слой репозиториев (src/repository/base.py, user_repository.py)
- [x] Service layer (core/services/)
- [x] bot.py разбит на модули (bot/commands/)
- [x] Middleware для ошибок (bot/middleware/error_handler.py)
- [x] Graceful shutdown (src/process_manager.py)
- [x] ParsingConfigManager, конфигурация парсинга в БД
- [ ] ParserRegistry — в работе

### Фаза 3 — Безопасность 🔄 В РАБОТЕ
- [ ] Блокировки для операций с балансом / Unit of Work
- [ ] Connection pooling
- [ ] Аудит SQL injection
- [ ] Система алиасов пользователей
- [ ] DI контейнер

### Фаза 4 — Очистка ⏳ НЕ НАЧАТА
- [ ] Аудит D&D системы
- [ ] Аудит системы кланов
- [ ] Аудит таблиц БД
- [ ] Deprecated функции

### Фаза 5 — Тесты и документация ⏳ НЕ НАЧАТА
- [ ] E2E тесты
- [ ] Тесты безопасности
- [ ] Coverage 80%+
- [ ] README / DEPLOYMENT.md / диаграммы
- [ ] Docstrings (Google style)

## Известные проблемы
- Некоторые handlers всё ещё содержат бизнес-логику
- DI не настроен — зависимости создаются вручную
- Дублирующиеся парсеры не объединены

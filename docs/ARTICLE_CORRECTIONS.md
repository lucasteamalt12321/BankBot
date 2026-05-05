# Исправления к статье "Как мы построили мета-игрового Telegram-бота"

## Найденные неточности

### 1. Импорт в parsing_handler.py
**Статья:** `from src.repository import SQLiteRepository`
**Факт:** В файле используется `from src.repository_impl import SQLiteRepository` (файл `repository.py` не существует)

### 2. Таблица bot_balances
**Статья:** Упоминается поле `last_updated`
**Факт:** В `database/database.py` таблица `BotBalance` имеет поля:
- `id`, `user_id`, `game`, `last_balance`, `current_bot_balance`, `last_updated`, `created_at`
В `src/repository_impl.py` используется упрощенная схема без `last_updated`

### 3. Миграция данных
**Статья:** "Данные из таблицы parsed_transactions не переносятся"
**Факт:** Таблица `parsed_transactions` в `database/database.py` существует, но в новой системе используется `processed_messages` для идемпотентности

### 4. Файлы, упомянутые как несуществующие
**Статья:** "src/repository.py — не существует"
**Факт:** Правильно — используется `repository_impl.py`

**Статья:** "utils/parsing/parsing_stats.py — не существует"
**Факт:** Правильно — файл не найден

**Статья:** "utils/logging/logging_config.py — не существует"
**Факт:** Правильно — файл не найден

### 5. Импорт в repository_impl.py
**Статья:** Используется `from src.models import BotBalance, UserBalance`
**Факт:** В файле `repository_impl.py` определены свои локальные классы `BotBalance` и `UserBalance` (не импортируются из models)

### 6. Метод process_game_winners
**Статья:** "True Mafia winners get 10 money each"
**Факт:** В `message_processor.py`:
- True Mafia: `fixed_amount=Decimal("10")`
- Bunker RP: `fixed_amount=Decimal("30")`

### 7. Коэффициенты по умолчанию
**Статья:** "GD Cards: 1, Shmalala: 1, True Mafia: 15, Bunker RP: 20"
**Факт:** В `coefficients.json`:
- GD Cards: 1
- Shmalala: 1
- Shmalala Karma: 1
- True Mafia: 15
- Bunker RP: 20

### 8. Файл coefficients.json
**Статья:** "коэффициенты загружаются из JSON-файла"
**Факт:** В `config/coefficients.json`:
```json
{
  "GD Cards": 1,
  "Shmalala": 1,
  "Shmalala Karma": 1,
  "True Mafia": 15,
  "Bunker RP": 20
}
```

### 9. Классификатор
**Статья:** "MessageClassifier определяет тип сообщения по ключевым фразам"
**Факт:** В `classifier.py` используется `MessageType` enum с 10 типами:
- GDCARDS_PROFILE, GDCARDS_ACCRUAL
- SHMALALA_FISHING, SHMALALA_FISHING_TOP, SHMALALA_KARMA, SHMALALA_KARMA_TOP
- TRUEMAFIA_GAME_END, TRUEMAFIA_PROFILE
- BUNKERRP_GAME_END, BUNKERRP_PROFILE
- UNKNOWN

### 10. Идемпотентность
**Статья:** "message_id (SHA256 от текста + timestamp)"
**Факт:** В `idempotency.py`:
```python
content = f"{message}{timestamp.isoformat()}"
return hashlib.sha256(content.encode()).hexdigest()
```
Используется `timestamp.isoformat()` (ISO 8601 строка), а не просто timestamp.

## Рекомендации по улучшению статьи

### 1. Добавить раздел "Текущий статус"
- Фаза 0: ЗАВЕРШЕНА (новая система парсинга создана)
- Фаза 1: В РАЗРАБОТКЕ (интеграция через ParsingHandler)
- Фаза 2: ПЛАНИРУЕТСЯ (параллельный запуск)

### 2. Уточнить про миграцию
- Старая система: `core/parsers/registry.py` → `parse_message()`
- Новая система: `src/message_processor.py` → `process_message()`
- Обе системы работают параллельно
- Старая используется в `bot/bot.py` через `parse_all_messages()`

### 3. Добавить про проблемы
- **N+1 запросы**: В `process_game_winners()` для каждого победителя вызывается `get_or_create_user()`
- **Отсутствие кеширования**: Коэффициенты загружаются из JSON при каждом обращении
- **Hot-reload**: Изменение коэффициентов требует перезапуска

### 4. Уточнить про тестирование
- Property-based тесты есть (в `.hypothesis/`)
- Unit-тесты для `balance_manager.py` НЕТ
- Интеграционные тесты с моками Telegram API

### 5. Добавить про мониторинг
- Системные метрики: CPU, память, диск, сеть
- Бизнес-метрики: пользователи, транзакции, выручка
- Производительность: время ответа, ошибки
- **Алерты на успешность парсинга НЕТ**

### 6. Уточнить про таблицу bot_balances
В `database/database.py`:
```python
class BotBalance(Base):
    id, user_id, game, last_balance, current_bot_balance, last_updated, created_at
```

В `src/repository_impl.py` (упрощенная схема):
```python
user_id, game, last_balance, current_bot_balance
```

### 7. Добавить про архитектуру
- **Модульная архитектура**: bot/, core/, database/, utils/, src/
- **Слойная структура**: UI → Handlers → Business Logic → Data Layer → DB
- **Паттерны**: Strategy (парсеры), Factory (создание парсеров), Observer (уведомления), Repository (абстракция БД)

### 8. Уточнить про коэффициенты
- GD Cards: 1 (Орбы → Банковские монеты)
- Shmalala: 1 (Монеты → Банковские монеты)
- Shmalala Karma: 1 (Карма → Банковские монеты)
- True Mafia: 15 (Деньги → Банковские монеты)
- Bunker RP: 20 (Деньги → Банковские монеты)

### 9. Добавить про систему дельт
Для профилей:
1. При первом парсинге: `bot_balance = None` → создается запись с `last_balance = parsed.orbs`
2. При повторном: `delta = parsed.orbs - bot_balance.last_balance`
3. Если `delta != 0`: `bank_change = delta * coefficient`

Для событий:
1. `current_bot_balance += parsed.points`
2. `bank_change = parsed.points * coefficient`

### 10. Добавить про обработку ошибок
- `ParserError` → логирование через `AuditLogger.log_error()`
- Транзакция откатывается (`rollback_transaction()`)
- Пользователю отправляется сообщение об ошибке
- В `parsing_handler.py` есть детальная обработка с уведомлениями

## Заключение

Статья в целом точна, но требует небольших исправлений для соответствия реальной реализации. Основные изменения:
1. Исправить импорт `SQLiteRepository` (используется `repository_impl.py`)
2. Уточнить про таблицу `bot_balances` (разные схемы в разных слоях)
3. Добавить про проблемы (N+1 запросы, отсутствие кеширования, hot-reload)
4. Уточнить про тестирование (unit-тесты НЕТ)
5. Добавить про мониторинг (алерты на успешность парсинга НЕТ)

# Быстрый старт миграции

**Для разработчиков, которые хотят начать прямо сейчас**

---

## Что нужно сделать СЕЙЧАС

### 1. Завершить реализацию новой системы (Фаза 0)

Spec уже готов: `.kiro/specs/message-parsing-system/`

**Осталось реализовать:**

```bash
# Проверить статус задач
cat .kiro/specs/message-parsing-system/tasks.md | grep "\[~\]"
```

**Приоритетные задачи:**
- [ ] `BalanceManager` (задачи 9.1-9.10)
- [ ] `IdempotencyChecker` (задачи 10.1-10.3)
- [ ] `AuditLogger` (задачи 11.1-11.3)
- [ ] `MessageProcessor` (задачи 12.1-12.5)
- [ ] Интеграционные тесты (задачи 13.1-13.12)

### 2. Запустить тесты

```bash
# Unit тесты
pytest tests/unit/test_balance_manager.py -v
pytest tests/unit/test_message_processor.py -v

# Property тесты
pytest tests/property/ -v

# Интеграционные тесты
pytest tests/integration/test_full_cycle_integration.py -v
```

### 3. Создать адаптер (Фаза 1)

```python
# bot/adapters/parsing_adapter.py
from src.message_processor import MessageProcessor
from src.parsers import *
from src.balance_manager import BalanceManager
# ... и т.д.

class ParsingAdapter:
    def __init__(self):
        # Инициализация всех компонентов
        self.processor = self._create_processor()
    
    def _create_processor(self) -> MessageProcessor:
        # Создание всех зависимостей
        pass
    
    async def process_message(self, message_text: str, message_id: str):
        # Обработка сообщения
        result = self.processor.process_message(message_text, message_id)
        return self._format_result(result)
```

---

## Структура файлов

### Текущая (старая система)
```
core/parsers/simple_parser.py  ← используется сейчас
bot/bot.py                      ← вся логика здесь
bot/handlers/parsing_handler.py ← обёртка
```

### Новая система (в разработке)
```
src/
├── parsers.py              ← 8 парсеров (готово)
├── classifier.py           ← классификатор (готово)
├── message_processor.py    ← главный процессор (нужно доделать)
├── balance_manager.py      ← менеджер балансов (нужно доделать)
├── repository.py           ← БД репозиторий (готово)
├── coefficient_provider.py ← коэффициенты (готово)
├── idempotency.py         ← защита от дубликатов (нужно доделать)
└── audit_logger.py        ← логирование (нужно доделать)
```

### После миграции (целевая)
```
core/
├── parsers/
│   ├── parsers.py         ← переместить из src/
│   └── classifier.py      ← переместить из src/
├── processors/
│   └── message_processor.py ← переместить из src/
├── managers/
│   ├── balance_manager.py ← переместить из src/
│   └── coefficient_provider.py ← переместить из src/
├── database/
│   └── repository.py      ← переместить из src/
└── utils/
    ├── idempotency.py     ← переместить из src/
    └── audit_logger.py    ← переместить из src/
```

---

## Команды для разработки

### Запуск тестов
```bash
# Все тесты
pytest tests/ -v

# Только новая система
pytest tests/unit/test_*parser*.py -v
pytest tests/property/test_*parser*.py -v

# С покрытием
pytest tests/ --cov=src --cov-report=html
```

### Проверка кода
```bash
# Линтер
flake8 src/ --max-line-length=100

# Типы
mypy src/

# Форматирование
black src/
```

### Работа с БД
```bash
# Создать тестовую БД
python database/create_test_db.py --path test_migration.db

# Проверить схему
python -c "from database.connection import get_connection; conn = get_connection('test_migration.db'); print(conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall())"
```

---

## Чеклист перед коммитом

- [ ] Все тесты проходят
- [ ] Код отформатирован (black)
- [ ] Нет ошибок линтера (flake8)
- [ ] Добавлены docstrings
- [ ] Обновлена документация (если нужно)
- [ ] Проверено на реальных сообщениях

---

## Полезные ссылки

- **Spec:** `.kiro/specs/message-parsing-system/`
- **План миграции:** `docs/MIGRATION_PLAN.md`
- **Примеры сообщений:** `for_programmer/messages_examples`
- **Текущая документация:** `docs/guides/parsing_system_guide.md`

---

## Вопросы?

Смотри полный план миграции: `docs/MIGRATION_PLAN.md`

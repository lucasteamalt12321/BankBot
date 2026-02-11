# Объединение баз данных

## Проблема

В проекте было несколько дублирующихся баз данных:
- `bot.db` в корне
- `admin_system.db` в корне  
- `data/bot.db` в папке data

Разные модули использовали разные пути, что создавало путаницу и несогласованность данных.

## Решение

Все базы данных объединены в одну: **`data/bot.db`**

## Что было сделано

### 1. Создан скрипт миграции

**Файл:** `database/unify_databases.py`

Скрипт:
- Объединяет все БД в `data/bot.db`
- Удаляет дублирующиеся БД из корня
- Проверяет структуру таблиц
- Добавляет недостающие поля (is_admin)

**Запуск:**
```bash
python database/unify_databases.py
```

**Результат:**
```
✓ Основная БД: data/bot.db
  Размер: 16,384 байт
  Пользователей: 1
✅ ОБЪЕДИНЕНИЕ ЗАВЕРШЕНО
```

### 2. Обновлены пути в коде

Изменены следующие файлы:

| Файл | Старый путь | Новый путь |
|------|-------------|------------|
| `bot/bot.py` | `bot.db` | `data/bot.db` |
| `bot/commands/advanced_admin_commands.py` | `bot.db` | `data/bot.db` |
| `bot/commands/admin_commands.py` | `data/bot.db` | ✅ Уже правильно |
| `utils/admin/admin_system.py` | `data/bot.db` | ✅ Уже правильно |
| `utils/config.py` | `sqlite:///bot.db` | `sqlite:///data/bot.db` |
| `utils/core/config.py` | `sqlite:///bot.db` | `sqlite:///data/bot.db` |
| `utils/database/simple_db.py` | `bot.db` | `data/bot.db` |
| `core/database/shop_database.py` | `bot.db` | `data/bot.db` |
| `database/backup_system.py` | `bot.db` | `data/bot.db` |
| `database/shop_migration.py` | `sqlite:///bot.db` | `sqlite:///data/bot.db` |
| `database/add_admin_field_migration.py` | `bot.db` | `data/bot.db` |
| `scripts/update_achievements.py` | `sqlite:///bot.db` | `sqlite:///data/bot.db` |
| `scripts/simple_shop_init.py` | `bot.db` | `data/bot.db` |

### 3. Очищен корень проекта

**До:**
```
BankBot/
├── bot.db              ❌ Удалено
├── admin_system.db     ❌ Удалено
├── data/
│   └── bot.db          ✅ Основная БД
└── ...
```

**После:**
```
BankBot/
├── .gitignore
├── README.md
├── run_bot.py
├── init_db.py
├── simple_init.py
├── data/
│   └── bot.db          ✅ Единственная БД
└── ...
```

## Структура базы данных

**Файл:** `data/bot.db`

**Таблицы:**
- `users` - пользователи
  - `id` - внутренний ID
  - `username` - имя пользователя
  - `first_name` - имя
  - `balance` - баланс
  - `is_admin` - флаг администратора
- `transactions` - транзакции
- `sqlite_sequence` - служебная таблица

## Преимущества

✅ **Единая точка истины** - все данные в одном месте  
✅ **Нет дублирования** - одна БД вместо трех  
✅ **Чистый корень** - только необходимые файлы  
✅ **Согласованность** - все модули используют один путь  
✅ **Простота бэкапа** - нужно копировать только один файл  

## Миграция для существующих установок

Если у вас уже есть данные в старых БД:

1. **Сделайте бэкап:**
   ```bash
   copy bot.db bot.db.backup
   copy admin_system.db admin_system.db.backup
   ```

2. **Запустите скрипт миграции:**
   ```bash
   python database/unify_databases.py
   ```

3. **Проверьте результат:**
   ```bash
   # Должна существовать только data/bot.db
   dir data\bot.db
   ```

4. **Запустите бота:**
   ```bash
   python run_bot.py
   ```

## Проверка

### Проверка путей в коде

```bash
# Не должно быть упоминаний bot.db без data/
grep -r "bot\.db" --include="*.py" | grep -v "data/bot.db"
```

### Проверка файлов

```bash
# В корне не должно быть БД
ls *.db
# Должна быть только data/bot.db
ls data/*.db
```

### Проверка работы

```python
# Все модули должны использовать data/bot.db
from utils.admin.admin_system import AdminSystem
admin = AdminSystem()
print(admin.db_path)  # Должно быть: data/bot.db
```

## Troubleshooting

### Проблема: Бот не находит БД

**Решение:**
```bash
# Убедитесь, что БД существует
python database/unify_databases.py
```

### Проблема: Данные не сохраняются

**Решение:**
```bash
# Проверьте права на запись
chmod 644 data/bot.db
```

### Проблема: Старые БД в корне

**Решение:**
```bash
# Удалите вручную
del bot.db
del admin_system.db
```

## Заключение

Все базы данных успешно объединены в `data/bot.db`. Проект теперь использует единую БД, что упрощает разработку, тестирование и развертывание.

---

**Дата:** 2026-02-08  
**Статус:** ✅ Завершено  
**Основная БД:** `data/bot.db`

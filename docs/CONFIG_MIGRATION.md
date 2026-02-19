# Миграция системы конфигурации

## Обзор изменений

В рамках унификации системы конфигурации проекта были выполнены следующие изменения:

### ✅ Что было сделано

1. **Создан единый источник конфигурации**: `src/config.py`
   - Использует Pydantic Settings для валидации
   - Поддерживает множественные окружения (development, test, staging, production)
   - Автоматическая загрузка из environment-specific файлов

2. **Удалены дублирующие файлы конфигурации**:
   - ❌ `utils/config.py` - удален
   - ❌ `utils/core/config.py` - удален
   - ✅ `src/config.py` - единственный источник конфигурации

3. **Обновлены все импорты**:
   - Старый способ: `from utils.config import ...`
   - Новый способ: `from src.config import settings`

4. **Обновлена документация**:
   - README.md - содержит инструкции по настройке
   - docs/MULTIPLE_ENVIRONMENTS.md - руководство по работе с окружениями
   - config/.env.example - пример конфигурации

## Структура конфигурации

### Единый файл конфигурации

```python
# src/config.py
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Environment
    ENV: str = Field(default="development")
    
    # Bot Configuration
    BOT_TOKEN: str
    ADMIN_TELEGRAM_ID: int
    
    # Database
    DATABASE_URL: str
    
    # Parsing
    PARSING_ENABLED: bool = Field(default=False)
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: Optional[str] = Field(default=None)

# Singleton instance
settings = get_settings()
```

### Использование в коде

```python
from src.config import settings

# Доступ к настройкам
bot_token = settings.BOT_TOKEN
admin_id = settings.ADMIN_TELEGRAM_ID
db_url = settings.DATABASE_URL
env = settings.ENV
```

## Поддержка множественных окружений

### Структура файлов

```
config/
├── .env                    # Общие настройки (fallback)
├── .env.example            # Пример конфигурации
├── .env.development        # Настройки для разработки
├── .env.test               # Настройки для тестирования
├── .env.staging            # Настройки для staging
└── .env.production         # Настройки для production
```

### Приоритет загрузки

1. **Переменные окружения** - наивысший приоритет
2. **Environment-specific файл** - `config/.env.{ENV}`
3. **Дефолтный .env файл** - `config/.env`
4. **Значения по умолчанию** - встроенные в Settings

### Запуск в разных окружениях

```bash
# Разработка (по умолчанию)
python run_bot.py

# Или явно
ENV=development python run_bot.py

# Тестирование
ENV=test python run_bot.py

# Production
ENV=production python run_bot.py
```

## Валидация конфигурации

Система автоматически валидирует все настройки при запуске:

- `BOT_TOKEN` - не может быть пустым
- `ADMIN_TELEGRAM_ID` - должен быть положительным числом
- `DATABASE_URL` - не может быть пустым
- `ENV` - должен быть одним из: development, test, staging, production
- `LOG_LEVEL` - должен быть одним из: DEBUG, INFO, WARNING, ERROR, CRITICAL

При ошибке валидации приложение не запустится и выведет понятное сообщение об ошибке.

## Миграция существующего кода

### Было (старый способ)

```python
# ❌ Устаревший импорт
from utils.config import ADMIN_ID, BOT_TOKEN
from utils.core.config import DATABASE_URL

# Использование
admin_id = ADMIN_ID
token = BOT_TOKEN
```

### Стало (новый способ)

```python
# ✅ Новый импорт
from src.config import settings

# Использование
admin_id = settings.ADMIN_TELEGRAM_ID
token = settings.BOT_TOKEN
db_url = settings.DATABASE_URL
```

## Обязательные переменные

Следующие переменные **обязательны** и должны быть установлены:

- `BOT_TOKEN` - токен Telegram бота (получите у [@BotFather](https://t.me/BotFather))
- `ADMIN_TELEGRAM_ID` - ваш Telegram ID (получите у [@userinfobot](https://t.me/userinfobot))
- `DATABASE_URL` - путь к базе данных

## Опциональные переменные

Следующие переменные имеют значения по умолчанию:

- `ENV` - окружение (по умолчанию: `development`)
- `PARSING_ENABLED` - включить парсинг (по умолчанию: `false`)
- `LOG_LEVEL` - уровень логирования (по умолчанию: `INFO`)
- `LOG_FILE` - путь к файлу логов (по умолчанию: `None` - вывод в консоль)

## Пример конфигурации

### Development

```env
# config/.env.development
ENV=development
BOT_TOKEN=your_dev_bot_token
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=sqlite:///data/bot_dev.db
PARSING_ENABLED=false
LOG_LEVEL=DEBUG
LOG_FILE=logs/bot_dev.log
```

### Production

```env
# config/.env.production
ENV=production
BOT_TOKEN=your_prod_bot_token
ADMIN_TELEGRAM_ID=123456789
DATABASE_URL=postgresql://user:password@localhost:5432/bankbot
PARSING_ENABLED=true
LOG_LEVEL=INFO
LOG_FILE=logs/bot_prod.log
```

## Безопасность

### ⚠️ Важно

1. **Никогда не коммитьте .env файлы** - они содержат конфиденциальные данные
2. **Используйте .env.example** - для документирования необходимых переменных
3. **В production используйте переменные окружения** - не храните секреты в файлах
4. **Проверьте .gitignore** - убедитесь, что `.env*` файлы исключены (кроме `.env.example`)

### Рекомендации

```bash
# .gitignore должен содержать:
config/.env
config/.env.*
!config/.env.example
```

## Устранение проблем

### Ошибка: "BOT_TOKEN cannot be empty"

**Причина**: Не установлена переменная `BOT_TOKEN`

**Решение**:
1. Создайте файл `config/.env` из `config/.env.example`
2. Укажите ваш токен бота в `BOT_TOKEN`

### Ошибка: "ENV must be one of..."

**Причина**: Указано неверное значение для `ENV`

**Решение**: Используйте одно из допустимых значений: `development`, `test`, `staging`, `production`

### Конфигурация не загружается

**Причина**: Файл `.env` не найден или имеет неверный путь

**Решение**:
1. Убедитесь, что файл находится в `config/.env` или `config/.env.{ENV}`
2. Проверьте права доступа к файлу
3. Убедитесь, что переменная `ENV` установлена правильно

### Изменения не применяются

**Причина**: Конфигурация загружается один раз при старте

**Решение**: Перезапустите приложение после изменения `.env` файлов

## Дополнительная информация

- **Полная документация**: [docs/MULTIPLE_ENVIRONMENTS.md](MULTIPLE_ENVIRONMENTS.md)
- **Пример использования**: [README.md](../README.md#установка-и-настройка)
- **Исходный код**: [src/config.py](../src/config.py)

## Статус миграции

✅ **Миграция завершена**

- [x] Создан `src/config.py` с Pydantic Settings
- [x] Удалены `utils/config.py` и `utils/core/config.py`
- [x] Обновлены все импорты в коде
- [x] Обновлена документация
- [x] Все тесты проходят

---

**Дата миграции**: 2026-02-14  
**Версия**: 2.0

# AliasService - Руководство по использованию

## Обзор

`AliasService` - это сервис для управления алиасами (псевдонимами) пользователей из разных игровых источников. Он решает проблему идентификации пользователей, когда их игровые ники отличаются от Telegram username.

## Основные возможности

1. **Добавление/удаление алиасов** - управление псевдонимами пользователей
2. **Поиск пользователей** - по алиасу с fallback на username/first_name
3. **Оценка достоверности** - confidence score для каждого алиаса
4. **Автоматическая синхронизация** - из результатов парсинга
5. **Статистика** - по алиасам пользователя

## Использование

### Базовое использование

```python
from core.services.alias_service import AliasService

# Создание сервиса
with AliasService() as service:
    # Добавить алиас
    alias = service.add_alias(
        user_id=1,
        alias_value="GameNickname",
        alias_type="nickname",
        game_source="gdcards",
        confidence_score=1.0
    )
    
    # Найти пользователя по алиасу
    user = service.find_user_by_alias("GameNickname")
    
    # Найти с fallback на username/first_name
    user = service.find_user_by_name_or_alias("GameNickname")
```

### Использование с существующей сессией

```python
from database.connection import get_connection
from core.services.alias_service import AliasService

session = get_connection()
service = AliasService(session=session)

# Работа с сервисом
alias = service.add_alias(user_id=1, alias_value="Nick")

session.close()
```

### Интеграция с парсерами

Парсеры должны использовать `find_user_by_name_or_alias` для поиска пользователей:

```python
from core.services.alias_service import AliasService

class GameParser:
    def parse(self, message: str):
        # Извлечь имя игрока из сообщения
        player_name = self.extract_player_name(message)
        
        # Найти пользователя через AliasService
        with AliasService() as service:
            user = service.find_user_by_name_or_alias(
                name=player_name,
                game_source="gdcards",  # Опционально
                min_confidence=0.7
            )
            
            if user:
                # Синхронизировать алиас для будущих поисков
                service.sync_alias_from_parser(
                    telegram_id=user.telegram_id,
                    game_name=player_name,
                    game_source="gdcards",
                    confidence_score=0.9
                )
                
                return user
        
        return None
```

### Пример обновления существующего парсера

**До:**
```python
def find_user(self, player_name: str):
    session = get_connection()
    user = session.query(User).filter_by(username=player_name).first()
    session.close()
    return user
```

**После:**
```python
def find_user(self, player_name: str):
    with AliasService() as service:
        return service.find_user_by_name_or_alias(
            name=player_name,
            game_source=self.game_source
        )
```

## API Reference

### add_alias()

Добавить новый алиас для пользователя.

```python
alias = service.add_alias(
    user_id: int,              # ID пользователя в БД
    alias_value: str,          # Значение алиаса
    alias_type: str = "nickname",  # Тип: nickname, game_name
    game_source: Optional[str] = None,  # gdcards, shmalala, etc.
    confidence_score: float = 1.0  # Оценка достоверности (0.0-1.0)
) -> UserAlias
```

**Особенности:**
- Если алиас уже существует, обновляется confidence_score (берется максимум)
- Выбрасывает `ValueError` если пользователь не найден

### remove_alias()

Удалить алиас пользователя.

```python
success = service.remove_alias(
    user_id: int,
    alias_value: str,
    game_source: Optional[str] = None
) -> bool
```

**Возвращает:** `True` если алиас удален, `False` если не найден

### find_user_by_alias()

Найти пользователя по алиасу.

```python
user = service.find_user_by_alias(
    alias_value: str,
    game_source: Optional[str] = None,
    min_confidence: float = 0.5
) -> Optional[User]
```

**Особенности:**
- Фильтрует по минимальному confidence_score
- Возвращает пользователя с наивысшим confidence_score

### find_user_by_name_or_alias()

**Основной метод для парсеров!** Найти пользователя с fallback.

```python
user = service.find_user_by_name_or_alias(
    name: str,
    game_source: Optional[str] = None,
    min_confidence: float = 0.5
) -> Optional[User]
```

**Порядок поиска:**
1. Точное совпадение алиаса (с учетом game_source)
2. Username (регистронезависимо)
3. First name (регистронезависимо)

### sync_alias_from_parser()

Синхронизировать алиас из результата парсинга.

```python
alias = service.sync_alias_from_parser(
    telegram_id: int,
    game_name: str,
    game_source: str,
    confidence_score: float = 0.9
) -> Optional[UserAlias]
```

**Использование:** Вызывать после успешной идентификации пользователя для автоматического создания/обновления алиаса.

### get_user_aliases()

Получить все алиасы пользователя.

```python
aliases = service.get_user_aliases(
    user_id: int,
    game_source: Optional[str] = None
) -> List[UserAlias]
```

**Возвращает:** Список алиасов, отсортированный по confidence_score (убывание)

### get_alias_stats()

Получить статистику по алиасам пользователя.

```python
stats = service.get_alias_stats(user_id: int) -> Dict[str, int]
```

**Возвращает:**
```python
{
    "total": 5,
    "by_game": {
        "gdcards": 2,
        "shmalala": 3
    },
    "by_type": {
        "nickname": 3,
        "game_name": 2
    }
}
```

## Confidence Score

Оценка достоверности (0.0 - 1.0) показывает, насколько уверенно можно связать алиас с пользователем:

- **1.0** - Ручное добавление пользователем через команду
- **0.9** - Автоматическое из парсера с высокой уверенностью
- **0.7** - Автоматическое из парсера со средней уверенностью
- **0.5** - Автоматическое из парсера с низкой уверенностью
- **< 0.5** - Не используется по умолчанию

## Типы алиасов

- **nickname** - Псевдоним, добавленный пользователем
- **game_name** - Имя из игрового сообщения
- **username** - Telegram username (обычно не нужен, т.к. есть в User)
- **custom** - Пользовательский тип

## Источники игр

Стандартные значения для `game_source`:
- `gdcards` - GD Cards
- `shmalala` - Shmalala
- `bunkerrp` - Bunker RP
- `truemafia` - True Mafia

## Примеры использования

### Пример 1: Добавление алиаса вручную

```python
with AliasService() as service:
    # Пользователь хочет добавить свой игровой ник
    alias = service.add_alias(
        user_id=user.id,
        alias_value="ProGamer123",
        alias_type="nickname",
        game_source="gdcards",
        confidence_score=1.0  # Максимальная уверенность
    )
    print(f"Алиас добавлен: {alias.alias_value}")
```

### Пример 2: Поиск в парсере с автосинхронизацией

```python
def process_game_message(message_text: str, telegram_id: int):
    player_name = extract_player_name(message_text)
    
    with AliasService() as service:
        # Попытка найти пользователя
        user = service.find_user_by_name_or_alias(
            name=player_name,
            game_source="gdcards"
        )
        
        if user:
            # Синхронизировать для будущих поисков
            service.sync_alias_from_parser(
                telegram_id=user.telegram_id,
                game_name=player_name,
                game_source="gdcards",
                confidence_score=0.9
            )
            
            # Начислить очки
            award_points(user, points)
        else:
            print(f"Пользователь не найден: {player_name}")
```

### Пример 3: Просмотр алиасов пользователя

```python
with AliasService() as service:
    aliases = service.get_user_aliases(user_id=1)
    
    for alias in aliases:
        print(f"{alias.alias_value} ({alias.game_source}) - "
              f"confidence: {alias.confidence_score}")
    
    # Статистика
    stats = service.get_alias_stats(user_id=1)
    print(f"Всего алиасов: {stats['total']}")
    print(f"По играм: {stats['by_game']}")
```

### Пример 4: Удаление алиаса

```python
with AliasService() as service:
    success = service.remove_alias(
        user_id=user.id,
        alias_value="OldNickname",
        game_source="gdcards"
    )
    
    if success:
        print("Алиас удален")
    else:
        print("Алиас не найден")
```

## Миграция существующих парсеров

### Шаг 1: Обновить импорты

```python
from core.services.alias_service import AliasService
```

### Шаг 2: Заменить прямые запросы к БД

**Старый код:**
```python
session = get_connection()
user = session.query(User).filter_by(username=player_name).first()
session.close()
```

**Новый код:**
```python
with AliasService() as service:
    user = service.find_user_by_name_or_alias(player_name)
```

### Шаг 3: Добавить синхронизацию алиасов

После успешной идентификации:
```python
if user:
    service.sync_alias_from_parser(
        telegram_id=user.telegram_id,
        game_name=player_name,
        game_source="your_game_source",
        confidence_score=0.9
    )
```

## Тестирование

Запуск тестов:
```bash
pytest tests/unit/test_alias_service.py -v
```

Тесты покрывают:
- Добавление/удаление алиасов
- Поиск пользователей
- Обработку дубликатов
- Confidence score
- Статистику
- Интеграцию с парсерами

## Troubleshooting

### Пользователь не найден по алиасу

1. Проверьте confidence_score - возможно он ниже порога
2. Проверьте game_source - возможно фильтр слишком строгий
3. Используйте `find_user_by_name_or_alias` вместо `find_user_by_alias`

### Дублирующиеся алиасы

Система автоматически обновляет confidence_score при добавлении дубликата. Если нужно разные алиасы для разных игр - используйте разные `game_source`.

### Низкая производительность

Используйте существующую сессию вместо создания новой:
```python
service = AliasService(session=existing_session)
```

## Будущие улучшения

- [ ] Fuzzy matching для похожих имен
- [ ] Автоматическое снижение confidence при неактивности
- [ ] История изменений алиасов
- [ ] Bulk операции для массового добавления
- [ ] Webhook для уведомлений об изменениях

## См. также

- [Database Schema](./DATABASE_SCHEMA.md)
- [Parser Integration Guide](./PARSER_INTEGRATION.md)
- [User Management](./USER_MANAGEMENT.md)

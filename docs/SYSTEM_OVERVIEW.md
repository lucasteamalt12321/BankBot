# Мета-Игровая Платформа LucasTeam - Обзор системы

## Описание системы

Telegram бот "Мета-Игровая Платформа" - это многофункциональная система, объединяющая:
- Банк-аггрегатор для сбора валют из различных игровых ботов
- Магазин внутриигровых товаров и привилегий
- Систему мини-игр (Города, Слова, Уровни GD)
- Мастерскую для проведения D&D сессий
- Социальные функции и мотивационные механизмы

## Архитектура системы

```
┌─────────────┐    ┌──────────────────────────────────┐    ┌─────────────┐
│   Telegram  │    │      Мета-Игровая Платформа      │    │  Database   │
│    API      │◄──►│           (Python)               │◄──►│  (SQLite)   │
└─────────────┘    └──────────────────────────────────┘    └─────────────┘
                        │                    │
                ┌─────────────┐      ┌─────────────┐
                │   Logging   │      │   Cache     │
                │   System    │      │   System    │
                └─────────────┘      └─────────────┘
```

## Модули системы

### 1. Модуль банка-аггрегатора

#### Поддерживаемые источники:
- Shmalala (полный набор активностей)
- GDcards
- True Mafia
- BunkerRP

#### Парсинг Shmalala:
- Система крокодила с сохранением состояния
- Начисления: победа = +5 банковских, участие = +1 банковских
- Поддержка битв, рыбалки, ловушек и других активностей

#### Многоуровневая идентификация пользователей:
- Поиск по Telegram User ID
- Поиск по username (@nickname) с нормализацией
- Поиск по имени и фамилии с fuzzy matching
- Создание новой записи с автоматическим связыванием алиасов
- Ручное объединение через админ-панель

#### Динамические коэффициенты конвертации:
```python
ADVANCED_CURRENCY_CONFIG = {
    'shmalala': {
        'base_rate': 1.0,
        'currency_name': 'coins',
        'admin_editable': True,
        'event_multipliers': {
            'battle_win': 1.0,
            'crocodile_win': 1.2,
            'fishing_bonus': 0.8
        }
    },
    'gdcards': {
        'base_rate': 2.0,
        'currency_name': 'points', 
        'admin_editable': True,
        'rarity_multipliers': {
            'common': 1.0,
            'rare': 1.5,
            'epic': 2.0,
            'legendary': 3.0
        }
    },
    'true_mafia': {'base_rate': 15.0, 'currency_name': 'wins'},
    'bunkerrp': {'base_rate': 20.0, 'currency_name': 'survivals'}
}
```

#### Валидация и безопасность транзакций:
- Максимальная сумма за раз: 100
- Защита от спама: максимум 50 транзакций в час
- Проверка дубликатов в течение 24 часов
- Анализ аномалий

### 2. Модуль магазина и виртуальных товаров

#### Категории товаров:
- Стикеры и медиа: безлимитные стикерпаки, GIF-анимации
- Привилегии: админка на день, особые роли в чате
- Игровые бусты: множители опыта, временные бонусы
- Кастомный контент: персонализированные команды, уникальные возможности

#### Система лимитов и ограничений:
```python
PURCHASE_LIMITS = {
    'default_sticker_rate': 3,           # Стикеров в час по умолчанию
    'unlimited_sticker_price': 5000,     # Стоимость безлимита
    'admin_day_price': 10000,            # Стоимость админки на день
    'cooldown_24h_items': ['admin_day'], # Товары с суточным КД
    'unique_purchases': ['custom_title'] # Уникальные покупки
}
```

#### Система активации товаров:
```python
ITEM_ACTIVATION_HANDLERS = {
    'unlimited_stickers': enable_unlimited_stickers,
    'admin_day': grant_temporary_admin,
    'experience_boost': apply_experience_multiplier,
    'custom_title': set_custom_user_title
}
```

### 3. Модуль мини-игр

#### Игра "Города"
```python
CITIES_GAME_CONFIG = {
    'max_response_time': 30,        # Секунд на ход
    'used_cities_cooldown': 100,    # Через сколько ходов город можно использовать снова
    'reward_per_turn': 5,           # Банковских монет за ход
    'penalty_invalid_city': -2,     # Штраф за несуществующий город
    'bonus_chain_5': 25,            # Бонус за цепочку из 5 городов
    'difficulty_levels': {
        'easy': {'min_population': 100000},
        'medium': {'min_population': 50000},
        'hard': {'min_population': 0}
    }
}
```

#### Игра "Слова, которые могут убить"
```python
KILLER_WORDS_CONFIG = {
    'word_categories': ['оружие', 'яды', 'стихии', 'животные'],
    'letter_combinations': ['уби', 'смер', 'конц', 'гибе'],
    'reward_killer_word': 15,       # За убийственное слово
    'penalty_weak_word': -3,        # За слабое слово
    'bonus_category_completion': 50 # За заполнение категории
}
```

#### Система уровней GD (Geometric Dash)
Игра по правилам игры в города, но уровни geometry dash английскими буквами

### 4. Модуль D&D Мастерской

#### Система управления сессиями
```python
DND_MASTER_CONFIG = {
    'max_players_per_session': 6,
    'session_duration_limit': 1000,    # Часов
    'master_reward_per_hour': 100,  # Вознаграждение мастера
    'player_attendance_bonus': 20,  # Бонус за участие
    'achievement_system': True      # Система достижений за сессии
}
```

#### Функционал для мастера:
- Создание и планирование сессий
- Управление игроками и персонажами
- Бросок костей с различными модификаторами
- Ведение журнала событий и лора
- Система инвентаря и квестов

#### Функционал для игроков:
- Регистрация на сессии
- Создание и развитие персонажей
- Бросок костей в рамках сессии
- Отслеживание прогресса и достижений

### 5. Мотивационная система и социальные функции

#### Расширенная система ежедневных бонусов
```python
ENHANCED_DAILY_BONUS = {
    'base_amount': 10,
    'streak_multipliers': {
        1: 1.0,    # 10 монет
        3: 1.5,    # 15 монет
        7: 2.0,    # 20 монет
        14: 2.5,   # 25 монет
        30: 3.0,   # 30 монет
        90: 4.0,   # 40 монет
        365: 5.0   # 50 монет
    },
    'activity_bonuses': {
        'mini_game_played': 5,
        'shop_purchase': 10, 
        'dnd_session': 25,
        'invite_friend': 50
    },
    'weekly_challenges': True,      # Еженедельные задания
    'monthly_leaderboards': True    # Месячные рейтинги
}
```

#### Социальные функции
```python
SOCIAL_FEATURES = {
    'user_profiles': True,          # Публичные профили
    'friends_system': True,         # Система друзей
    'gifting_system': True,         # Подарки друзьям
    'clans_guilds': True,           # Кланы и гильдии
    'achievements_showcase': True   # Витрина достижений
}
```

## Административная панель

### Расширенные команды администрирования

#### Управление банком
- `/admin_rates` - Просмотр коэффициентов
- `/admin_rate <game> <value>` - Изменение коэффициента
- `/admin_merge @user1 @user2` - Объединение аккаунтов
- `/admin_transactions @user` - История транзакций пользователя

#### Управление магазином
- `/admin_shop_add` - Добавление товара
- `/admin_shop_edit <item_id>` - Редактирование товара
- `/admin_shop_stats` - Статистика магазина

#### Управление играми
- `/admin_games_stats` - Статистика по играм
- `/admin_reset_game <game>` - Сброс состояния игры
- `/admin_ban_player @user <game>` - Бан в конкретной игре

#### Системный мониторинг
- `/admin_health` - Проверка здоровья системы
- `/admin_errors [date]` - Просмотр ошибок
- `/admin_backup` - Ручное резервное копирование
- `/admin_cleanup` - Очистка устаревших данных

### Система алертов и мониторинга
```python
ALERT_SYSTEM = {
    'transaction_anomalies': True,      # Аномальные транзакции
    'system_errors': True,              # Критические ошибки
    'performance_issues': True,         # Проблемы производительности
    'security_events': True,            # Подозрительная активность
    'business_metrics': True            # Ключевые бизнес-метрики
}
```

## Технические требования

### Стек технологий
- Язык: Python 3.9+
- Фреймворк: python-telegram-bot 20.0+
- База данных: SQLite 3.x с миграцией на PostgreSQL
- ORM: SQLAlchemy 2.0+
- Кэширование: Redis (опционально)
- Логирование: structlog + ротация логов
- Конфигурация: Pydantic + python-dotenv

### Производительность и масштабируемость
```python
PERFORMANCE_TARGETS = {
    'message_processing': '< 2 секунд',
    'command_response': '< 1 секунды', 
    'concurrent_users': '100+',
    'daily_messages': '500+',
    'database_size': 'до 10GB',
    'uptime': '99.9%'
}
```

## Структура базы данных (расширенная)

### Основные таблицы (25+ таблиц)
- users
- user_aliases
- user_profiles
- transactions
- currency_config
- error_logs

### Магазин
- shop_categories
- shop_items
- user_purchases
- purchase_activations

### Мини-игры
- game_sessions
- game_players
- cities_game_state
- killer_words_progress
- gd_levels_completions

### D&D система
- dnd_sessions
- dnd_characters
- dnd_quests
- dnd_dice_rolls

### Социальные функции
- friendships
- user_achievements
- clans
- gifts

### Системные таблицы
- system_logs
- backup_history
- admin_alerts

## Команды бота

### Основные команды
- `/start` - приветственное сообщение
- `/balance` - проверка баланса
- `/history` - история транзакций
- `/profile` - профиль пользователя
- `/stats` - персональная статистика

### Магазин
- `/shop` - каталог товаров
- `/buy <id>` - покупка товара
- `/inventory` - инвентарь

### Мини-игры
- `/games` - информация о мини-играх
- `/play <type>` - создание игры
- `/join <id>` - присоединение к игре
- `/startgame <id>` - начало игры
- `/turn <id> <ход>` - выполнение хода

### D&D
- `/dnd` - информация о D&D системе
- `/dnd_create <название> [описание]` - создание сессии
- `/dnd_join <id>` - присоединение к сессии
- `/dnd_sessions` - список сессий
- `/dnd_roll <тип> [модификатор] [цель]` - бросок костей

### Мотивация
- `/daily` - ежедневный бонус
- `/challenges` - задания
- `/streak` - статистика мотивации

### Достижения и уведомления
- `/achievements` - достижения
- `/notifications` - уведомления
- `/notifications_clear` - очистка уведомлений

### Социальные функции
- `/friends` - друзья
- `/friend_add <пользователь>` - добавить друга
- `/gift <пользователь> <сумма> [сообщение]` - отправить подарок
- `/clan` - информация о клане
- `/clan_create <название> [описание]` - создать клан
- `/clan_join <название>` - вступить в клан
- `/clan_leave` - покинуть клан

## Система безопасности

### Проверки и валидации
- Защита от SQL-инъекций
- Валидация всех входящих данных
- Корректное разграничение прав доступа
- Шифрование конфиденциальных данных

### Мониторинг безопасности
- Отслеживание подозрительной активности
- Логирование безопасности
- Валидация пользовательских действий

## Процедуры обновления

- Автоматические миграции базы данных
- Постепенное развертывание новых функций
- Роллбек-процедуры при критических ошибках
- Резервное копирование перед всеми обновлениями

## Мониторинг работоспособности

```python
MONITORING_METRICS = {
    'system_health': ['cpu', 'memory', 'disk', 'network'],
    'business_metrics': ['active_users', 'transactions', 'revenue'],
    'performance_metrics': ['response_time', 'error_rate', 'throughput'],
    'security_metrics': ['failed_logins', 'suspicious_activities']
}
```

## Политика обновлений и поддержки

- Еженедельные патчи и исправления ошибок
- Ежемесячные обновления с новыми функциями
- Квартальный аудит безопасности
- Годовой пересмотр архитектуры системы

Система разработана с учетом будущего масштабирования и может быть расширена дополнительными модулями, интеграциями с другими платформами и усовершенствованными механиками игр.
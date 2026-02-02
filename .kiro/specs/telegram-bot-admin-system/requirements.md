# Requirements Document

## Introduction

Доработка существующего Telegram-бота на Python с добавлением полноценной системы администрирования, магазина товаров и улучшенной структуры базы данных. Бот должен поддерживать автоматическую регистрацию пользователей, административные команды для управления очками и пользователями, а также систему покупок в магазине.

## Glossary

- **Telegram_Bot**: Основная система бота, обрабатывающая команды пользователей
- **Admin_System**: Подсистема для управления пользователями и очками администраторами
- **Shop_System**: Система магазина для покупки товаров за очки
- **Database_System**: SQLite база данных для хранения пользователей и транзакций
- **User**: Зарегистрированный пользователь бота с уникальным Telegram ID
- **Administrator**: Пользователь с флагом is_admin = True, имеющий доступ к административным командам
- **Transaction**: Запись о финансовой операции (начисление, списание, покупка)

## Requirements

### Requirement 1

**User Story:** Как администратор, я хочу иметь доступ к панели администратора, чтобы видеть доступные команды и статистику пользователей

#### Acceptance Criteria

1. WHEN администратор отправляет команду /admin, THE Telegram_Bot SHALL отправить сообщение со списком административных команд и общим количеством пользователей
2. IF пользователь без прав администратора отправляет команду /admin, THEN THE Telegram_Bot SHALL отправить сообщение об отсутствии прав доступа
3. THE Admin_System SHALL проверять флаг is_admin в таблице users для определения прав доступа
4. THE Telegram_Bot SHALL отображать команды в формате: "/add_points @username [число] - начислить очки" и "/add_admin @username - добавить администратора"

### Requirement 2

**User Story:** Как администратор, я хочу начислять очки пользователям, чтобы поощрять их активность

#### Acceptance Criteria

1. WHEN администратор отправляет команду /add_points с корректными параметрами, THE Admin_System SHALL добавить указанное количество очков к балансу пользователя
2. THE Admin_System SHALL создать запись в таблице transactions с типом 'add' и ID администратора
3. THE Telegram_Bot SHALL отправить подтверждение в формате "Пользователю @username начислено X очков. Новый баланс: Y"
4. IF указанный пользователь не найден, THEN THE Telegram_Bot SHALL отправить сообщение об ошибке
5. IF формат команды неверный, THEN THE Telegram_Bot SHALL отправить инструкцию по использованию

### Requirement 3

**User Story:** Как администратор, я хочу назначать других пользователей администраторами, чтобы делегировать управление ботом

#### Acceptance Criteria

1. WHEN администратор отправляет команду /add_admin с username, THE Admin_System SHALL установить флаг is_admin = TRUE для указанного пользователя
2. THE Telegram_Bot SHALL отправить подтверждение "Пользователь @username теперь администратор"
3. IF указанный пользователь не найден, THEN THE Telegram_Bot SHALL отправить сообщение об ошибке
4. THE Database_System SHALL обновить запись пользователя в таблице users

### Requirement 4

**User Story:** Как пользователь, я хочу видеть доступные товары в магазине, чтобы потратить накопленные очки

#### Acceptance Criteria

1. WHEN пользователь отправляет команду /shop, THE Shop_System SHALL отправить список доступных товаров с ценами
2. THE Telegram_Bot SHALL отображать товары в формате "1. Сообщение админу - 10 очков"
3. THE Shop_System SHALL включать инструкцию "Для покупки введите /buy_contact"

### Requirement 5

**User Story:** Как пользователь, я хочу покупать товары в магазине, чтобы получать услуги за накопленные очки

#### Acceptance Criteria

1. WHEN пользователь отправляет команду /buy_contact, THE Shop_System SHALL проверить достаточность баланса (минимум 10 очков)
2. IF баланс достаточный, THE Shop_System SHALL списать 10 очков с баланса пользователя
3. THE Shop_System SHALL создать транзакцию типа 'buy' в таблице transactions
4. THE Telegram_Bot SHALL отправить пользователю подтверждение "Вы купили контакт. Администратор свяжется с вами."
5. THE Shop_System SHALL отправить всем администраторам сообщение "Пользователь @username купил контакт. Его баланс: X очков"
6. IF баланс недостаточный, THEN THE Telegram_Bot SHALL отправить сообщение о недостатке очков

### Requirement 6

**User Story:** Как новый пользователь, я хочу автоматически регистрироваться при первом обращении к боту, чтобы начать использовать его функции

#### Acceptance Criteria

1. WHEN пользователь отправляет любое сообщение боту впервые, THE Database_System SHALL создать новую запись в таблице users
2. THE Database_System SHALL заполнить поля: id (Telegram ID), username, first_name, balance = 0, is_admin = FALSE
3. IF пользователь уже существует в базе данных, THEN THE Database_System SHALL не создавать дублирующую запись
4. THE Telegram_Bot SHALL обрабатывать регистрацию прозрачно для пользователя

### Requirement 7

**User Story:** Как разработчик, я хочу иметь правильную структуру базы данных, чтобы обеспечить корректную работу всех функций

#### Acceptance Criteria

1. THE Database_System SHALL содержать таблицу users с колонками: id (INTEGER PRIMARY KEY), username (TEXT), first_name (TEXT), balance (REAL DEFAULT 0), is_admin (BOOLEAN DEFAULT FALSE)
2. THE Database_System SHALL содержать таблицу transactions с колонками: id (INTEGER PRIMARY KEY AUTOINCREMENT), user_id (INTEGER), amount (REAL), type (TEXT), admin_id (INTEGER), timestamp (DATETIME DEFAULT CURRENT_TIMESTAMP)
3. THE Database_System SHALL использовать внешние ключи для связи таблиц users и transactions
4. THE Database_System SHALL автоматически создавать таблицы при первом запуске бота
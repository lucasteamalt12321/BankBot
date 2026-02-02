# Requirements Document

## Introduction

Доработка существующего Telegram-бота на Python с добавлением полноценной системы администрирования, магазина товаров и улучшенной структуры базы данных. Бот должен поддерживать автоматическую регистрацию пользователей, административные команды для управления очками и пользователями, а также систему покупок в магазине. Система использует библиотеку pyTelegramBotAPI и SQLite для хранения данных.

## Glossary

- **Telegram_Bot**: Основная система бота, обрабатывающая команды пользователей через pyTelegramBotAPI
- **Admin_System**: Подсистема для управления пользователями и очками администраторами
- **Shop_System**: Система магазина для покупки товаров за очки
- **Database_System**: SQLite база данных для хранения пользователей и транзакций
- **User**: Зарегистрированный пользователь бота с уникальным Telegram ID
- **Administrator**: Пользователь с флагом is_admin = True, имеющий доступ к административным командам
- **Transaction**: Запись о финансовой операции (начисление, списание, покупка)
- **Auth_Decorator**: Функция-декоратор для проверки прав администратора

## Requirements

### Requirement 1

**User Story:** Как администратор, я хочу иметь доступ к панели администратора, чтобы видеть доступные команды и статистику пользователей

#### Acceptance Criteria

1. WHEN администратор отправляет команду /admin, THE Telegram_Bot SHALL отправить сообщение в точном формате: "Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: [число]"
2. IF пользователь без прав администратора отправляет команду /admin, THEN THE Telegram_Bot SHALL отправить сообщение об отсутствии прав доступа
3. THE Auth_Decorator SHALL проверять флаг is_admin в таблице users для определения прав доступа
4. THE Admin_System SHALL подсчитывать общее количество пользователей в базе данных для отображения в панели

### Requirement 2

**User Story:** Как администратор, я хочу начислять очки пользователям, чтобы поощрять их активность

#### Acceptance Criteria

1. WHEN администратор отправляет команду в формате "/add_points @username [число]", THE Admin_System SHALL добавить указанное количество очков к балансу пользователя
2. THE Admin_System SHALL создать запись в таблице transactions с типом 'add' и ID администратора
3. THE Telegram_Bot SHALL отправить подтверждение в точном формате "Пользователю @username начислено [число] очков. Новый баланс: [новый_баланс]"
4. IF указанный пользователь не найден в базе данных, THEN THE Telegram_Bot SHALL отправить сообщение об ошибке
5. IF формат команды неверный, THEN THE Telegram_Bot SHALL отправить инструкцию по использованию
6. THE Auth_Decorator SHALL проверять права администратора перед выполнением команды

### Requirement 3

**User Story:** Как администратор, я хочу назначать других пользователей администраторами, чтобы делегировать управление ботом

#### Acceptance Criteria

1. WHEN администратор отправляет команду в формате "/add_admin @username", THE Admin_System SHALL установить флаг is_admin = TRUE для указанного пользователя
2. THE Telegram_Bot SHALL отправить подтверждение в точном формате "Пользователь @username теперь администратор"
3. IF указанный пользователь не найден в базе данных, THEN THE Telegram_Bot SHALL отправить сообщение об ошибке
4. THE Database_System SHALL обновить запись пользователя в таблице users
5. THE Auth_Decorator SHALL проверять права администратора перед выполнением команды

### Requirement 4

**User Story:** Как пользователь, я хочу видеть доступные товары в магазине, чтобы потратить накопленные очки

#### Acceptance Criteria

1. WHEN пользователь отправляет команду /shop, THE Shop_System SHALL отправить сообщение в точном формате: "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
2. THE Shop_System SHALL отображать все доступные товары с их ценами в очках
3. THE Telegram_Bot SHALL обрабатывать команду /shop для всех зарегистрированных пользователей

### Requirement 5

**User Story:** Как пользователь, я хочу покупать товары в магазине, чтобы получать услуги за накопленные очки

#### Acceptance Criteria

1. WHEN пользователь отправляет команду /buy_contact, THE Shop_System SHALL проверить достаточность баланса (минимум 10 очков)
2. IF баланс достаточный, THE Shop_System SHALL списать 10 очков с баланса пользователя
3. THE Shop_System SHALL создать транзакцию типа 'buy' в таблице transactions с указанием user_id покупателя
4. THE Telegram_Bot SHALL отправить пользователю подтверждение в точном формате "Вы купили контакт. Администратор свяжется с вами."
5. THE Shop_System SHALL отправить всем администраторам личное сообщение в формате "Пользователь @username купил контакт. Его баланс: [новый_баланс] очков"
6. IF баланс недостаточный, THEN THE Telegram_Bot SHALL отправить сообщение о недостатке очков с указанием текущего баланса

### Requirement 6

**User Story:** Как новый пользователь, я хочу автоматически регистрироваться при первом обращении к боту, чтобы начать использовать его функции

#### Acceptance Criteria

1. WHEN пользователь отправляет любое сообщение или команду боту впервые, THE Database_System SHALL проверить существование пользователя по Telegram ID
2. IF пользователь не существует в базе данных, THE Database_System SHALL создать новую запись в таблице users
3. THE Database_System SHALL заполнить поля: id (Telegram ID), username (@username если есть), first_name (имя пользователя), balance = 0, is_admin = FALSE
4. IF пользователь уже существует в базе данных, THEN THE Database_System SHALL не создавать дублирующую запись
5. THE Telegram_Bot SHALL обрабатывать регистрацию прозрачно для пользователя без дополнительных сообщений

### Requirement 7

**User Story:** Как разработчик, я хочу иметь правильную структуру базы данных, чтобы обеспечить корректную работу всех функций

#### Acceptance Criteria

1. THE Database_System SHALL содержать таблицу users с точной структурой: id (INTEGER PRIMARY KEY - Telegram ID), username (TEXT), first_name (TEXT), balance (REAL DEFAULT 0), is_admin (BOOLEAN DEFAULT FALSE)
2. THE Database_System SHALL содержать таблицу transactions с точной структурой: id (INTEGER PRIMARY KEY AUTOINCREMENT), user_id (INTEGER), amount (REAL), type (TEXT со значениями 'add', 'remove', 'buy'), admin_id (INTEGER), timestamp (DATETIME DEFAULT CURRENT_TIMESTAMP)
3. THE Database_System SHALL использовать внешние ключи для связи user_id в transactions с id в users
4. THE Database_System SHALL автоматически создавать таблицы при первом запуске бота
5. THE Database_System SHALL использовать SQLite как основную СУБД

### Requirement 8

**User Story:** Как разработчик, я хочу иметь надежную систему обработки ошибок и технических требований, чтобы обеспечить стабильную работу бота

#### Acceptance Criteria

1. THE Telegram_Bot SHALL использовать библиотеку pyTelegramBotAPI для взаимодействия с Telegram API
2. THE Auth_Decorator SHALL реализовать проверку прав администратора через декоратор или функцию
3. THE Telegram_Bot SHALL обрабатывать ошибки недостаточного количества очков с информативными сообщениями
4. THE Telegram_Bot SHALL обрабатывать ошибки "пользователь не найден" с соответствующими уведомлениями
5. THE Telegram_Bot SHALL обрабатывать ошибки неверного формата команд с инструкциями по использованию
6. THE Database_System SHALL обрабатывать ошибки подключения к базе данных без прерывания работы бота
7. THE Telegram_Bot SHALL сохранять существующий функционал, если он не противоречит новым требованиям
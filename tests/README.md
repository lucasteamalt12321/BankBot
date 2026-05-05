# Структура тестов

Эта папка содержит все тесты для Telegram бота. Тесты организованы по типам и функциональности.

## Типы тестов

### 🔧 Unit тесты (базовая функциональность)
- `test_admin_manager.py` - Управление администраторами
- `test_purchase_handler_unit.py` - Обработка покупок
- `test_shop_manager.py` - Управление магазином
- `test_message_parser.py` - Парсинг сообщений
- `test_sticker_manager.py` - Управление стикерами
- `test_bank_system.py` - Банковская система
- `test_broadcast_system.py` - Система рассылки
- `test_config_manager.py` - Управление конфигурацией
- `test_background_task_manager.py` - Фоновые задачи
- `test_user_manager.py` - Управление пользователями
- `test_parsers.py` - Парсеры сообщений

### 🔗 Интеграционные тесты (взаимодействие компонентов)
- `test_purchase_integration.py` - Интеграция покупок
- `test_shop_manager_integration.py` - Интеграция магазина
- `test_message_monitoring_middleware.py` - Middleware парсинга
- `test_admin_manager_integration.py` - Интеграция администратора
- `test_background_integration.py` - Интеграция фоновых задач
- `test_balance_integration.py` - Интеграция баланса
- `test_bot_command_integration.py` - Интеграция команд бота
- `test_checkpoint_integration.py` - Интеграция контрольных точек
- `test_config_integration.py` - Интеграция конфигурации
- `test_full_cycle_integration.py` - Полный цикл интеграции

### 🎯 Property-based тесты (свойства системы)
- `test_add_points_pbt.py` - Добавление очков
- `test_admin_status_persistence_pbt.py` - Персистентность статуса админа
- `test_authorization_pbt.py` - Авторизация
- `test_auto_registration_pbt.py` - Автоматическая регистрация
- `test_balance_validation_deduction_pbt.py` - Валидация баланса
- `test_currency_conversion_logging_pbt.py` - Логирование конвертации
- `test_database_integrity_pbt.py` - Целостность БД
- `test_database_schema_integrity_pbt.py` - Целостность схемы БД
- `test_error_handling_consistency_pbt.py` - Консистентность обработки ошибок
- `test_message_pattern_parsing_pbt.py` - Парсинг паттернов
- `test_purchase_balance_validation_pbt.py` - Валидация баланса при покупке
- `test_purchase_effects_pbt.py` - Эффекты покупок
- `test_purchase_validation_pbt.py` - Валидация покупок
- `test_shop_accessibility_pbt.py` - Доступность магазина
- `test_shop_display_completeness_pbt.py` - Полнота отображения магазина
- `test_sticker_access_lifecycle_pbt.py` - Жизненный цикл доступа к стикерам
- `test_sticker_usage_control_pbt.py` - Контроль использования стикеров
- `test_transaction_logging_pbt.py` - Логирование транзакций

### ⚙️ Специальные тесты (специфичные функции)
- `test_add_item_command.py` - Команда добавления товара
- `test_add_item_command_integration.py` - Интеграция команды добавления
- `test_add_item_integration.py` - Интеграция добавления товара
- `test_add_admin_simple.py` - Простое добавление админа
- `test_add_admin_verification.py` - Верификация добавления админа
- `test_advanced_admin_commands.py` - Продвинутые команды админа
- `test_advanced_database_schema.py` - Продвинутая схема БД
- `test_balance_command_update.py` - Обновление команды баланса
- `test_bot_commands.py` - Команды бота
- `test_shop_command.py` - Команда магазина
- `test_edge_cases_unit.py` - Граничные случаи
- `test_message_formats_unit.py` - Форматы сообщений
- `test_message_formats_integration.py` - Интеграция форматов
- `test_message_formats_bot_verification.py` - Верификация форматов
- `test_admin_commands_integration.py` - Интеграция команд администратора
- `test_admin_notification_integration.py` - Интеграция уведомлений администратора

## Запуск тестов

### Все тесты
```bash
pytest tests/
```

### Только unit тесты
```bash
pytest tests/test_*_unit.py tests/test_admin_manager.py tests/test_shop_manager.py tests/test_message_parser.py tests/test_sticker_manager.py tests/test_bank_system.py tests/test_broadcast_system.py tests/test_config_manager.py tests/test_background_task_manager.py tests/test_user_manager.py tests/test_parsers.py
```

### Только интеграционные тесты
```bash
pytest tests/test_*_integration.py tests/test_message_monitoring_middleware.py tests/test_full_cycle_integration.py
```

### Только property-based тесты
```bash
pytest tests/test_*_pbt.py
```

### Конкретный модуль
```bash
pytest tests/test_shop_manager.py -v
```

## Структура папок

- `integration/` - Дополнительные интеграционные тесты
- `property/` - Дополнительные property-based тесты  
- `unit/` - Дополнительные unit тесты
- `reports/` - Отчеты о тестировании
- `temp_files/` - Временные файлы (пустая после очистки)

## Соглашения по именованию

- `test_*_unit.py` - Unit тесты
- `test_*_integration.py` - Интеграционные тесты
- `test_*_pbt.py` - Property-based тесты
- `test_*.py` - Обычные тесты (unit по умолчанию)

## Статистика

- **Всего тестов**: ~52 файла
- **Unit тесты**: 11 файлов
- **Интеграционные тесты**: 11 файлов  
- **Property-based тесты**: 18 файлов
- **Специальные тесты**: 12 файлов

Структура оптимизирована для быстрого поиска и понимания назначения каждого теста.
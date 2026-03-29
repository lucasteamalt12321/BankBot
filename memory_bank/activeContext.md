# Active Context

## Текущий фокус
**Решение проблем из ревизии: merge conflicts, сломанные тесты, очистка legacy-кода.**

## Следующие задачи (2026-03-29)

### P0 — Критические
1. [ ] Исправить merge conflict markers в README.md (строки 260-307)
2. [ ] Добавить `BotApplication` в bot/main.py или удалить 18 тестов в test_shutdown_resource_cleanup.py
3. [ ] Исправить test_user_manager.py — добавить миграцию колонки alias для in-memory тестов

### P1 — Высокий приоритет
4. [ ] Исправить merge conflicts в test_task_9_verification.py и test_auto_registration_pbt.py
5. [ ] Очистить ruff errors в legacy коде (354 errors)

### P2 — Опционально
6. [ ] Удалить лишние папки из корня (backups/, data/, examples/)
7. [ ] Удалить test_*.db файлы

## Статус предыдущих этапов
- [x] bridge_bot/ — реальный код ✅
- [x] bank_bot/ — реальный код ✅
- [x] vk_bot/ — реальный код ✅
- [x] common/ — реальный код ✅
- [x] Dockerfile, docker-compose.yml ✅
- [x] Core services tests (706 passed) ✅

## Известные проблемы (Known Issues)
- **README.md**: Merge conflict markers (строки 260-307)
- **test_shutdown_resource_cleanup.py**: Импорт `BotApplication` не найден
- **test_user_manager.py**: Таблица `users` без колонки `alias`
- **test_task_9_verification.py**: Merge conflict markers
- **test_auto_registration_pbt.py**: Merge conflict markers
- **Ruff**: 354 errors в legacy коде

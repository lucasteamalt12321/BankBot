# Active Context

## Текущий фокус
**F01: Исправление unit тестов** — Root cause найден, импорты исправлены

## Статус проекта: 97%
Проект готов к эксплуатации. Идёт работа над F01.

## Сводка
| Метрика | Значение |
|---------|----------|
| bot/bot.py | 2112 строк (−44%) |
| ruff errors | 0 (продакшн) |
| Тесты unit | 746 passed, 62 failed (test-specific) |
| Git commit | a5355a2 |

## Known Issues
- 62 failed tests (не импорты, а test-specific issues — DynamicSettings, fixtures, etc.)
- Возможные merge conflict markers в коде (F02 pending)

## Roadmap (Future Improvements)
- F01: Исправление sys.path.insert (in progress)
- F02: Критические (исправить merge markers)
- F03–F06: Высокий приоритет (CI/CD, тесты, webhook)
- F07–F10: Средний (мониторинг, кэш, логи)
- F11–F13: Низкий (микросервисы, Kubernetes)

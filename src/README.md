# src/ — Legacy-слой (deprecated)

Этот пакет содержит оригинальный монолитный код до рефакторинга.

**Статус:** deprecated, не удалять — используется в тестах `tests/property/`.

**Новые аналоги:**
| Старый модуль | Новый модуль |
|---|---|
| `src/config.py` | `config/settings.py` |
| `src/repository.py` | `core/repositories/` |
| `src/balance_manager.py` | `core/services/balance_service.py` |
| `src/parsers.py` | `core/parsers/` |
| `src/message_processor.py` | `core/managers/` |
| `src/models.py` | `core/models/` |

Не добавлять новый код в этот пакет.

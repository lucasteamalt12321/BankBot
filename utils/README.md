# utils/ — Compatibility shims (deprecated)

Этот пакет содержит shim-модули для обратной совместимости со старыми путями импорта.

**Статус:** deprecated, не удалять — используется в тестах `tests/unit/`.

**Новые аналоги:**
| Старый путь | Новый путь |
|---|---|
| `utils.admin_system` | `utils.admin.admin_system` |
| `utils.simple_db` | `utils.database.simple_db` |
| `utils.config` | `src.config` |
| `utils.core.user_manager` | `core/services/user_service.py` |
| `utils.core.error_handling` | `core/middleware/error_handling.py` |

Импорты через старые пути выдают `DeprecationWarning`.
Не добавлять новый код в этот пакет.

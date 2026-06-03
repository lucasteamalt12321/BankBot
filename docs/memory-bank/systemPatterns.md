# Legacy Memory Bank Mirror — System Patterns

Канонический файл: [`memory_bank/systemPatterns.md`](../../memory_bank/systemPatterns.md).

Высокоуровневая архитектура по правилу `AGENTS.md` описывается в [`docs/README.md`](../README.md). Этот файл не должен становиться вторым источником архитектурной правды.

Старое содержимое этого mirror описывало SQLite-only production и устаревшие фоновые runtime-компоненты. Текущий канон: HF webhook runtime, PostgreSQL/Supabase production storage, local/dev polling fallback, безопасный reply-only parsing.

# TODO

- [x] LthubTunnel: прогресс пробы нод — сделано (2026-10-14)
- [x] LthubTunnel: прокси-автоопределение (http/socks5h) — сделано (2026-10-14, `proxy.py`)
- [x] Протестировать туннель 127.0.0.1:2080 — сделано (туннель поднимается и проксирует; публичные ноды мёртвые/whitelist)
- [x] BUGHUNT Phase 11: BUG-04..BUG-10 — сделано (2026-10-15, см. progress.md)
- [x] Обновить memory_bank и last_checked_commit — сделано (2026-10-18, `1fdaa62`)
- [x] Зеркало RelaxDev — решено: оставить Vercel основным, зеркало не поднимать
- [x] Закоммитить и запушить блок — сделано (2026-10-18): `a8570b5` (туннель), `1fdaa62` (BUGHUNT) → `origin/main`
- [x] Переписать историю git, убрать `data/chat_export/` (274 файла PII) — сделано (2026-10-18): `git filter-repo` в зеркальном клоне + `push --force` (`main` и тег `lthub-tunnel-v1`); дерево `HEAD` до/после идентично, 3 PII-коммита отфильтрованы, `deploy-clean` не переписывался
- [x] Разобрать незакоммиченный WIP `api/index.py` (study-chat) — сделано (2026-10-18, `f756160`): прежний контракт `prompt`/`ok`/`actions` возвращён; база осталась открытой анонимам (`0041376`)
- [x] `cmd_up` туннеля проверяет только «порт слушает» → добавить живость своего sing-box — сделано (2026-10-18, `57b0d9d`): `listening_pids()` + `own_tunnel_problem()` в `up` и `TunnelSession.start`, +11 регрессионных тестов
- [x] Проверить зелёный CI на `main` — сделано (2026-10-18): `774e797` — Lint / Test / Integration Tests / Coverage — success (run 39135293160)

## Открыто (ждёт решения)

- [ ] TUN-08: серверная раздача конфигов туннеля — ещё не согласовано
- [ ] Чужие файлы в корне не закоммичены (не трогал): `AGENTS.md` (правка автора) и отладочные `*.py` (`dbg*.py`, `fchat*.py`, `t*.py`, `f2.py`, `f3.py`, `fix*.py`, `dchat.py`)
- [ ] Продуктовые deliverables, оставшиеся `in_progress` (22.5 веса): B07 Universe, B08 AI, B10 Mom, B11 Family Budget, B12 VK Mini App, B16 Code Explainer, B21 Tunnel — см. `projectbrief.md` → `## Project Deliverables`
- [ ] Опционально: удалить бэкап старой истории (ветка `backup/pre-pii-rewrite`, `%TEMP%\bb_backup_245ab4f.bundle`) и временные каталоги `%TEMP%\bb_*`
- [ ] Render-реле для обхода блокировки `*.vercel.app` из РФ (реализовано `relay/` + тесты + пинг в `hf-watchdog.yml`): требуется деплой на Render (сервис из `relay/`, без карты) + добавить секрет `RENDER_RELAY_URL` — см. `relay/README.md`

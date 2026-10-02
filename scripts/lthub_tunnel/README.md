# lthub-tunnel — доступ к сайту из РФ

Сайт живёт на Vercel (`lthub.vercel.app` + `audioservice.vercel.app`), а домены
`*.vercel.app` в России фильтруются. Инструмент поднимает **локальный прокси
sing-box** из обычной VPN-подписки и открывает сайт в браузере, который ходит
только через этот прокси.

Никаких TUN-драйверов и прав администратора: `mixed`-инбаунд на
`127.0.0.1:2080`, который понимает и HTTP, и SOCKS5.

## Установка

```powershell
python -m scripts.lthub_tunnel.tunnel install
```

Скачивает `sing-box` (1.14.2) в `scripts/lthub_tunnel/bin/` (папка в `.gitignore`).

## Источники подписок

Создать `scripts/lthub_tunnel/sources.local.json` (в git не попадает):

```json
{
  "urls": ["https://.../subscription/..."],
  "probe_url": "https://cp.cloudflare.com/generate_204",
  "port": 2080
}
```

Поддерживаются и base64-подписки, и «голый» текст со строками `vless://`.
Можно переопределить из CLI: `--source <url>` (можно дважды).

## Команды

| Команда | Что делает |
|---|---|
| `build` | скачивает подписки, собирает `config.json`, печатает статистику |
| `check` | `build` + вердикт `sing-box check` |
| `up` | поднимает прокси, проверяет сайт, ждёт Enter |
| `up --open` | то же + открывает сайт в Edge с прокси и отдельным профилем |
| `export` | выгружает конфиги для пользователей (sing-box / Clash) |
| `install` | скачать sing-box |

Полезные опции (идут **после** имени команды): `--site`, `--state-dir`,
`--only`, `--limit`, `--log-level`, `--settle`.

## Windows

```powershell
python -m scripts.lthub_tunnel.tunnel up --open
```

Откроется Edge с `--proxy-server=http://127.0.0.1:2080` и отдельным
`--user-data-dir`, так что личные сессии не затрагиваются. Через тот же прокси
автоматически идёт и `audioservice.vercel.app` — отдельные настройки не нужны.

## Если сайт не открылся

1. `python -m scripts.lthub_tunnel.tunnel up` — посмотреть, что пишет.
2. Ноды из бесплатных подписок умирают constantly: перезапустить.
3. Проверить конкретную ноду: `--only n7` (список — в `nodes.tsv` рядом с конфигом).
4. Лог sing-box — в `<state-dir>/sing-box.log`.

`--state-dir` по умолчанию `%LOCALAPPDATA%\lthub-tunnel`.

## Android

Свой APK не нужен — конфиги выгружаются командой:

```powershell
python -m scripts.lthub_tunnel.tunnel export --out dist
```

- `dist/lthub-clash.yaml` — импортируется в Mihomo / Clash Meta GUI и v2rayNG.
- `dist/lthub-sing-box.json` — конфиг для sing-box-android / SagerNet.
- `dist/lthub-nodes.tsv` — список нод, если нужно разбираться руками.

## Как это устроено

1. `subscriptions.py` скачивает подписку, распаковывает base64, режет на
   строки и считает статистику.
2. `nodes.py` превращает каждую строку в outbound sing-box и умеет объяснять,
   почему нода не годится (`xhttp`, reality без `pbk`, грязный `host`).
3. `sbconfig.py` собирает конфиг: `mixed`-inbound + группа `urltest`.
4. **Самочистка**: одна плохая нода рушит весь конфиг sing-box, поэтому
   `prune_config()` по сообщению `sing-box check` выкидывает негодя и повторяет
   проверку, пока конфиг не станет валидным.
5. `tunnel.py up` ждёт первый замер `urltest`, затем открывает сайт через
   прокси с несколькими попытками.

## Ограничения

- **`xhttp` не поддерживается** sing-box 1.14.2 (проверено `sing-box check`),
  такие ноды отбрасываются — обычно это ~10–15% списка.
- **Один битый источник не роняет всю работу:** источники проверяются по очереди,
  недоступные пропускаются с предупреждением. Типичные причины — сертификат
  выдан не на тот хост (`CERTIFICATE_VERIFY_FAILED`) или сервер не отвечает
  по IPv4.
- Свободные ноды живут минутами. Надёжность даёт не конкретная нода, а группа
  `urltest` с переподключением раз в минуту.
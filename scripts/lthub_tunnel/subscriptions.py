"""Загрузка VPN-подписок и их разбор в список нод.

Подписки встречаются в трёх видах:

* base64 от ``vless://...`` строк (классический subscription-ответ);
* «голый» текст со ссылками построчно - так отдают некоторые генераторы
  случайных подписок, вместе с заголовками вида ``#profile-title``;
* base64 cURL-подобными ``clash://`` ссылками (такие пропускаем).

Источники проверяются по очереди и молча пропускаются, если не поднялись:
достаточно одного рабочего. Частые причины: сертификат выдан не на тот хост
(``CERTIFICATE_VERIFY_FAILED``) либо сервер не отвечает по IPv4.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import ssl
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.lthub_tunnel.nodes import Node, parse_trojan, parse_vless

# Подписки отдают разное содержимое в зависимости от User-Agent.
# Первым идёт sing-box: у него самый чистый base64-ответ.
USER_AGENTS = (
    "sing-box",
    "Clash.Meta",
    "v2rayN/6.23.4",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
)
# Подписки живут на Vercel, а он периодически рвёт соединение на холодном
# старте (наблюдалось как WinError 10054 / "connection reset"). Без повторов
# одна такая вспышка молча выкидывала все ~100 нод источника, поэтому
# источник проверяется RETRIES раз, и уже после этого считается мёртвым.
RETRIES = 3
RETRY_PAUSE = 1.5

_LINK_RE = re.compile(r"^\s*(vless|trojan)://\S+", re.I)
# Считаем и чужие схемы (vmess, ss, hy2) - они попадают в «мусор» честно.
_ANY_LINK_RE = re.compile(r"^\s*[a-z][a-z0-9+.\-]*://\S+", re.I)
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/\-_\s]+={0,2}$")


class SubscriptionError(RuntimeError):
    """Подписка недоступна или ответ не похож на список нод."""


def _is_fatal(exc: Exception) -> bool:
    """Ошибки, которые повторами и сменой агента не лечатся.

    Сертификат, выданный не на тот хост, - это не вспышка: пока DNS/сервер
    не починят, повтор вернёт ровно то же самое. Такие случаи надо отсекать
    сразу, иначе мёртвый источник съедает минуты ожидания на ровном месте.
    """
    text = str(exc).lower()
    return "certificate_verify_failed" in text or "certificate verify failed" in text


def fetch(
    url: str,
    timeout: int = 15,
    user_agent: str = USER_AGENTS[0],
    retries: int | None = None,
) -> str:
    """Скачать подписку, повторяя при сетевых сбоях и меняя User-Agent вслепую.

    Повторы и смена User-Agent - разные инструменты, и раньше они были
    склеены в один вложенный цикл во что-то дорогое: 3 попытки × 4 агента ×
    30 секунд = до 6 минут молчаливого ожидания. Разделено так:

    * сетевой сбой (reset, таймаут) лечится повтором того же запроса - менять
      User-Agent после ``WinError 10054`` бессмысленно;
    * смена агента имеет смысл только когда ответ пришёл, но оказался не
      подпиской (некоторые хосты отдают HTML-заглушку вместо конфига);
    * ошибка сертификата - сразу финальная, см. ``_is_fatal``.

    ``retries`` позволяет сузить бюджет: с сохранённой копией на диске
    бессмысленно ждать полного цикла повторов, если сеть легла.
    """
    attempts = RETRIES if retries is None else retries
    last_error: Exception | None = None
    agents = (user_agent,) if user_agent != USER_AGENTS[0] else USER_AGENTS
    for attempt in range(max(1, attempts)):
        for agent in agents:
            request = Request(
                url,
                headers={"User-Agent": agent, "Accept": "*/*", "Accept-Encoding": "identity"},
            )
            try:
                with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
                    text = response.read().decode("utf-8", "replace")
            except (URLError, OSError, ValueError) as exc:
                last_error = exc
                if _is_fatal(exc):
                    raise SubscriptionError(f"{url}: {exc}") from exc
                break
            if "://" in decode_body(text):
                return text
            last_error = SubscriptionError("ответ не похож на подписку")
        if attempt + 1 < RETRIES:
            time.sleep(RETRY_PAUSE * (attempt + 1))
    raise SubscriptionError(f"{url}: {last_error}") from last_error


def decode_body(text: str) -> str:
    """Распаковать base64-тело подписки; «голый» текст вернуть как есть."""
    if _LINK_RE.search(text):
        return text
    compact = "".join(text.split())
    if not compact or not _BASE64_RE.match(compact):
        return text
    padded = compact + "=" * (-len(compact) % 4)
    try:
        decoded = base64.b64decode(padded.replace("-", "+").replace("_", "/")).decode("utf-8", "replace")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return text
    return decoded if "://" in decoded else text


def parse_subscription(text: str) -> tuple[list[Node], dict[str, int]]:
    """Разобрать тело подписки. Возвращает (ноды, счётчики)."""
    nodes: list[Node] = []
    stats = {"total": 0, "parsed": 0, "skipped": 0}
    for line in decode_body(text).splitlines():
        if not _ANY_LINK_RE.match(line):
            continue
        stats["total"] += 1
        uri = line.strip()
        if uri.lower().startswith("vless://"):
            node = parse_vless(uri)
        elif uri.lower().startswith("trojan://"):
            node = parse_trojan(uri)
        else:
            node = None
        if node is None:
            stats["skipped"] += 1
            continue
        node = _with_tag(node, len(nodes))
        nodes.append(node)
        stats["parsed"] += 1
    return nodes, stats


def _with_tag(node: Node, index: int) -> Node:
    """Присвоить уникальный тег: часть подписок дублирует сервер:порт."""
    return replace(node, tag=f"n{index}")


def merge(nodes: Iterable[Node]) -> list[Node]:
    """Свести ноды из нескольких подписок и перенумеровать теги."""
    merged: list[Node] = []
    seen: set[tuple] = set()
    for node in nodes:
        key = (node.protocol, node.server, node.port, node.uuid or node.password, node.short_id)
        if key in seen:
            continue
        seen.add(key)
        merged.append(_with_tag(node, len(merged)))
    return merged


def _cache_file(url: str, cache_dir: str | Path) -> Path:
    """Путь кеша для источника: от URL берём хеш, токен на диск не попадает."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    host = urlsplit(url).netloc or "source"
    safe = re.sub(r"[^a-zA-Z0-9.-]", "_", host)[:40]
    return Path(cache_dir) / f"{safe}-{digest}.txt"


def fetch_cached(url: str, timeout: int = 15, cache_dir: str | Path | None = None) -> tuple[str, bool]:
    """Скачать подписку, при неудаче отдать последнюю удачную из кеша.

    Возвращает (тело, из_кеша). Источники живут на Vercel и периодически
    рвут соединение; без кеша такое молча теряло все ~100 нод разом, и
    приложение оставалось вообще без рабочих вариантов. Кеш - только запасной
    путь: пинг всё равно отсечёт ноды, которые за время простоя умерли.

    Пока есть кеш, бюджет на сеть - одна попытка. Полный цикл повторов
    (до ~48 секунд на источник) имел смысл только когда свежей копии нет:
    иначе мёртвая сеть держала запуск минутами, а в окне при этом не было
    ни одной новой строки.
    """
    if cache_dir is None:
        return fetch(url, timeout=timeout), False
    cache = _cache_file(url, cache_dir)
    cached_exists = cache.exists()
    try:
        body = fetch(url, timeout=timeout, retries=1 if cached_exists else None)
    except SubscriptionError:
        if cached_exists:
            try:
                return cache.read_text(encoding="utf-8"), True
            except OSError:
                pass
        raise
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(body, encoding="utf-8")
    except OSError:
        # Кеш - необязательная роскошь: не смогли записать, не повод падать.
        pass
    return body, False


def load_all(
    urls: Iterable[str],
    timeout: int = 15,
    verbose: bool = True,
    cache_dir: str | Path | None = None,
    log: Callable[[str], None] | None = None,
) -> list[Node]:
    """Скачать все подписки и объединить. Недоступные источники пропускаются.

    Источники независимы, поэтому качаются параллельно: суммарное время -
    это теперь самый долгий из них, а не сумма всех. Прогресс идёт в ``log``
    (его видно в окне) либо в stdout, если лог не передан.
    """
    sources = [url.strip() for url in urls if url and url.strip()]
    if not sources:
        raise SubscriptionError("нет источников подписок")

    def emit(message: str) -> None:
        if log is not None:
            log(message)
        elif verbose:
            print(message)

    def load_one(position: int, url: str) -> list[Node] | SubscriptionError:
        label = f"[{position + 1}/{len(sources)}]"
        emit(f"{label} Скачиваю {url}")
        try:
            body, cached = fetch_cached(url, timeout=timeout, cache_dir=cache_dir)
        except SubscriptionError as exc:
            emit(f"{label} пропущен: {exc}")
            return exc
        parsed, stats = parse_subscription(body)
        mark = " (из кеша)" if cached else ""
        emit(
            f"{label} ok{mark} -> ссылок {stats['total']}, "
            f"разобрано {stats['parsed']}, мусор {stats['skipped']}"
        )
        return parsed

    # Пул не больше числа источников и не раздут: их обычно 2-3.
    with ThreadPoolExecutor(max_workers=min(len(sources), 4)) as pool:
        loaded = list(pool.map(lambda item: load_one(*item), enumerate(sources)))

    nodes: list[Node] = []
    for item in loaded:
        if isinstance(item, list):
            nodes.extend(item)
    merged = merge(nodes)
    if not merged:
        raise SubscriptionError("ни одна подписка не вернула ни одной ноды")
    return merged
"""Runtime updater for AI-lite canon knowledge.

The updater intentionally stays free: it fetches public Google Docs export text
and public Telegram web pages, then stores a compact local cache consumed by the
deterministic AI-lite service.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import aiohttp


CANON_DOC_ID = "1cThh8Yo_y74Zz2MKZHhVgUzfTa8-SO-fuoQvtxLzSl0"
CANON_DOC_URL = f"https://docs.google.com/document/d/{CANON_DOC_ID}/edit?tab=t.0"
CANON_DOC_EXPORT_URL = f"https://docs.google.com/document/d/{CANON_DOC_ID}/export?format=txt"
DEFAULT_CHANNEL_URL = "https://t.me/s/lucasteamgd"
DEFAULT_CACHE_PATH = Path("data/ai_knowledge_cache.json")
LOCAL_CANON_PATH = Path("data/canon_knowledge.txt")

MAX_DYNAMIC_ENTRIES = 40
MAX_ENTRY_TEXT_LENGTH = 1200
MIN_KEYWORD_LENGTH = 4


@dataclass(frozen=True)
class DynamicKnowledgeEntry:
    """Serializable AI-lite knowledge entry loaded from runtime cache."""

    title: str
    keywords: tuple[str, ...]
    answer: str
    source: str
    canon_level: str = "runtime"


@dataclass(frozen=True)
class KnowledgeUpdateResult:
    """Summary returned by an AI knowledge refresh."""

    updated_at: str
    fetched_urls: tuple[str, ...]
    failed_urls: tuple[str, ...]
    entries_count: int
    cache_path: str


async def update_ai_knowledge_cache(
    *,
    cache_path: Path = DEFAULT_CACHE_PATH,
    channel_url: str = DEFAULT_CHANNEL_URL,
) -> KnowledgeUpdateResult:
    """Fetch public canon/channel data and write a compact local AI cache."""

    fetched: list[str] = []
    failed: list[str] = []
    entries: list[DynamicKnowledgeEntry] = []

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        canon_text = await _fetch_text(session, CANON_DOC_EXPORT_URL, fetched, failed)
        channel_text = await _fetch_telegram_text(session, channel_url, fetched, failed)

        if canon_text:
            entries.append(
                _entry_from_text(
                    title="runtime_canon_doc",
                    text=canon_text,
                    source=CANON_DOC_URL,
                    canon_level="main",
                    prefix="📖 Обновлённый канон из Google Doc:",
                )
            )

        if channel_text:
            entries.append(
                _entry_from_text(
                    title="runtime_channel_lucasteamgd",
                    text=channel_text,
                    source=channel_url.replace("/s/", "/"),
                    canon_level="channel",
                    prefix="📣 Новые данные из канала LucasTeam GD:",
                )
            )

        source_urls = _extract_ranked_source_urls(canon_text or "")
        for source_url, level in source_urls[:MAX_DYNAMIC_ENTRIES]:
            text = await _fetch_telegram_text(session, _telegram_web_url(source_url), fetched, failed)
            if not text:
                continue
            entries.append(
                _entry_from_text(
                    title=_title_from_url(source_url),
                    text=text,
                    source=source_url,
                    canon_level=level,
                    prefix=f"{_level_emoji(level)} Источник канона ({level}):",
                )
            )

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "entries": [asdict(entry) for entry in entries if entry.answer.strip()],
        "fetched_urls": fetched,
        "failed_urls": failed,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return KnowledgeUpdateResult(
        updated_at=payload["updated_at"],
        fetched_urls=tuple(fetched),
        failed_urls=tuple(failed),
        entries_count=len(payload["entries"]),
        cache_path=str(cache_path),
    )


def load_local_canon_knowledge(path: Path = LOCAL_CANON_PATH) -> tuple[DynamicKnowledgeEntry, ...]:
    """Parse data/canon_knowledge.txt into structured entries with good keywords.

    Splits by 📖 block headers and by glossary lines so each topic has its own
    searchable entry with full canon text as the answer.
    """

    if not path.exists():
        return ()

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return ()

    blocks = re.split(r"(?=^[📖🔗🧩] )", raw, flags=re.MULTILINE)
    entries: list[DynamicKnowledgeEntry] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        title_match = re.match(r"^[📖🔗🧩]\s*(.+?)$", block, re.MULTILINE)
        block_title = title_match.group(1).strip() if title_match else "unknown"

        cleaned = _compact_text(block)
        if len(cleaned) < 30:
            continue

        if block_title == "unknown":
            continue

        if "ГЛОССАРИЙ" in block_title.upper():
            _add_glossary_terms(cleaned, entries, path)
            continue

        keywords = _keywords_from_text(cleaned, extra=(block_title,))
        entries.append(
            DynamicKnowledgeEntry(
                title=f"local_{block_title}",
                keywords=keywords,
                answer=cleaned,
                source=str(path),
                canon_level="local",
            )
        )

    return tuple(entries)


def _add_glossary_terms(text: str, entries: list[DynamicKnowledgeEntry], path: Path) -> None:
    """Parse glossary lines and add individual term entries."""

    for line in text.split("\n"):
        line = line.strip()
        if not line or " — " not in line:
            continue
        term = line.split(" — ", 1)[0].strip()
        if len(term) < 3:
            continue
        entries.append(
            DynamicKnowledgeEntry(
                title=f"glossary_{term}",
                keywords=_keywords_from_text(term, extra=(term,)),
                answer=line,
                source=str(path),
                canon_level="local_glossary",
            )
        )


def load_dynamic_knowledge(cache_path: Path = DEFAULT_CACHE_PATH) -> tuple[DynamicKnowledgeEntry, ...]:
    """Load runtime AI knowledge entries from cache if it exists."""

    if not cache_path.exists():
        return ()

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()

    entries = []
    for raw_entry in payload.get("entries", []):
        try:
            entries.append(
                DynamicKnowledgeEntry(
                    title=str(raw_entry["title"]),
                    keywords=tuple(str(keyword) for keyword in raw_entry.get("keywords", ())),
                    answer=str(raw_entry["answer"]),
                    source=str(raw_entry.get("source", "runtime cache")),
                    canon_level=str(raw_entry.get("canon_level", "runtime")),
                )
            )
        except (KeyError, TypeError):
            continue
    return tuple(entries)


async def _fetch_text(
    session: aiohttp.ClientSession,
    url: str,
    fetched: list[str],
    failed: list[str],
) -> str:
    try:
        async with session.get(url) as response:
            if response.status >= 400:
                failed.append(url)
                return ""
            fetched.append(url)
            return await response.text()
    except Exception:
        failed.append(url)
        return ""


async def _fetch_telegram_text(
    session: aiohttp.ClientSession,
    url: str,
    fetched: list[str],
    failed: list[str],
) -> str:
    raw_html = await _fetch_text(session, url, fetched, failed)
    return _telegram_html_to_text(raw_html)


def _telegram_html_to_text(raw_html: str) -> str:
    """Extract readable text from public Telegram web HTML."""

    if not raw_html:
        return ""
    matches = re.findall(
        r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>',
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not matches:
        return _clean_html(raw_html)
    return "\n\n".join(_clean_html(match) for match in matches if _clean_html(match))


def _clean_html(raw_html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _extract_ranked_source_urls(canon_text: str) -> list[tuple[str, str]]:
    """Return t.me links near words 'Высокий' or 'Средний' from the canon doc."""

    ranked: list[tuple[str, str]] = []
    seen = set()
    for line in canon_text.splitlines():
        urls = re.findall(r"https?://t\.me/[\w_]+/\d+", line)
        if not urls:
            continue
        normalized_line = line.lower()
        level = ""
        if "высок" in normalized_line:
            level = "Высокий"
        elif "средн" in normalized_line:
            level = "Средний"
        if not level:
            continue
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            ranked.append((url, level))
    return ranked


def _telegram_web_url(url: str) -> str:
    return url.replace("https://t.me/", "https://t.me/s/")


def _title_from_url(url: str) -> str:
    return "runtime_" + re.sub(r"\W+", "_", url.removeprefix("https://")).strip("_")


def _level_emoji(level: str) -> str:
    return "🔵" if level.lower().startswith("выс") else "🟡"


def _entry_from_text(
    *,
    title: str,
    text: str,
    source: str,
    canon_level: str,
    prefix: str,
) -> DynamicKnowledgeEntry:
    cleaned = _compact_text(text)
    excerpt = cleaned[:MAX_ENTRY_TEXT_LENGTH].rstrip()
    answer = f"{prefix}\n{excerpt}\n\nИсточник: {source}"
    return DynamicKnowledgeEntry(
        title=title,
        keywords=tuple(_keywords_from_text(cleaned, extra=(canon_level, source))),
        answer=answer,
        source=source,
        canon_level=canon_level,
    )


def _compact_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\xa0", " ").splitlines()]
    lines = [line for line in lines if line]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _keywords_from_text(text: str, *, extra: Iterable[str] = ()) -> list[str]:
    words = re.findall(r"[a-zа-яё0-9][a-zа-яё0-9_-]+", text.lower())
    stop_words = {
        "https",
        "telegram",
        "канон",
        "источник",
        "который",
        "которая",
        "чтобы",
        "это",
        "для",
        "как",
        "или",
        "что",
        "the",
        "and",
    }
    scored: dict[str, int] = {}
    for word in words:
        if len(word) < MIN_KEYWORD_LENGTH or word in stop_words:
            continue
        scored[word] = scored.get(word, 0) + 1
    for item in extra:
        for word in re.findall(r"[a-zа-яё0-9][a-zа-яё0-9_-]+", item.lower()):
            if len(word) >= MIN_KEYWORD_LENGTH:
                scored[word] = scored.get(word, 0) + 3
    return [word for word, _score in sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:20]]

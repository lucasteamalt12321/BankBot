"""
Канонический модуль хранения канона вселенной Олеговируса и LTL-паразита.

Единый источник правды (source of truth):
- `canon.md` — полный текст канона (версия 2.9, read-only артефакт репозитория).
- `works.py` — перечень канонических произведений (Блок 3.2).
- `glossary.py` — глоссарий и сущности (Блок 4).
- `questions.py` — единый пул вопросов trivia.
- `prayers.py` — единый набор молитв чайной религии.

Модуль намеренно лёгкий (только stdlib + dataclasses, как `core/rates.py`):
никаких structlog/aiohttp — api/index.py (Vercel) импортирует его напрямую.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

CANON_VERSION = "2.9 (12 мая 2026)"
CANON_DOC_ID = "1cThh8Yo_y74Zz2MKZHhVgUzfTa8-SO-fuoQvtxLzSl0"
CANON_DOC_URL = (
    "https://docs.google.com/document/d/"
    "1cThh8Yo_y74Zz2MKZHhVgUzfTa8-SO-fuoQvtxLzSl0/edit?usp=sharing"
)
CANON_DOC_EXPORT_URL = (
    "https://docs.google.com/document/d/"
    "1cThh8Yo_y74Zz2MKZHhVgUzfTa8-SO-fuoQvtxLzSl0/export?format=txt"
)

_CANON_PATH = Path(__file__).parent / "canon.md"
CANON_FILE_PATH = _CANON_PATH

# Запрещённые темы из Блока 1.3 — используются для фильтрации вопросов/поиска.
PROHIBITED_CANON_KEYWORDS = (
    "внешность",
    "цвет волос",
    "лицо",
    "кожа",
    "рост",
    "вес",
    "семья",
    "родител",
    "брат",
    "сестр",
    "диагноз",
    "болезн",
    "эпилеп",
    "аутиз",
)


@dataclass(frozen=True)
class CanonWork:
    """Каноническое произведение из Блока 3.2."""

    title: str
    kind: str  # track | article | archive
    author: str
    date: str
    canon_level: str  # high | medium | low | archive
    url: str = ""


@dataclass(frozen=True)
class CanonTerm:
    """Термин из глоссария канона (Блок 4)."""

    term: str
    definition: str
    source: str = ""


@dataclass(frozen=True)
class CanonEntity:
    """Вымышленная сущность или понятие вселенной."""

    name: str
    description: str
    source: str = ""


def load_canon_text() -> str:
    """Возвращает полный текст канона из canon.md (переживает cold start)."""
    try:
        return _CANON_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def canon_version() -> str:
    """Версия канона из текста (формат: '2.9 (12 мая 2026)')."""
    match = re.search(r"Версия:\s*([^\n]+)", load_canon_text())
    return match.group(1).strip() if match else CANON_VERSION


def _block_heading(text: str, block: str) -> str:
    """Извлекает заголовок блока (📖 БЛОК N. НАЗВАНИЕ)."""
    match = re.search(rf"({block})\s*$", text, re.MULTILINE)
    return match.group(1) if match else block


def canon_sections() -> list[dict]:
    """Возвращает список секций канона для оглавления страницы /canon.

    Каждая секция: {'title': заголовок блока, 'content': текст блока}.
    """
    text = load_canon_text()
    if not text:
        return []

    # Маркеры блоков из канона.
    headings = [
        (m.start(), m.group(0).strip())
        for m in re.finditer(r"^(?:📖 БЛОК|🔗 БЛОК|🧩 БЛОК|📖 .+|🔗 .+|🧩 .+)$", text, re.MULTILINE)
    ]
    sections: list[dict] = []
    for idx, (pos, title) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(text)
        content = text[pos + len(title):end].strip()
        sections.append({"title": title, "content": content})
    return sections


def _normalize(value: str) -> str:
    return value.lower().strip()


def render_markdown(text: str) -> str:
    """Конвертирует markdown канона в HTML (без внешних зависимостей).

    Поддерживает ровно тот поднабор синтаксиса, что используется в canon.md:
    **жирный**, *курсив*, `### заголовки`, `>` блок-цитаты, `-` списки,
    автоссылки `https://...`, горизонтальные линии `---` и параграфы.
    """
    import html as _html
    import re as _re

    def _inline(value: str) -> str:
        value = _html.escape(value)
        value = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
        value = _re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", value)
        value = _re.sub(
            r"(https?://[^\s<]+)",
            r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
            value,
        )
        return value

    lines = text.split("\n")
    html_parts: list[str] = []
    in_list = False
    in_quote = False
    blank = True  # предыдущая строка была пустой (параграф ещё не открыт)

    def _close_block() -> None:
        nonlocal in_list, in_quote, blank
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        if in_quote:
            html_parts.append("</blockquote>")
            in_quote = False
        blank = True

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            _close_block()
            continue

        stripped = line.strip()
        if stripped == "---":
            _close_block()
            html_parts.append("<hr>")
            blank = True
            continue

        heading = _re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            _close_block()
            level = min(len(heading.group(1)), 4)
            html_parts.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            blank = True
            continue

        if stripped.startswith(">"):
            quote_text = stripped.lstrip(">").strip()
            if not in_quote:
                _close_block()
                html_parts.append("<blockquote>")
                in_quote = True
                blank = True
            html_parts.append(_inline(quote_text) + "<br>")
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            item = _inline(stripped[2:].strip())
            if not in_list:
                _close_block()
                html_parts.append("<ul>")
                in_list = True
                blank = True
            html_parts.append(f"<li>{item}</li>")
            continue

        # Обычный параграф (продолжение предыдущей строки).
        if blank:
            html_parts.append("<p>")
            blank = False
        else:
            html_parts.append("<br>")
        html_parts.append(_inline(stripped))

    _close_block()
    return "".join(html_parts)


def find_canon(query: str, limit: int = 5) -> list[dict]:
    """Простой локальный поиск по канону (для /ask_canon fallback).

    Возвращает список совпадений: {'section': заголовок, 'excerpt': фрагмент}.
    """
    q = _normalize(query)
    if not q:
        return []

    results: list[dict] = []
    for section in canon_sections():
        content = section["content"]
        if q in _normalize(content):
            idx = _normalize(content).find(q)
            start = max(0, idx - 120)
            end = min(len(content), idx + len(query) + 180)
            excerpt = content[start:end].strip()
            results.append({"section": section["title"], "excerpt": excerpt})
            if len(results) >= limit:
                break

    if results:
        return results

    # Fallback: поиск по глоссарию.
    for term in get_glossary():
        if q in _normalize(term.term) or q in _normalize(term.definition):
            results.append(
                {"section": "Глоссарий", "excerpt": f"{term.term} — {term.definition}"}
            )
            if len(results) >= limit:
                break

    return results


def get_glossary() -> tuple[CanonTerm, ...]:
    """Глоссарий канона (Блок 4) — отложенный импорт во избежание циклов."""
    from core.canon.glossary import GLOSSARY_TERMS

    return GLOSSARY_TERMS


def get_works() -> tuple[CanonWork, ...]:
    """Перечень канонических произведений (Блок 3.2)."""
    from core.canon.works import CANON_WORKS

    return CANON_WORKS

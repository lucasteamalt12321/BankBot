"""Игровой Universe-модуль: заражение, передача вируса, чай и лечение.

Логика вынесена из ``api/index.py``, чтобы:

* её можно было покрыть тестами без вызова Telegram-вебхука;
* в вебхуке не оставалось SQL с диалектными функциями (``NOW()``,
  ``INTERVAL '1 hour'``) — они не работают на SQLite, который используется
  локально и как фолбэк, если PostgreSQL недоступен.

Все отметки времени считаются в UTC и передаются параметрами, поэтому один
и тот же код одинаково работает на PostgreSQL (прод) и SQLite.

Схема работы с заражённым сообщением:

* бот удаляет исходное сообщение заражённого;
* вместо него публикует ``"Имя:\\n<текст с тиками>"`` — так в чате видно,
  кто именно говорит и что его реплику исказил вирус;
* если кто-то спрашивает, что это такое, бот объясняет, что такое
  олеговирус (или LTL-паразит) и что делать.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

OLEGOVIRUS = "олеговирус"
LTL_PARASITE = "LTL-паразит"

VIRUSES: tuple[str, ...] = (OLEGOVIRUS, LTL_PARASITE)

#: Сколько держится иммунитет после заражения (повторное /infect).
IMMUNITY = timedelta(hours=24)

#: Сколько длится облегчение после /tea.
TEA_RELIEF = timedelta(hours=1)

#: Максимальная длина изменённого сообщения (как было в вебхуке).
MAX_MODIFIED_LEN = 200

EMOJI = {OLEGOVIRUS: "🦠", LTL_PARASITE: "🧬"}

SYMPTOMS = {
    OLEGOVIRUS: (
        "кхм-кхм в каждом предложении",
        "непреодолимое желание писать манифесты",
        "постоянная потребность поправлять других",
    ),
    LTL_PARASITE: (
        "непонятные вспышки смеха",
        "желание пить чай 24/7",
        "странные байты в голове",
    ),
}

#: Вокальные тики олеговируса (канон: «кхм-кхм», «бум-бум», «тыц-тыц»).
TICKS: tuple[str, ...] = ("кхм-кхм", "бум-бум", "тыц-тыц")

#: Веса тиков: «кхм-кхм» — визитная карточка вируса, остальные — редкие.
TICK_WEIGHTS: tuple[float, ...] = (0.6, 0.25, 0.15)

#: Канонические реплики, которые «выдавливает» вирус (встречаются нечасто).
OLEGOVIRUS_TAILS: tuple[str, ...] = (
    "Ты не Олег, ты вирус в зале.",
    "Олеговирус — твой диагноз.",
    "Это не я, это вирус. Кхм-кхм.",
)

#: Вероятность добавить каноническую реплику в конец искажённого сообщения.
TAIL_PROBABILITY = 0.25

#: Сколько часов чат считается «активным» (в нём недавно подменялись сообщения).
CHAT_ACTIVITY_WINDOW = timedelta(hours=3)

#: Человекопонятные алиасы для аргумента /infect.
VIRUS_ALIASES = {
    "олеговирус": OLEGOVIRUS,
    "олег": OLEGOVIRUS,
    "oleg": OLEGOVIRUS,
    "ltl": LTL_PARASITE,
    "ltl-паразит": LTL_PARASITE,
    "ltl паразит": LTL_PARASITE,
    "паразит": LTL_PARASITE,
    "parasite": LTL_PARASITE,
}


@dataclass(frozen=True)
class Infection:
    """Сохранённый статус заражения пользователя."""

    user_id: int
    virus_type: str
    infected_at: datetime | None = None
    tea_until: datetime | None = None


def utcnow() -> datetime:
    """Текущее время в UTC (единственная точка для тестов)."""

    return datetime.now(timezone.utc)


def parse_utc(value) -> datetime | None:
    """Привести значение из БД к timezone-aware UTC.

    PostgreSQL возвращает ``datetime``, SQLite — ISO-строку, поэтому
    полагаться на тип колонки нельзя.
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        raw = value.strip().replace("Z", "+00:00")
        try:
            moment = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def normalize_virus(value: str | None) -> str | None:
    """Разобрать аргумент /infect; неизвестное значение — ``None``."""

    if not value:
        return None
    return VIRUS_ALIASES.get(value.strip().lower())


def random_virus(rng: random.Random | None = None) -> str:
    return (rng or random).choice(VIRUSES)


def emoji_for(virus: str) -> str:
    return EMOJI.get(virus, "🦠")


def symptom_for(virus: str) -> str:
    variants = SYMPTOMS.get(virus) or SYMPTOMS[OLEGOVIRUS]
    return random.choice(variants)


def load_infection(engine, user_id: int) -> Infection | None:
    """Прочитать статус заражения или ``None``."""

    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT user_id, virus_type, infected_at, tea_cooldown_until "
                    "FROM infection_status WHERE user_id = :uid"
                ),
                {"uid": user_id},
            )
            .mappings()
            .first()
        )
    if not row or not row["virus_type"]:
        return None
    return Infection(
        user_id=int(row["user_id"]),
        virus_type=str(row["virus_type"]),
        infected_at=parse_utc(row["infected_at"]),
        tea_until=parse_utc(row["tea_cooldown_until"]),
    )


def infect(
    engine,
    user_id: int,
    *,
    virus: str | None = None,
    now: datetime | None = None,
    only_if_healthy: bool = False,
) -> tuple[str, Infection | None]:
    """Заразить пользователя.

    Возвращает ``(код, статус)``:

    * ``infected`` — заражение создано/обновлено;
    * ``immunity`` — уже заражён меньше 24 часов назад;
    * ``already`` — уже заражён, а ``only_if_healthy`` запрещает перезаражение.
    """

    moment = now or utcnow()
    current = load_infection(engine, user_id)
    if current:
        if only_if_healthy:
            return "already", current
        if current.infected_at and moment - current.infected_at < IMMUNITY:
            return "immunity", current

    chosen = normalize_virus(virus) or random_virus()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO infection_status "
                "(user_id, virus_type, infected_at, tea_cooldown_until) "
                "VALUES (:uid, :virus, :now, NULL) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "virus_type = :virus, infected_at = :now, tea_cooldown_until = NULL"
            ),
            {"uid": user_id, "virus": chosen, "now": moment},
        )
    return "infected", load_infection(engine, user_id)


def spread(
    engine,
    source_id: int,
    target_id: int,
    *,
    now: datetime | None = None,
) -> tuple[str, Infection | None]:
    """Передать вирус от заражённого пользователя другому.

    Коды: ``spread`` / ``not_infected`` (источник здоров) /
    ``target_infected`` (получатель уже заражён — вирус не перезаписываем).
    """

    if source_id == target_id:
        return "not_infected", None
    source = load_infection(engine, source_id)
    if not source:
        return "not_infected", None
    target = load_infection(engine, target_id)
    if target:
        return "target_infected", target

    moment = now or utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO infection_status "
                "(user_id, virus_type, infected_at, tea_cooldown_until) "
                "VALUES (:uid, :virus, :now, NULL) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "virus_type = :virus, infected_at = :now, tea_cooldown_until = NULL"
            ),
            {"uid": target_id, "virus": source.virus_type, "now": moment},
        )
    return "spread", load_infection(engine, target_id)


def cure(engine, user_id: int) -> tuple[str, Infection | None]:
    """Вылечить пользователя. Коды: ``cured`` / ``not_infected``."""

    current = load_infection(engine, user_id)
    if not current:
        return "not_infected", None
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM infection_status WHERE user_id = :uid"),
            {"uid": user_id},
        )
    return "cured", current


def minutes_left(until: datetime, now: datetime) -> int:
    seconds = max(0.0, (until - now).total_seconds())
    return max(1, math.ceil(seconds / 60))


def drink_tea(
    engine,
    user_id: int,
    *,
    now: datetime | None = None,
) -> tuple[str, int, Infection | None]:
    """Выпить чай: облегчение симптомов на час.

    Возвращает ``(код, минут_до_конца_облегчения, статус)``:

    * ``relieved`` — облегчение включено;
    * ``cooldown`` — облегчение ещё действует;
    * ``not_infected`` — пить чай не от чего.
    """

    moment = now or utcnow()
    current = load_infection(engine, user_id)
    if not current:
        return "not_infected", 0, None
    if current.tea_until and current.tea_until > moment:
        return "cooldown", minutes_left(current.tea_until, moment), current

    until = moment + TEA_RELIEF
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE infection_status SET tea_cooldown_until = :until "
                "WHERE user_id = :uid"
            ),
            {"uid": user_id, "until": until},
        )
    return "relieved", minutes_left(until, moment), load_infection(engine, user_id)


def is_symptomatic(infection: Infection | None, now: datetime | None = None) -> bool:
    """Есть ли активные симптомы (чай временно их снимает)."""

    if not infection or not infection.virus_type:
        return False
    if infection.tea_until and infection.tea_until > (now or utcnow()):
        return False
    return True


def _pick_tick(rng: random.Random | None = None) -> str:
    """Выбрать вокальный тик (чаще всего «кхм-кхм»)."""

    return (rng or random).choices(TICKS, weights=TICK_WEIGHTS, k=1)[0]


def modify_text(text: str, virus: str, *, rng: random.Random | None = None) -> str:
    """Исказить сообщение заражённого пользователя.

    Олеговирус вставляет вокальные тики между словами («кхм-кхм», реже
    «бум-бум»/«тыц-тыц») и иногда дописывает каноническую реплику.
    LTL-паразит оставляет чайный след.
    """

    generator = rng or random
    if virus != OLEGOVIRUS:
        return f"{text} ☕"[:MAX_MODIFIED_LEN]

    tick = _pick_tick(generator)
    body = text.replace(" ", f" {tick} ").strip()
    if generator.random() >= TAIL_PROBABILITY:
        return body[:MAX_MODIFIED_LEN]

    tail = generator.choice(OLEGOVIRUS_TAILS)
    body = body[: max(0, MAX_MODIFIED_LEN - len(tail) - 1)].rstrip()
    return f"{body}\n{tail}" if body else tail


def format_infected_message(
    name: str,
    text: str,
    virus: str,
    *,
    rng: random.Random | None = None,
) -> str:
    """Сообщение заражённого в пересказе бота.

    Формат: ``"Имя:\\n<текст оригинала с тиками>"`` — в чате видно, кто
    говорит, а сам текст выдаёт вирус.
    """

    display = (name or "").strip() or "Аноним"
    return f"{display}:\n{modify_text(text, virus, rng=rng)}"


def display_name(user: dict | None) -> str:
    """Имя пользователя из Telegram-апдейта (для подписи сообщения)."""

    if not user:
        return "Аноним"
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    full = " ".join(part for part in (first, last) if part)
    return full or (user.get("username") or "").strip() or "Аноним"


def caption_for(virus: str) -> str:
    """Подпись под подменённым сообщением (plain text, без разметки)."""

    if virus == OLEGOVIRUS:
        return ""
    return "🧬 заражён LTL-паразитом"


# ── Ответ на вопрос «что это такое» ───────────────────────────────────────

OLEGOVIRUS_EXPLAINER = (
    "🦠 Это олеговирус (Olegovirus checkmarevus) — вымышленный пародийный вирус "
    "из вселенной Олеговируса и LTL-паразита.\n\n"
    "• У заражённого в каждую реплику просачиваются тики «кхм-кхм» "
    "(иногда «бум-бум» или «тыц-тыц»), а у окружающих закатываются глаза — "
    "это антиген KHM.\n"
    "• Антиген POST прилипает к чужим текстам и постам: поэтому сообщение "
    "заражённого бот подменяет целиком — на «Имя:» и текст с тиками.\n"
    "• Вирус передаётся через /spread (ответом на сообщение) и при упоминании бота.\n"
    "• У носителя просыпаются личности: Степан, Иван и Олег-диктатор.\n\n"
    "Что делать: /tea — облегчение на час, /cure — полное выздоровление.\n"
    "Подробнее: /ask_canon <вопрос>"
)

LTL_EXPLAINER = (
    "🧬 Это LTL-паразит — вымышленный паразит из вселенной Олеговируса.\n\n"
    "• Заражённого тянет к чаю, и всюду в сообщения просачивается «чай» — "
    "навязчивое чаепитие (СНЧ) и громкостная дисрегуляция (СГД).\n"
    "• Сообщения носителя бот подменяет целиком — на «Имя:» и текст с чайным следом.\n"
    "• Паразит передаётся через /spread (ответом на сообщение) и при упоминании бота.\n\n"
    "Что делать: /tea — облегчение на час, /cure — полное выздоровление.\n"
    "Подробнее: /ask_canon <вопрос>"
)

#: Явные вопросы о вирусе — бот отвечает на них в любом чате.
_STRONG_QUESTION_PATTERNS: tuple[str, ...] = (
    r"кто\s+такой\s+олеговирус",
    r"что\s+так(?:ое|ой|о)\s+олеговирус",
    r"что\s+за\s+олеговирус",
    r"что\s+так(?:ое|ой|о)\s+вирус",
    r"что\s+за\s+вирус",
    r"это\s+что\s+за\s+вирус",
    r"что\s+так(?:ое|ой|о)\s+лтл",
    r"что\s+за\s+лтл",
    r"кто\s+такой\s+лтл",
    r"что\s+так(?:ое|ой|о)\s+паразит",
    r"что\s+так(?:ое|ой|о)\s+заражение",
    r"что\s+за\s+заражение",
    r"что\s+за\s+кхм",
    r"что\s+так(?:ое|ой|о)\s+кхм",
    r"откуда\s+кхм",
    r"почему\s+.*кхм",
    r"почему\s+.*вирус",
    r"почему\s+.*зараж",
    r"кто\s+меня\s+заразил",
    r"кто\s+заразил",
)

#: Общие вопросы вида «что это?» — бот отвечает, только если в чате активен вирус.
_WEAK_QUESTION_PATTERNS: tuple[str, ...] = (
    r"^\s*что\s+это\s*\??\s*$",
    r"^\s*что\s+это\s+такое\s*\??\s*$",
    r"^\s*что\s+за\s+хрень\s*\??\s*$",
    r"^\s*что\s+за\s+фигня\s*\??\s*$",
    r"^\s*что\s+за\s+ерунда\s*\??\s*$",
    r"^\s*кто\s+это\s*\??\s*$",
    r"^\s*это\s+что\s*\??\s*$",
)

#: То же, но в середине фразы — засчитывается только при вопросительном знаке.
_WEAK_QUESTION_PATTERNS_MARKED: tuple[str, ...] = (
    r"\bчто\s+это\b",
    r"\bэто\s+что\b",
    r"\bчто\s+это\s+за\b",
    r"\bчто\s+тут\s+происходит\b",
    r"\bчто\s+творится\b",
)

#: Слова, по которым понятно, что речь именно про вирус.
_VIRUS_CONTEXT_MARKERS: tuple[str, ...] = (
    "вирус",
    "кхм",
    "зараж",
    "олеговирус",
    "паразит",
    "ltl",
    "тик",
    "бум-бум",
    "тыц-тыц",
)


def _normalize_question(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def question_strength(text: str) -> str:
    """Насколько уверенно текст выглядит вопросом про вирус.

    Возвращает ``"strong"`` (явный вопрос о вирусе), ``"weak"`` (общий
    вопрос вроде «что это?» — нужен активный вирус в чате) или ``""``.
    """

    normalized = _normalize_question(text)
    if not normalized:
        return ""

    if any(re.search(pattern, normalized) for pattern in _STRONG_QUESTION_PATTERNS):
        return "strong"

    has_context = any(marker in normalized for marker in _VIRUS_CONTEXT_MARKERS)
    weak_hit = any(
        re.search(pattern, normalized) for pattern in _WEAK_QUESTION_PATTERNS
    )
    marked_hit = any(
        re.search(pattern, normalized) for pattern in _WEAK_QUESTION_PATTERNS_MARKED
    )
    if has_context and (weak_hit or marked_hit):
        # «что это за вирус» — упоминание вируса делает вопрос явным.
        return "strong"
    if weak_hit:
        return "weak"
    if "?" in normalized and marked_hit:
        return "weak"
    return ""


def is_virus_question(text: str, *, active_chat: bool = False) -> bool:
    """Похоже ли сообщение на вопрос о вирусе (для которого нужен ответ)."""

    strength = question_strength(text)
    if strength == "strong":
        return True
    return strength == "weak" and active_chat


def virus_explainer(virus: str | None = None) -> str:
    """Канонический ответ бота на вопрос «что это такое»."""

    if virus == LTL_PARASITE:
        return LTL_EXPLAINER
    return OLEGOVIRUS_EXPLAINER


# ── Активность чата ────────────────────────────────────────────────────────


def mark_chat_activity(
    engine,
    chat_id: int,
    virus: str,
    *,
    now: datetime | None = None,
) -> None:
    """Запомнить, что в чате бот подменял сообщения заражённых."""

    moment = now or utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO virus_chat_activity (chat_id, virus_type, updated_at) "
                "VALUES (:chat, :virus, :now) "
                "ON CONFLICT (chat_id) DO UPDATE SET "
                "virus_type = :virus, updated_at = :now"
            ),
            {"chat": chat_id, "virus": virus, "now": moment},
        )


def chat_activity(
    engine,
    chat_id: int,
    *,
    now: datetime | None = None,
    window: timedelta = CHAT_ACTIVITY_WINDOW,
) -> tuple[str, datetime] | None:
    """Активен ли вирус в чате недавно. Возвращает ``(вирус, время)``."""

    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT virus_type, updated_at FROM virus_chat_activity "
                    "WHERE chat_id = :chat"
                ),
                {"chat": chat_id},
            )
            .mappings()
            .first()
        )
    if not row:
        return None
    updated = parse_utc(row["updated_at"])
    if not updated:
        return None
    moment = now or utcnow()
    if moment - updated > window:
        return None
    virus = str(row["virus_type"] or OLEGOVIRUS)
    return virus, updated


def _plural_ru(value: int, one: str, few: str, many: str) -> str:
    if value % 10 == 1 and value % 100 != 11:
        return one
    if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14:
        return few
    return many


def format_duration(delta: timedelta) -> str:
    """«5 мин.», «2 ч. 10 мин.», «3 дн.» — коротко и по-русски."""

    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return "только что"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} {_plural_ru(minutes, 'минуту', 'минуты', 'минут')}"
    hours, rest_minutes = divmod(minutes, 60)
    if hours < 24:
        base = f"{hours} {_plural_ru(hours, 'час', 'часа', 'часов')}"
        if rest_minutes:
            base += f" {rest_minutes} мин."
        return base
    days, rest_hours = divmod(hours, 24)
    base = f"{days} {_plural_ru(days, 'день', 'дня', 'дней')}"
    if rest_hours:
        base += f" {rest_hours} ч."
    return base


def status_text(infection: Infection | None, now: datetime | None = None) -> str:
    """Карточка статуса для /virus."""

    if not infection:
        return (
            "🦠 Вы не заражены.\n\n"
            "/infect — заразиться (или ответьте /infect на чужое сообщение)\n"
            "/spread — передать свой вирус другому"
        )
    moment = now or utcnow()
    virus = infection.virus_type
    lines = [f"{emoji_for(virus)} Заражение: «{virus}»"]
    if infection.infected_at:
        lines.append(
            f"⏱ Заражён: {format_duration(moment - infection.infected_at)} назад"
        )
    lines.append(f"Симптомы: {symptom_for(virus)}")
    if infection.tea_until and infection.tea_until > moment:
        lines.append(
            f"☕ Чай: облегчение ещё {minutes_left(infection.tea_until, moment)} мин."
        )
    else:
        lines.append("☕ /tea — облегчение симптомов на 1 час")
    lines.append("🩹 /cure — вылечиться · 🦠 /spread — заразить в ответ")
    return "\n".join(lines)


def leaderboard(engine, *, limit: int = 10) -> list[tuple[int, str, datetime | None]]:
    """Топ заражённых (кто дольше всех носит вирус)."""

    safe_limit = max(1, min(int(limit), 50))
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT user_id, virus_type, infected_at FROM infection_status "
                    "WHERE virus_type IS NOT NULL ORDER BY infected_at ASC LIMIT :lim"
                ),
                {"lim": safe_limit},
            )
            .mappings()
            .all()
        )
    return [
        (int(row["user_id"]), str(row["virus_type"]), parse_utc(row["infected_at"]))
        for row in rows
    ]

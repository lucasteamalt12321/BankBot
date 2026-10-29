"""Игровой Universe-модуль: заражение, передача вируса, чай и лечение.

Логика вынесена из ``api/index.py``, чтобы:

* её можно было покрыть тестами без вызова Telegram-вебхука;
* в вебхуке не оставалось SQL с диалектными функциями (``NOW()``,
  ``INTERVAL '1 hour'``) — они не работают на SQLite, который используется
  локально и как фолбэк, если PostgreSQL недоступен.

Все отметки времени считаются в UTC и передаются параметрами, поэтому один
и тот же код одинаково работает на PostgreSQL (прод) и SQLite.
"""

from __future__ import annotations

import math
import random
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


def modify_text(text: str, virus: str) -> str:
    """Исказить сообщение заражённого пользователя."""

    if virus == OLEGOVIRUS:
        modified = text.replace(" ", " кхм-кхм ").strip()
    else:
        modified = f"{text} ☕"
    return modified[:MAX_MODIFIED_LEN]


def caption_for(virus: str) -> str:
    if virus == OLEGOVIRUS:
        return "🦠 _заражён олеговирусом_"
    return "🧬 _заражён LTL-паразитом_"


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
        lines.append(f"⏱ Заражён: {format_duration(moment - infection.infected_at)} назад")
    lines.append(f"Симптомы: {symptom_for(virus)}")
    if infection.tea_until and infection.tea_until > moment:
        lines.append(f"☕ Чай: облегчение ещё {minutes_left(infection.tea_until, moment)} мин.")
    else:
        lines.append("☕ /tea — облегчение симптомов на 1 час")
    lines.append("🩹 /cure — вылечиться · 🦠 /spread — заразить в ответ")
    return "\n".join(lines)


def leaderboard(engine, *, limit: int = 10) -> list[tuple[int, str, datetime | None]]:
    """Топ заражённых (кто дольше всех носит вирус)."""

    safe_limit = max(1, min(int(limit), 50))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT user_id, virus_type, infected_at FROM infection_status "
                "WHERE virus_type IS NOT NULL ORDER BY infected_at ASC LIMIT :lim"
            ),
            {"lim": safe_limit},
        ).mappings().all()
    return [
        (int(row["user_id"]), str(row["virus_type"]), parse_utc(row["infected_at"]))
        for row in rows
    ]

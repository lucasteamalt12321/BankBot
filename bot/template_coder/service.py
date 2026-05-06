"""Parametric service for the dialog template coder.

The service keeps a compact semantic state per chat and derives phrases from
that state. It intentionally avoids pair/triple/four-template lookup tables so
sequences can be extended without combinatorial data growth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

from bot.template_coder.data import (
    AGREEMENT_CODE,
    ALIASES,
    ARRIVAL_CODE,
    BUSY_CODE,
    ENTHUSIASM_CODE,
    GOODBYE_CODE,
    NEGATION_CODE,
    OK_CODE,
    POLITE_REFUSAL_CODE,
    REPEAT_THANKS_CODE,
    TEMPLATES,
    THANKS_CODE,
)

SATURATION_STEPS = 10


@dataclass
class CoderState:
    """Per-chat semantic state for the parameteric template coder."""

    topic: str = "neutral"
    time_minutes: int = 0
    intensity: int = 0
    politeness: int = 0
    confidence: float = 1.0
    repeat_flag: bool = False
    last_template: str | None = None
    history: list[int] = field(default_factory=list)
    steps: int = 0
    updated_at: datetime | None = None

    @property
    def step(self) -> int:
        """Backward-compatible alias for old tests/adapters."""
        return self.steps

    def is_empty(self) -> bool:
        """Return true if no template has been applied yet."""
        return self.steps == 0 and not self.history


class TemplateCoderService:
    """Build state transitions and response text for template coding."""

    state_ttl = timedelta(minutes=30)

    unknown_message = (
        "Не понял. Допустимые шаблоны: ОК, Да, Спасибо, "
        '"Спасибо, нет", Великолепно, Спасибо еще раз, Скоро увидимся, '
        "Скоро буду, Я занят(а), Нет."
    )

    def normalize(self, text: str | None) -> int | None:
        """Normalize user text to a template code."""
        if not text:
            return None

        normalized = text.strip().lower().replace("ё", "е")
        normalized = normalized.replace("“", '"').replace("”", '"')
        normalized = normalized.replace("«", '"').replace("»", '"')
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip(" .!?")
        return ALIASES.get(normalized)

    def is_template_text(self, text: str | None) -> bool:
        """Return true if text is one of known templates/aliases."""
        return self.normalize(text) is not None

    def empty_state(self) -> CoderState:
        """Return a reset state."""
        return CoderState()

    def is_expired(
        self,
        state: CoderState,
        now: datetime | None = None,
    ) -> bool:
        """Return true if an active state exceeded inactivity TTL."""
        if state.is_empty() or state.updated_at is None:
            return False
        current_time = now or datetime.now(UTC)
        updated_at = state.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return current_time - updated_at > self.state_ttl

    def help_text(self) -> str:
        """Return user-facing instructions."""
        return (
            "Диалоговый кодер шаблонов.\n\n"
            "Пришлите любую последовательность шаблонов. После каждого шага я "
            "покажу текущий смысл и все 10 следующих вариантов с preview.\n\n"
            "Шаблоны:\n"
            f"{self.template_list_text()}\n\n"
            "Команды:\n"
            "/coder - открыть этот модуль и сбросить состояние\n"
            "/reset - сбросить текущую последовательность\n"
            "/done - закончить и вывести финальную фразу\n"
            "/help - показать эту инструкцию"
        )

    def start_text(self) -> str:
        """Return start/reset text for the coder."""
        return (
            "Диалоговый кодер шаблонов запущен. Состояние сброшено.\n"
            "Просто напишите первый шаблон, затем уточняйте смысл следующими.\n\n"
            f"Доступные шаблоны:\n{self.template_list_text()}"
        )

    def welcome_hint_text(self) -> str:
        """Return a compact hint appended to the main /start response."""
        return (
            "\n\n[TEMPLATE_CODER] <b>Диалоговый кодер шаблонов:</b>\n"
            "Напишите один из шаблонов текстом: ОК, Да, Спасибо, "
            '"Спасибо, нет", Великолепно, Спасибо еще раз, Скоро увидимся, '
            "Скоро буду, Я занят(а), Нет.\n"
            "Команды: /coder — открыть кодер, /reset — сбросить, "
            "/done — закончить, /help — инструкция."
        )

    def template_list_text(self) -> str:
        """Return canonical template list for commands and errors."""
        return "\n".join(f"{code}. {template}" for code, template in TEMPLATES.items())

    def data_stats(self) -> dict[str, int]:
        """Return compact data sizes for diagnostics."""
        return {
            "templates": len(TEMPLATES),
            "aliases": len(ALIASES),
            "pair_values": 0,
            "triple_values": 0,
        }

    def process(self, text: str, state: CoderState) -> tuple[str, CoderState]:
        """Process a template text and return response plus new state."""
        code = self.normalize(text)
        if code is None:
            return self.unknown_message, state

        new_state = self.clone_state(state)
        self.apply(new_state, code)
        new_state.updated_at = datetime.now(UTC)

        return self.response_text(new_state), new_state

    def done_text(self, state: CoderState) -> str:
        """Return final text for /done without mutating state."""
        if state.is_empty():
            return "Последовательность пуста. Чтобы начать, пришлите первый шаблон."
        return (
            f"Готово! Смысл вашей последовательности: «{self.render(state)}». "
            "Чтобы начать новую, пришлите первый шаблон."
        )

    def display_template(self, code: int) -> str:
        """Return canonical template for display."""
        return TEMPLATES[code]

    def clone_state(self, state: CoderState) -> CoderState:
        """Return a copy safe for previews."""
        return replace(state, history=list(state.history))

    def apply(self, state: CoderState, template_code: int) -> None:
        """Mutably apply a template to the semantic state."""
        if state.is_empty():
            self._initialize_first(state, template_code)
        else:
            self._apply_next(state, template_code)

        state.intensity = max(-2, min(2, state.intensity))
        state.politeness = max(0, min(2, state.politeness))
        state.confidence = max(0.0, min(1.0, state.confidence))
        state.last_template = self.display_template(template_code)
        state.history.append(template_code)
        state.steps += 1

    def render(self, state: CoderState) -> str:
        """Render the current semantic state to a deterministic Russian phrase."""
        if state.topic == "arrival":
            if state.time_minutes == 0:
                return "Я уже здесь"
            base = f"Буду через {self._minutes_text(state.time_minutes)}"
            if state.intensity >= 1:
                base += ", спешу"
            elif state.intensity <= -1:
                base += ", но не спешу"
            if state.confidence < 0.9:
                base = "Возможно, " + base.lower()
            if state.politeness == 1:
                base += ", пожалуйста"
            elif state.politeness >= 2:
                base += ", спасибо за ожидание"
            if state.repeat_flag:
                base += " (повторно)"
            return base

        if state.topic == "thanks":
            base = "Ещё раз спасибо" if state.repeat_flag else "Спасибо"
            if state.intensity >= 2:
                base = "Огромное " + base.lower()
            elif state.intensity >= 1:
                base = "Большое " + base.lower()
            if state.politeness >= 1:
                base += ", очень приятно"
            if state.politeness >= 2:
                base += ", я тронут(а)"
            return base

        if state.topic == "refusal":
            base = "Спасибо, нет" if state.politeness >= 1 else "Нет, спасибо"
            if state.intensity <= -1:
                base += ", категорически"
            if state.intensity <= -2:
                base += " и окончательно"
            return base

        if state.topic in {"agreement", "enthusiasm"}:
            base = "Да"
            if state.intensity == 1:
                base = "Да, конечно"
            elif state.intensity >= 2:
                base = "Да, безусловно"
            if state.politeness >= 1:
                base += ", спасибо"
            return base

        if state.topic == "goodbye":
            base = "До встречи"
            if state.politeness >= 1:
                base = "Спасибо, до встречи"
            if state.intensity >= 1:
                base = "До скорой встречи"
            return base

        if state.topic == "busy":
            if state.intensity <= -1:
                base = f"Я очень занят(а) на {self._minutes_text(state.time_minutes)}"
            else:
                base = f"Я занят(а) на {self._minutes_text(state.time_minutes)}"
            if state.politeness >= 1:
                base += ", спасибо"
            return base

        if state.topic == "negation":
            return "Категорическое нет" if state.intensity <= -2 else "Нет"

        if state.intensity >= 1:
            return "Отлично"
        if state.intensity <= -1:
            return "Не очень"
        return "Всё в порядке"

    def ranked_options(self, state: CoderState) -> list[tuple[int, str, str, bool]]:
        """Return all templates sorted by state-change usefulness."""
        ranked: list[tuple[float, int, str, str, bool]] = []
        for code in TEMPLATES:
            preview_state = self.clone_state(state)
            before = self._state_metric_tuple(preview_state)
            self.apply(preview_state, code)
            after = self._state_metric_tuple(preview_state)
            change = self._change_score(before, after)
            unchanged = change == 0
            usage_bonus = 0.01 * state.history.count(code)
            ranked.append(
                (
                    change + usage_bonus,
                    code,
                    self.display_template(code),
                    self.render(preview_state),
                    unchanged,
                )
            )
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return [(code, template, preview, unchanged) for _, code, template, preview, unchanged in ranked]

    def response_text(self, state: CoderState) -> str:
        """Build full bot response for an updated state."""
        history = " → ".join(self.display_template(code) for code in state.history)
        lines = [
            f"Вы написали: «{history}»",
            f"Текущий смысл: «{self.render(state)}»",
            "",
        ]
        if state.steps >= SATURATION_STEPS:
            lines.append(
                "Вы достигли максимальной глубины уточнений. "
                "Можно нажать /done или /reset."
            )
            lines.append("")

        lines.append(
            "Вы можете прислать один из следующих шаблонов "
            "(наиболее релевантные первыми):"
        )
        for index, (_code, template, preview, unchanged) in enumerate(
            self.ranked_options(state),
            start=1,
        ):
            suffix = " (не изменит смысл)" if unchanged else ""
            lines.append(f"{index}. {template} → «{preview}»{suffix}")

        lines.append("")
        lines.append("Если хотите закончить, нажмите /done.")
        return "\n".join(lines)

    def _initialize_first(self, state: CoderState, template_code: int) -> None:
        state.topic = "neutral"
        state.time_minutes = 0
        state.intensity = 0
        state.politeness = 0
        state.confidence = 1.0
        state.repeat_flag = False

        if template_code == AGREEMENT_CODE:
            state.topic = "agreement"
            state.intensity = 1
        elif template_code == THANKS_CODE:
            state.topic = "thanks"
            state.politeness = 1
        elif template_code == POLITE_REFUSAL_CODE:
            state.topic = "refusal"
            state.intensity = -1
            state.politeness = 1
        elif template_code == ENTHUSIASM_CODE:
            state.topic = "enthusiasm"
            state.intensity = 2
        elif template_code == REPEAT_THANKS_CODE:
            state.topic = "thanks"
            state.politeness = 2
            state.repeat_flag = True
        elif template_code == GOODBYE_CODE:
            state.topic = "goodbye"
        elif template_code == ARRIVAL_CODE:
            state.topic = "arrival"
            state.time_minutes = 5
        elif template_code == BUSY_CODE:
            state.topic = "busy"
            state.time_minutes = 30
            state.intensity = -1
        elif template_code == NEGATION_CODE:
            state.topic = "negation"
            state.intensity = -2

    def _apply_next(self, state: CoderState, template_code: int) -> None:
        if state.topic == "arrival":
            self._apply_arrival(state, template_code)
            return
        if state.topic == "busy":
            self._apply_busy(state, template_code)
            return
        if state.topic == "thanks":
            self._apply_thanks(state, template_code)
            return
        if state.topic in {"agreement", "refusal", "enthusiasm", "negation"}:
            self._apply_agreement_refusal(state, template_code)
            return

        self._apply_global(state, template_code)

    def _apply_global(self, state: CoderState, template_code: int) -> None:
        if template_code == AGREEMENT_CODE:
            state.intensity += 1
            if state.topic in {"neutral", "negation"}:
                state.topic = "agreement"
        elif template_code == NEGATION_CODE:
            state.intensity -= 1
            if state.topic == "agreement":
                state.topic = "refusal"
                state.intensity = -1
            elif state.topic == "neutral":
                state.topic = "negation"
        elif template_code == OK_CODE:
            state.intensity = 0
        elif template_code == THANKS_CODE:
            state.politeness += 1
            if state.topic == "neutral":
                state.topic = "thanks"
        elif template_code == POLITE_REFUSAL_CODE:
            state.topic = "refusal"
            state.intensity -= 1
            state.politeness += 1
        elif template_code == ENTHUSIASM_CODE:
            state.intensity = 2
            if state.topic == "thanks":
                state.politeness += 1
            elif state.topic == "neutral":
                state.topic = "enthusiasm"
        elif template_code == REPEAT_THANKS_CODE:
            state.repeat_flag = True
            state.politeness += 1
            if state.topic == "neutral":
                state.topic = "thanks"
        elif template_code == GOODBYE_CODE:
            state.topic = "goodbye"
            state.time_minutes = 0
        elif template_code == ARRIVAL_CODE:
            state.topic = "arrival"
            state.time_minutes = 5
        elif template_code == BUSY_CODE:
            state.topic = "busy"
            state.time_minutes = 30

    def _apply_arrival(self, state: CoderState, template_code: int) -> None:
        if template_code == OK_CODE:
            state.time_minutes = 5
            state.intensity = 0
        elif template_code == AGREEMENT_CODE:
            state.time_minutes = max(1, state.time_minutes - 5)
            state.intensity += 1
        elif template_code == NEGATION_CODE:
            state.time_minutes += 10
            state.intensity -= 1
        elif template_code == THANKS_CODE:
            state.politeness += 1
        elif template_code == ENTHUSIASM_CODE:
            state.time_minutes = max(1, int(state.time_minutes / 2))
            state.intensity = 2
        elif template_code == POLITE_REFUSAL_CODE:
            state.time_minutes += 20
            state.confidence *= 0.8
            state.intensity -= 1
            state.politeness += 1
        elif template_code == REPEAT_THANKS_CODE:
            state.repeat_flag = True
            state.politeness += 1
        elif template_code == GOODBYE_CODE:
            state.topic = "goodbye"
            state.time_minutes = 0
        elif template_code == ARRIVAL_CODE:
            state.time_minutes = max(1, state.time_minutes - 2)
        elif template_code == BUSY_CODE:
            state.time_minutes += 15
            state.intensity -= 1

    def _apply_busy(self, state: CoderState, template_code: int) -> None:
        if template_code == OK_CODE:
            state.intensity = 0
        elif template_code == AGREEMENT_CODE:
            state.time_minutes = max(5, state.time_minutes - 10)
            state.intensity += 1
        elif template_code == NEGATION_CODE:
            state.time_minutes += 15
            state.intensity -= 1
        elif template_code == THANKS_CODE:
            state.politeness += 1
        elif template_code == ENTHUSIASM_CODE:
            state.intensity = 2
        elif template_code == POLITE_REFUSAL_CODE:
            state.time_minutes += 20
            state.intensity -= 1
            state.politeness += 1
        elif template_code == REPEAT_THANKS_CODE:
            state.repeat_flag = True
            state.politeness += 1
        elif template_code == GOODBYE_CODE:
            state.topic = "goodbye"
            state.time_minutes = 0
        elif template_code == ARRIVAL_CODE:
            state.topic = "arrival"
            state.time_minutes = 5
        elif template_code == BUSY_CODE:
            state.time_minutes += 30
            state.intensity -= 1

    def _apply_thanks(self, state: CoderState, template_code: int) -> None:
        if template_code == NEGATION_CODE:
            state.topic = "refusal"
            state.intensity = -1
            return
        self._apply_global(state, template_code)

    def _apply_agreement_refusal(self, state: CoderState, template_code: int) -> None:
        if template_code == POLITE_REFUSAL_CODE:
            state.topic = "refusal"
            state.intensity = -2
            state.politeness = max(state.politeness, 1)
            return
        self._apply_global(state, template_code)

    def _state_metric_tuple(self, state: CoderState) -> tuple[str, int, int, int, float, bool]:
        return (
            state.topic,
            state.time_minutes,
            state.intensity,
            state.politeness,
            round(state.confidence, 2),
            state.repeat_flag,
        )

    def _change_score(
        self,
        before: tuple[str, int, int, int, float, bool],
        after: tuple[str, int, int, int, float, bool],
    ) -> float:
        score = 0.0
        if before[0] != after[0]:
            score += 20
        score += min(30, abs(after[1] - before[1]))
        score += abs(after[2] - before[2]) * 5
        score += abs(after[3] - before[3]) * 3
        score += abs(after[4] - before[4]) * 10
        if before[5] != after[5]:
            score += 2
        return score

    def _minutes_text(self, minutes: int) -> str:
        minutes = max(0, minutes)
        if minutes % 10 == 1 and minutes % 100 != 11:
            unit = "минуту"
        elif minutes % 10 in {2, 3, 4} and minutes % 100 not in {12, 13, 14}:
            unit = "минуты"
        else:
            unit = "минут"
        return f"{minutes} {unit}"

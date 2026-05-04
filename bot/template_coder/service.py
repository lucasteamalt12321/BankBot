"""Pure service for the dialog template coder."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from bot.template_coder.data import (
    ALIASES,
    PAIR_VALUES,
    SINGLE_VALUES,
    TEMPLATES,
    TRIPLE_VALUES,
    THIRD_STEP_CODES,
    get_triple_value,
)


@dataclass(frozen=True)
class CoderState:
    """Per-chat dialog state."""

    step: int = 0
    a_code: int | None = None
    b_code: int | None = None
    updated_at: datetime | None = None


class TemplateCoderService:
    """Builds state transitions and response text for template coding."""

    state_ttl = timedelta(minutes=30)

    unknown_message = (
        "Не понял. Пришлите один из шаблонов: ОК, Да, Спасибо, "
        '"Спасибо, нет", Великолепно, Спасибо еще раз, Скоро увидимся, '
        "Скоро буду, Я занят(а), Нет."
    )

    third_step_error_prefix = (
        "На третьем шаге разрешены только: ОК, Да, Спасибо, Великолепно, Нет."
    )

    def normalize(self, text: str | None) -> int | None:
        """Normalize user text to a template code."""
        if not text:
            return None

        normalized = text.strip().lower().replace("ё", "е")
        normalized = normalized.replace("“", '"').replace("”", '"')
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
        if state.step == 0 or state.updated_at is None:
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
            "Пришлите первый шаблон, затем второй, затем третий. "
            "На третьем шаге доступны только: ОК, Да, Спасибо, Великолепно, Нет.\n\n"
            "Шаблоны:\n"
            f"{self.template_list_text()}\n\n"
            "Команды:\n"
            "/coder - открыть этот модуль и сбросить состояние\n"
            "/reset - сбросить текущую последовательность\n"
            "/help - показать эту инструкцию"
        )

    def start_text(self) -> str:
        """Return start/reset text for the coder."""
        return (
            "Диалоговый кодер шаблонов запущен. Состояние сброшено.\n"
            "Чтобы начать новую последовательность, просто напишите первый шаблон.\n\n"
            f"Доступные шаблоны:\n{self.template_list_text()}"
        )

    def welcome_hint_text(self) -> str:
        """Return a compact hint appended to the main /start response."""
        return (
            "\n\n[TEMPLATE_CODER] <b>Диалоговый кодер шаблонов:</b>\n"
            "Напишите один из шаблонов текстом: ОК, Да, Спасибо, "
            '"Спасибо, нет", Великолепно, Спасибо еще раз, Скоро увидимся, '
            "Скоро буду, Я занят(а), Нет.\n"
            "Команды: /coder — открыть кодер, /reset — сбросить последовательность, "
            "/help — инструкция."
        )

    def template_list_text(self) -> str:
        """Return canonical template list for commands and errors."""
        return "\n".join(f"{code}. {template}" for code, template in TEMPLATES.items())

    def data_stats(self) -> dict[str, int]:
        """Return data table sizes for diagnostics and tests."""
        return {
            "templates": len(TEMPLATES),
            "single_values": len(SINGLE_VALUES),
            "pair_values": len(PAIR_VALUES),
            "triple_values": len(TRIPLE_VALUES),
        }

    def process(self, text: str, state: CoderState) -> tuple[str, CoderState]:
        """Process a template text and return response plus new state."""
        code = self.normalize(text)
        if code is None:
            return self.unknown_message, state

        if state.step == 0 or state.a_code is None:
            return self._handle_first(code, prefix="")

        if state.step == 1:
            if code == state.a_code:
                response, new_state = self._handle_first(
                    code,
                    prefix="Начинаю новую последовательность. ",
                )
                return response, new_state
            return self._handle_second(state.a_code, code)

        if state.step == 2 and state.a_code is not None and state.b_code is not None:
            if code not in THIRD_STEP_CODES:
                template = self.display_template(code)
                return (
                    f"{self.third_step_error_prefix} Вы написали «{template}». Попробуйте ещё раз.",
                    state,
                )
            return self._handle_third(state.a_code, state.b_code, code)

        return self.unknown_message, self.empty_state()

    def display_template(self, code: int) -> str:
        """Return canonical template for display."""
        return TEMPLATES[code]

    def _active_state(
        self,
        step: int,
        a_code: int,
        b_code: int | None = None,
    ) -> CoderState:
        return CoderState(
            step=step,
            a_code=a_code,
            b_code=b_code,
            updated_at=datetime.now(UTC),
        )

    def _handle_first(self, a_code: int, prefix: str) -> tuple[str, CoderState]:
        template = self.display_template(a_code)
        lines = [
            f"{prefix}Вы написали «{template}», что значит «{SINGLE_VALUES[a_code]}».",
            "Варианты для второго шаблона (любой из 10):",
        ]
        lines.extend(
            f"{self.display_template(b_code)} → «{PAIR_VALUES[(a_code, b_code)]}»"
            for b_code in range(1, 11)
        )
        return "\n".join(lines), self._active_state(step=1, a_code=a_code)

    def _handle_second(self, a_code: int, b_code: int) -> tuple[str, CoderState]:
        a_template = self.display_template(a_code)
        b_template = self.display_template(b_code)
        lines = [
            f"Вы написали «{a_template} → {b_template}», что значит «{PAIR_VALUES[(a_code, b_code)]}».",
            "Теперь вы можете прислать третий шаблон из списка: ОК, Да, Спасибо, Великолепно, Нет.",
            "Варианты:",
        ]
        lines.extend(
            f"{self.display_template(c_code)} → «{get_triple_value(a_code, b_code, c_code)}»"
            for c_code in THIRD_STEP_CODES
        )
        return "\n".join(lines), self._active_state(
            step=2,
            a_code=a_code,
            b_code=b_code,
        )

    def _handle_third(
        self,
        a_code: int,
        b_code: int,
        c_code: int,
    ) -> tuple[str, CoderState]:
        sequence = " → ".join(
            [
                self.display_template(a_code),
                self.display_template(b_code),
                self.display_template(c_code),
            ]
        )
        value = get_triple_value(a_code, b_code, c_code)
        return (
            f"Вы написали «{sequence}», что значит «{value}». Конец последовательности.\n"
            "Чтобы начать новую, просто напишите новый первый шаблон.",
            self.empty_state(),
        )

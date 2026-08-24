"""Русский язык (ОГЭ): правила, тренажёр, чек-листы сочинения."""

from __future__ import annotations

from .rules import (
    ESSAY_CRITERIA,
    RULES,
    RuTask,
    Rule,
    EssayCriterion,
    TASKS,
    rules_by_category,
    task_by_id,
    criterion_by_id,
)

__all__ = [
    "ESSAY_CRITERIA",
    "RULES",
    "RuTask",
    "Rule",
    "EssayCriterion",
    "TASKS",
    "rules_by_category",
    "task_by_id",
    "criterion_by_id",
]

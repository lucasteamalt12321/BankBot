"""Математика (ОГЭ): формулы, задачи, генераторы."""

from __future__ import annotations

from .formulas import (
    Formula,
    Generator,
    GENERATORS,
    MathTask,
    TASKS,
    FORMULAS,
    formulas_by_topic,
    task_by_id,
    generator_by_id,
)

__all__ = [
    "Formula",
    "Generator",
    "GENERATORS",
    "MathTask",
    "TASKS",
    "FORMULAS",
    "formulas_by_topic",
    "task_by_id",
    "generator_by_id",
]

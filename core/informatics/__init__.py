"""Модуль informatics — задачи для подготовки к ОГЭ.

Лёгкий stdlib-пакет (только dataclasses, как `core/history/emperors.py`):
без внешних зависимостей, чтобы api/index.py (Vercel) импортировал его напрямую.

Содержит задачи по всем разделам ОГЭ по информатике:
- math        — математика (теория алгоритмов, числовая арифметика);
- informatics — основы информатики (циклы, условия, строки);
- physics     — физические задачи с расчетами;
- russian     — задачи на логику и русский язык.
"""

from core.informatics.tasks import (
    MATH_TOPICS,
    MathTopic,
    MathTask,
    task_by_id,
    tasks_for_topic,
    get_random_task,
    get_tasks_by_difficulty,
)

__all__ = [
    "MATH_TOPICS",
    "MathTopic",
    "MathTask",
    "task_by_id",
    "tasks_for_topic",
    "get_random_task",
    "get_tasks_by_difficulty",
]
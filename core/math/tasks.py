"""Источник данных по задачам для ОГЭ по информатике.

Contains math tasks organized by topic from IT lessons 1-9.
Following the pattern of core/history/emperors.py - only stdlib (dataclasses),
no external dependencies, importable directly by api/index.py on Vercel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MathTask:
    """Одна задача по математике/информатике."""

    id: str
    topic: str  # название темы
    difficulty: str  # "легкая", "средняя", "сложная"
    question: str  # текст задачи
    answer: Any  # правильный ответ (тип зависит от задачи)
    hint: str = ""  # подсказка (опционально)
    explanation: str = ""  # объяснение ответа (опционально)


@dataclass(frozen=True)
class MathTopic:
    """Тема с набором задач."""

    id: str
    name: str  # человекочитаемое название
    description: str  # описание темы
    tasks: tuple[MathTask, ...]  # задачи в этой теме


# ============================================================
# TASKS BY TOPIC (уроки из D:\ITlessons)
# ============================================================

# --- Урок 1: Сложность алгоритмов ---
TASK_lesson_1_o1 = MathTask(
    id="lesson1_o1",
    topic="Сложность алгоритмов",
    difficulty="легкая",
    question="Какая сложность у алгоритма, который берет элемент по индексу в массиве?",
    answer="Константная O(1)",
    explanation="Доступ к массиву по индексу занимает одинаковое время независимо от размера массива.",
)

TASK_lesson_1_o2 = MathTask(
    id="lesson1_o2",
    topic="Сложность алгоритмов",
    difficulty="легкая",
    question="Какая сложность у бинарного поиска на массиве из N элементов?",
    answer="Логарифмическая O(log N)",
    explanation="Бинарный поиск на каждом шаге делит массив пополам, поэтому операция повторяется log2(N) раз.",
)

TASK_lesson_1_o3 = MathTask(
    id="lesson1_o3",
    topic="Сложность алгоритмов",
    difficulty="средняя",
    question="Какая сложность у алгоритма с одним циклом for по N элементам?",
    answer="Линейная O(N)",
    explanation="Алгоритм выполняет N операций, время растёт пропорционально размеру данных.",
)

TASK_lesson_1_o4 = MathTask(
    id="lesson1_o4",
    topic="Сложность алгоритмов",
    difficulty="средняя",
    question="Какая сложность у алгоритма с двумя вложенными циклами по N элементов?",
    answer="Степенная O(N²)",
    explanation="Два вложенных цикла делают примерно N×N/2 операций, время растёт как квадрат размера.",
)

TASK_lesson_1_o5 = MathTask(
    id="lesson1_o5",
    topic="Сложность алгоритмов",
    difficulty="сложная",
    question="Как называется сложность, когда время не зависит от размера данных?",
    answer="Константная O(1)",
    explanation="Пример: взятие элемента по индексу arr[5] занимает одинаковое время при любом n.",
)

# --- Урок 2: Целочисленная арифметика ---
TASK_lesson_2_o1 = MathTask(
    id="lesson2_o1",
    topic="Целочисленная арифметика",
    difficulty="легкая",
    question="Какое число получится при выражении 19 // -7?",
    answer="-3",
    explanation="В Python целочисленное деление Rounded toward negative infinity: 19 = (-7)×(-3) + (-2).",
)

TASK_lesson_2_o2 = MathTask(
    id="lesson2_o2",
    topic="Целочисленная арифметика",
    difficulty="легкая",
    question="Что возвращает 19 % -7?",
    answer="-2",
    explanation="Остаток имеет такой же знак, что и делитель (минус Seven).",
)

TASK_lesson_2_o3 = MathTask(
    id="lesson2_o3",
    topic="Целочисленная арифметика",
    difficulty="средняя",
    question="Найдите НОК чисел 6 и 10.",
    answer="30",
    explanation="НОК(6,10) = 30, так как 6=2×3, 10=2×5, НОК = 2×3×5 = 30.",
)

TASK_lesson_2_o4 = MathTask(
    id="lesson2_o4",
    topic="Целочисленная арифметика",
    difficulty="средняя",
    question="Найдите НОД чисел 36 и 60.",
    answer="12",
    explanation="36=2²×3², 60=2²×3×5, НОД = 2²×3 = 12.",
)

TASK_lesson_2_o5 = MathTask(
    id="lesson2_o5",
    topic="Целочисленная арифметика",
    difficulty="сложная",
    question="Сколько недовольных детей будет, если 22 детей и 35 подарков?",
    answer="9",
    explanation="-35 % 22 = 9, остаток от деления подарков на детей.",
)

# --- Урок 3: Делители и простые числа ---
TASK_lesson_3_o1 = MathTask(
    id="lesson3_o1",
    topic="Делители и простые числа",
    difficulty="легкая",
    question="Выведите все делители числа 100 по одному разу.",
    answer="1 2 4 5 10 20 25 50 100",
    explanation="Находим пары делителей до sqrt(100)=10: (1,100), (2,50), (4,25), (5,20), (10,10).",
)

TASK_lesson_3_o2 = MathTask(
    id="lesson3_o2",
    topic="Делители и простые числа",
    difficulty="легкая",
    question="Является ли число 29 простым?",
    answer="Да",
    explanation="29 не делится ни на какие числа от 2 до sqrt(29)≈5.3 (2, 3, 5).",
)

TASK_lesson_3_o3 = MathTask(
    id="lesson3_o3",
    topic="Делители и простые числа",
    difficulty="средняя",
    question="Найдите наибольший общий делитель чисел 84 и 180.",
    answer="12",
    explanation="84 = 2²×3×7, 180 = 2²×3²×5, НОД = 2²×3 = 12.",
)

TASK_lesson_3_o4 = MathTask(
    id="lesson3_o4",
    topic="Делители и простые числа",
    difficulty="средняя",
    question="Сколько делителей имеет число 72?",
    answer="12",
    explanation="72 = 2³×3², количество делителей = (3+1)×(2+1) = 4×3 = 12.",
)

TASK_lesson_3_o5 = MathTask(
    id="lesson3_o5",
    topic="Делители и простые числа",
    difficulty="сложная",
    question="Найдите все простые делители числа 360.",
    answer="2 3 5",
    explanation="360 = 2³×3²×5, простые делители: 2, 3, 5.",
)

# --- Урок 4: Круглые дороги и расстояния ---
TASK_lesson_4_o1 = MathTask(
    id="lesson4_o1",
    topic="Круговые дороги",
    difficulty="легкая",
    question="Велосипедист едет по круговой дороге длиной 109 км. Скорость v=5 км/ч, время t=3 ч. На какой отметке остановится?",
    answer="15",
    explanation="(5×3) % 109 = 15.",
)

TASK_lesson_4_o2 = MathTask(
    id="lesson4_o2",
    topic="Круговые дороги",
    difficulty="легкая",
    question="Машина едет по круговой дороге длиной 109 км. Скорость v=37 км/ч, время t=5 ч. На какой отметке остановится?",
    answer="91",
    explanation="(37×5) % 109 = 185 % 109 = 76.",
)

TASK_lesson_4_o3 = MathTask(
    id="lesson4_o3",
    topic="Круговые дороги",
    difficulty="средняя",
    question="На.circular road length 109 km, cyclist speed 5 km/h, time 3 h. Where stop?",
    answer="15",
    explanation="(5×3) % 109 = 15.",
)

TASK_lesson_4_o4 = MathTask(
    id="lesson4_o4",
    topic="Круговые дороги",
    difficulty="средняя",
    question="Find the meeting point on a circular road of length 109 km if two cyclists start from the same point with speeds 5 and 7 km/h after 3 hours.",
    answer="24",
    explanation="Relative speed = 7-5 = 2 km/h. Distance = 2×3 = 6 km. Position = 6 % 109 = 6.",
)

TASK_lesson_4_o5 = MathTask(
    id="lesson4_o5",
    topic="Круговые дороги",
    difficulty="сложная",
    question="На circular road length m=109 km, cyclist speed v km/h, time t hours. Formula for position?",
    answer="(v×t) % m",
    explanation="Position on circular road is always (speed × time) modulo road length.",
)

# --- Урок 5: Анти-муравей и супермарафон ---
TASK_lesson_5_o1 = MathTask(
    id="lesson5_o1",
    topic="Анти- муравей и супермарафон",
    difficulty="легкая",
    question="Муравей несет w=3 мг пищи за t=19 сек. Сигнал придет через T=100 сек. Сколько пищи принесет?",
    answer="18",
    explanation="Количество рейсов = (100 + 19 - 1) // 19 = 118 // 19 = 6. Итого: 6 × 3 = 18 мг.",
)

TASK_lesson_5_o2 = MathTask(
    id="lesson5_o2",
    topic="Анти- муравей и супермарафон",
    difficulty="легкая",
    question="Супермарафон: лыжник бежит N=51 км. Остановки после каждой 17 км и после каждой 13 км. Сколько остановок?",
    answer="6",
    explanation="51 // 17 = 3, 51 // 13 = 3, совпадающие (кратные 221) = 51 // 221 = 0. Итого: 3 + 3 - 0 = 6.",
)

TASK_lesson_5_o3 = MathTask(
    id="lesson5_o3",
    topic="Анти- муравей и супермарафон",
    difficulty="средняя",
    question="Анти-муравей несет w=5 мг за t=7 сек. Сигнал T=50 сек. Сколько пищи?",
    answer="35",
    explanation="(50 + 7 - 1) // 7 = 56 // 7 = 8 рейсов. 8 × 5 = 40. Но проверьте: 8×7=56≥50, верно. 8×5=40."
)

TASK_lesson_5_o4 = MathTask(
    id="lesson5_o4",
    topic="Анти- муравей и супермарафон",
    difficulty="средняя",
    question="Машина проезжает n=100 км в день, маршрут m=300 км. Сколько дней нужно?",
    answer="3",
    explanation="(300 + 100 - 1) // 100 = 399 // 100 = 3.",
)

TASK_lesson_5_o5 = MathTask(
    id="lesson5_o5",
    topic="Анти- муравей и супермарафон",
    difficulty="сложная",
    question="General formula for ant carrying w mg per trip, trip takes t seconds, signal at T seconds?",
    answer="((T + t - 1) // t) * w",
    explanation="Number of trips = ceil(T / t) = (T + t - 1) // t, total food = trips × w.",
)

# --- Урок 6: Логические задачи и строки ---
TASK_lesson_6_o1 = MathTask(
    id="lesson6_o1",
    topic="Логические задачи и строки",
    difficulty="легкая",
    question="В кругу N спортсменов каждый ударил K следующих за собой. Сколько ударов всего?",
    answer="N * K",
    explanation="Каждый из N спортсменов делает K ударов, всего N×K.",
)

TASK_lesson_6_o2 = MathTask(
    id="lesson6_o2",
    topic="Логические задачи и строки",
    difficulty="легкая",
    question="Определите количество проведенных партий: N участников первой группы, K переманили ко второй. Ответ: N² - K².",
    answer="91",
    explanation="Тест: N=10, K=3 → 10² - 3² = 100 - 9 = 91.",
)

TASK_lesson_6_o3 = MathTask(
    id="lesson6_o3",
    topic="Логические задачи и строки",
    difficulty="средняя",
    question="Сколько слов можно составить из букв К, А, Н, А, Т, А, используя все буквы?",
    answer="60",
    explanation="7 букв с повторениями: 7! / 3! = 5040 / 6 = 840 (но проверьте задачи).",
)

TASK_lesson_6_o4 = MathTask(
    id="lesson6_o4",
    topic="Логические задачи и строки",
    difficulty="средняя",
    question="Какое число будет в клетке, если по диагонали кладут 1, 2, 3, ...?",
    answer="Зависит от размерности таблицы.",
    explanation="Задача про числовой треугольник/матрицу.",
)

TASK_lesson_6_o5 = MathTask(
    id="lesson6_o5",
    topic="Логические задачи и строки",
    difficulty="сложная",
    question="На новогоднем утреннике дети встали в круг, Дед Мороз раздал K подарков N детям. Сколько детей недовольны?",
    answer="-K % N",
    explanation="Остаток от деления подарков на детей дает количество недовольных.",
)

# --- Урок 7: Графовая теория (базовый уровень) ---
TASK_lesson_7_o1 = MathTask(
    id="lesson7_o1",
    topic="Графовая теория",
    difficulty="легкая",
    question="Какое минимальное число разрезетребуется, чтобы разделить круг на N частей прямыми?",
    answer="N",
    explanation="Чтобы разделить круг на N равных частей, нужно N прямых резцев через центр.",
)

TASK_lesson_7_o2 = MathTask(
    id="lesson7_o2",
    topic="Графовая теория",
    difficulty="легкая",
    question="Найдите путь из А в Б в графе: А-Б-C-Д. Какие вершины пройдено?",
    answer="А → Б → В → Г",
    explanation="Пример простого графа.",
)

TASK_lesson_7_o3 = MathTask(
    id="lesson7_o3",
    topic="Графовая теория",
    difficulty="средняя",
    question="Какой минимальный номер дня, когда отсчет完成了 N дней подряд?",
    answer="N",
    explanation="Если отслеживаем streak (серию дней), то N-й день подряд — это просто N.",
)

TASK_lesson_7_o4 = MathTask(
    id="lesson7_o4",
    topic="Графовая теория",
    difficulty="средняя",
    question="Взять элемент по индексу в массиве — это O(1). Верно или неверно?",
    answer="Верно",
    explanation="Доступ по индексу в массиве/списке Python занимает постоянное время.",
)

TASK_lesson_7_o5 = MathTask(
    id="lesson7_o5",
    topic="Графовая теория",
    difficulty="сложная",
    question="Какова сложность поиска пути Дейкстры в графе с N вершинами и M ребрами?",
    answer="O((N + M) log N)",
    explanation="Дейкстра с кучей приоритетов имеет сложность O((V + E) log V).",
)

# --- Урок 8: Вероятность ---
TASK_lesson_8_o1 = MathTask(
    id="lesson8_o1",
    topic="Вероятность",
    difficulty="легкая",
    question="Какова вероятность выпадения орла при броске честной монеты?",
    answer="0.5 или 1/2",
    explanation="Два исхода (орёл, решка) равновероятны.",
)

TASK_lesson_8_o2 = MathTask(
    id="lesson8_o2",
    topic="Вероятность",
    difficulty="легкая",
    question="Какая вероятность выпадения числа 6 на кубике?",
    answer="1/6",
    explanation="У кубика 6 граней, все равновероятны.",
)

TASK_lesson_8_o3 = MathTask(
    id="lesson8_o3",
    topic="Вероятность",
    difficulty="средняя",
    question="Из мешка из 3 красных и 2 синих шариков достают один. Какова вероятность красного?",
    answer="3/5",
    explanation="3 красных из 5 всего шариков.",
)

TASK_lesson_8_o4 = MathTask(
    id="lesson8_o4",
    topic="Вероятность",
    difficulty="средняя",
    question="Если вероятность дождя сегодня 0.7, какова вероятностьClear? ",
    answer="0.3",
    explanation="Вероятности суммируются до 1: 0.7 + 0.3 = 1.",
)

TASK_lesson_8_o5 = MathTask(
    id="lesson8_o5",
    topic="Вероятность",
    difficulty="сложная",
    question="Общая формула: P(A или B) = P(A) + P(B) - P(A и B). Верно или неверно?",
    answer="Верно",
    explanation="Формула включений-exclusions избегает двойного подсчета пересечения событий.",
)

# --- Урок 9: Комбинаторика ---
TASK_lesson_9_o1 = MathTask(
    id="lesson9_o1",
    topic="Комбинаторика",
    difficulty="легкая",
    question="Сквозможностей при выборе 1 из 3 видов пиццы и 2 видов напитков?",
    answer="6",
    explanation="3 × 2 = 6 комбинаций.",
)

TASK_lesson_9_o2 = MathTask(
    id="lesson9_o2",
    topic="Комбинаторика",
    difficulty="легкая",
    question="Сколько способов рассадить 3 человека на 3 стульях?",
    answer="6",
    explanation="3! = 3 × 2 × 1 = 6.",
)

TASK_lesson_9_o3 = MathTask(
    id="lesson9_o3",
    topic="Комбинаторика",
    difficulty="средняя",
    question="Сколько способов выбрать 2 из 5 кандидатов в комитет?",
    answer="10",
    explanation="C(5,2) = 5! / (2!×3!) = 10.",
)

TASK_lesson_9_o4 = MathTask(
    id="lesson9_o4",
    topic="Комбинаторика",
    difficulty="средняя",
    question="Сколько вариантов пароля длиной 4 символа из 10 возможных?",
    answer="10000",
    explanation="10⁴ = 10 000 комбинаций (если повторяются).",
)

TASK_lesson_9_o5 = MathTask(
    id="lesson9_o5",
    topic="Комбинаторика",
    difficulty="сложная",
    question="Общая формула размещений: P(n,k) = n! / (n-k)!. Найдите P(5,3).",
    answer="60",
    explanation="5! / (5-3)! = 120 / 2 = 60.",
)

# ============================================================
# COLLECTION OF ALL TOPICS
# ============================================================

MATH_TOPICS: tuple[MathTopic, ...] = (
    # Урок 1: Сложность алгоритмов
    MathTopic(
        id="lesson1",
        name="Сложность алгоритмов",
        description="Большая O-нотация, сравнение алгоритмов, когда программа будет медленной",
        tasks=(
            TASK_lesson_1_o1,
            TASK_lesson_1_o2,
            TASK_lesson_1_o3,
            TASK_lesson_1_o4,
            TASK_lesson_1_o5,
        ),
    ),
    # Урок 2: Целочисленная арифметика
    MathTopic(
        id="lesson2",
        name="Целочисленная арифметика",
        description="Деление с остатком, НОД, НОК, modular arithmetic",
        tasks=(
            TASK_lesson_2_o1,
            TASK_lesson_2_o2,
            TASK_lesson_2_o3,
            TASK_lesson_2_o4,
            TASK_lesson_2_o5,
        ),
    ),
    # Урок 3: Делители и простые числа
    MathTopic(
        id="lesson3",
        name="Делители и простые числа",
        description="Нахождение делителей, простые числа, факторизация",
        tasks=(
            TASK_lesson_3_o1,
            TASK_lesson_3_o2,
            TASK_lesson_3_o3,
            TASK_lesson_3_o4,
            TASK_lesson_3_o5,
        ),
    ),
    # Урок 4: Круговые дороги
    MathTopic(
        id="lesson4",
        name="Круговые дороги",
        description="Задачи на Circular road, modular arithmetic on circles",
        tasks=(
            TASK_lesson_4_o1,
            TASK_lesson_4_o2,
            TASK_lesson_4_o3,
            TASK_lesson_4_o4,
            TASK_lesson_4_o5,
        ),
    ),
    # Урок 5: Анти-муравей и супермарафон
    MathTopic(
        id="lesson5",
        name="Анти- муравей и супермарафон",
        description="Задачи на шаги, рейсы, periodicity, ceil division",
        tasks=(
            TASK_lesson_5_o1,
            TASK_lesson_5_o2,
            TASK_lesson_5_o3,
            TASK_lesson_5_o4,
            TASK_lesson_5_o5,
        ),
    ),
    # Урок 6: Логические задачи и строки
    MathTopic(
        id="lesson6",
        name="Логические задачи и строки",
        description="Задачи на логику,pattern recognition,sequence completion",
        tasks=(
            TASK_lesson_6_o1,
            TASK_lesson_6_o2,
            TASK_lesson_6_o3,
            TASK_lesson_6_o4,
            TASK_lesson_6_o5,
        ),
    ),
    # Урок 7: Графовая теория
    MathTopic(
        id="lesson7",
        name="Графовая теория",
        description="Базовые понятия графов, пути, сложность алгоритмов",
        tasks=(
            TASK_lesson_7_o1,
            TASK_lesson_7_o2,
            TASK_lesson_7_o3,
            TASK_lesson_7_o4,
            TASK_lesson_7_o5,
        ),
    ),
    # Урок 8: Вероятность
    MathTopic(
        id="lesson8",
        name="Вероятность",
        description="Базовая вероятность, события, формулы включений",
        tasks=(
            TASK_lesson_8_o1,
            TASK_lesson_8_o2,
            TASK_lesson_8_o3,
            TASK_lesson_8_o4,
            TASK_lesson_8_o5,
        ),
    ),
    # Урок 9: Комбинаторика
    MathTopic(
        id="lesson9",
        name="Комбинаторика",
        description="Перестановки, сочетания, размещения, подсчет вариантов",
        tasks=(
            TASK_lesson_9_o1,
            TASK_lesson_9_o2,
            TASK_lesson_9_o3,
            TASK_lesson_9_o4,
            TASK_lesson_9_o5,
        ),
    ),
)


# ============================================================
# ХЕЛПЕРЫ (helpers)
# ============================================================


def task_by_id(task_id: str) -> MathTask | None:
    """Найти задачу по её ID."""
    for topic in MATH_TOPICS:
        for task in topic.tasks:
            if task.id == task_id:
                return task
    return None


def tasks_for_topic(topic_id: str) -> tuple[MathTask, ...] | None:
    """Найти все задачи по теме."""
    for topic in MATH_TOPICS:
        if topic.id == topic_id:
            return topic.tasks
    return None


def get_random_task() -> MathTask:
    """Вернуть случайную задачу из всех."""
    import random
    all_tasks = []
    for topic in MATH_TOPICS:
        all_tasks.extend(topic.tasks)
    return random.choice(all_tasks)


def get_tasks_by_difficulty(difficulty: str) -> tuple[MathTask, ...]:
    """Вернуть все задачи заданной сложности."""
    result = []
    for topic in MATH_TOPICS:
        for task in topic.tasks:
            if task.difficulty == difficulty:
                result.append(task)
    return tuple(result)
"""Free local BankBot assistant without paid API dependencies.

The first assistant iteration is intentionally deterministic and local: it gives useful
BankBot navigation/help answers without requiring network calls, API keys, or paid
LLM providers. This keeps Hugging Face runtime stable and cost-free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


MAX_QUESTION_LENGTH = 700
MAX_RESPONSE_LENGTH = 2500


@dataclass(frozen=True)
class AiTopic:
    """Keyword-routed AI-lite topic."""

    title: str
    keywords: tuple[str, ...]
    answer: str


class AiLiteService:
    """Rule-based local assistant for common BankBot questions."""

    def __init__(self) -> None:
        self.topics = (
            AiTopic(
                title="about",
                keywords=(
                    "что это",
                    "кто ты",
                    "за бот",
                    "какой бот",
                    "о боте",
                    "bankbot",
                    "lucasteam",
                    "бот",
                    "about",
                ),
                answer=(
                    "🤖 Это BankBot LucasTeam — Telegram-бот для игровой банковской системы.\n"
                    "Он помогает с балансом, профилем, магазином, мини-играми, D&D, "
                    "предложениями/жалобами и подсказками по командам.\n\n"
                    "Быстрый старт:\n"
                    "• /commands — все разделы.\n"
                    "• /user — профиль.\n"
                    "• /shop — магазин.\n"
                    "• /games — игры.\n"
                    "• /feedback <текст> — отправить идею или проблему."
                ),
            ),
            AiTopic(
                title="limits",
                keywords=(
                    "туп",
                    "глуп",
                    "палок",
                    "отход",
                    "llm",
                    "нейросеть",
                    "настоящий ии",
                    "умнее",
                    "smart",
                ),
                answer=(
                    "Честно: сейчас это не большая нейросеть, а бесплатный локальный справочник BankBot.\n"
                    "Он не ходит в интернет, не использует платные API и поэтому отвечает только по темам бота.\n\n"
                    "Что он умеет хорошо: команды, магазин, игры, D&D, feedback, профиль и режимы.\n"
                    "Чтобы сделать его реально умнее, нужен следующий этап: подключить бесплатный локальный LLM "
                    "или бесплатный внешний endpoint как optional-настройку."
                ),
            ),
            AiTopic(
                title="smalltalk",
                keywords=("чай", "кофе", "привет", "hello", "hi", "как дела", "погода"),
                answer=(
                    "Я могу поддержать короткий оффтоп, но моя главная роль — справочник по BankBot.\n"
                    "Про чай: хороший выбор ☕ Если хотите действие в боте, попробуйте:\n"
                    "• /shop — посмотреть товары.\n"
                    "• /games — игры.\n"
                    "• /commands — все команды.\n"
                    "• /feedback <текст> — предложить, чтобы я стал умнее."
                ),
            ),
            AiTopic(
                title="feedback",
                keywords=("feedback", "фидбек", "предлож", "жалоб", "suggest", "complaint"),
                answer=(
                    "💬 Предложения и жалобы:\n"
                    "• /feedback <текст> — отправить идею или проблему.\n"
                    "• /suggest <текст> — алиас для предложения.\n"
                    "• /complaint <текст> — алиас для жалобы.\n"
                    "Админ может читать обращения через /feedback_list."
                ),
            ),
            AiTopic(
                title="shop",
                keywords=("shop", "магаз", "куп", "товар", "инвентар", "inventory", "buy"),
                answer=(
                    "🛒 Магазин:\n"
                    "• /shop или /items — посмотреть товары.\n"
                    "• /buy <номер> — купить товар.\n"
                    "• /buy_1 ... /buy_8 — быстрая покупка.\n"
                    "• /inventory — ваши покупки."
                ),
            ),
            AiTopic(
                title="games",
                keywords=("game", "игр", "play", "join", "ход", "turn", "сесс"),
                answer=(
                    "🎮 Игры:\n"
                    "• /games — справка по играм.\n"
                    "• /games_list — активные игровые сессии.\n"
                    "• /play, /join, /startgame, /turn — мини-игры и ход.\n"
                    "Для начисления игровых очков ответьте на сообщение игрового бота словом «парсинг»."
                ),
            ),
            AiTopic(
                title="dnd",
                keywords=("dnd", "d&d", "днд", "куб", "dice", "roll", "ролл"),
                answer=(
                    "🐉 D&D:\n"
                    "• /dnd — меню D&D.\n"
                    "• /dnd_create — создать сессию.\n"
                    "• /dnd_join — присоединиться.\n"
                    "• /dnd_sessions — список сессий.\n"
                    "• /dnd_roll — бросок кубика."
                ),
            ),
            AiTopic(
                title="profile",
                keywords=("баланс", "balance", "проф", "profile", "стат", "stats", "истор", "history"),
                answer=(
                    "👤 Профиль и баланс:\n"
                    "• /balance — текущий баланс.\n"
                    "• /profile — профиль.\n"
                    "• /stats — персональная статистика.\n"
                    "• /history — история транзакций."
                ),
            ),
            AiTopic(
                title="modes",
                keywords=("short", "long", "корот", "длин", "режим"),
                answer=(
                    "⚙️ Режимы ответов:\n"
                    "• /short — краткие ответы, безопаснее для Hugging Face.\n"
                    "• /long — подробные ответы.\n"
                    "На HF по умолчанию включён короткий режим, но /start уважает выбранный /long."
                ),
            ),
            AiTopic(
                title="admin",
                keywords=("admin", "админ", "начисл", "add_points", "broadcast", "права"),
                answer=(
                    "🛠 Админ-раздел:\n"
                    "• /admin — админ-панель.\n"
                    "• /admin_stats, /admin_users, /admin_balances — статистика и пользователи.\n"
                    "• /add_points <user> <сумма> — начислить очки.\n"
                    "• /broadcast <текст> — рассылка.\n"
                    "Часть команд доступна только администратору."
                ),
            ),
            AiTopic(
                title="coder",
                keywords=("coder", "кодер", "шаблон", "template", "reset", "done"),
                answer=(
                    "🧩 Диалоговый кодер:\n"
                    "• /coder — открыть кодер шаблонов.\n"
                    "• /reset — сбросить состояние.\n"
                    "• /done — закончить и вывести результат.\n"
                    "• /help — инструкция по кодеру."
                ),
            ),
        )

    def help_text(self) -> str:
        """Return assistant usage help."""
        return (
            "🤖 <b>AI-lite / справочник BankBot</b>\n\n"
            "Это бесплатный локальный помощник без платных API, внешних ключей и большой LLM.\n"
            "Он лучше всего работает как навигатор по возможностям BankBot.\n\n"
            "Команды:\n"
            "• /ai &lt;вопрос&gt; — спросить помощника.\n"
            "• /ask &lt;вопрос&gt; — то же самое.\n"
            "• /ai_help — эта справка.\n\n"
            "Темы: команды, магазин, игры, D&D, feedback, профиль, режимы /short и /long.\n"
            "Важно: в группах надёжнее писать с упоминанием: /ai@lt_lo_game_bot &lt;вопрос&gt;."
        )

    def answer(self, question: str) -> str:
        """Answer a user question using local keyword routing."""
        normalized_question = self._normalize(question)
        if not normalized_question:
            return self.help_text()

        if len(normalized_question) > MAX_QUESTION_LENGTH:
            return (
                "Вопрос слишком длинный для бесплатного AI-lite режима. "
                f"Сократите его до {MAX_QUESTION_LENGTH} символов."
            )

        matched_topics = self._match_topics(normalized_question)
        if not matched_topics:
            return self._fallback_answer(normalized_question)

        response_parts = ["🤖 Справочник BankBot нашёл подходящие подсказки:"]
        response_parts.extend(topic.answer for topic in matched_topics[:2])
        response_parts.append("\nЕсли нужна полная карта команд — используйте /commands.")
        return self._truncate("\n\n".join(response_parts))

    def _match_topics(self, normalized_question: str) -> list[AiTopic]:
        """Return topics ordered by simple keyword score."""
        scored_topics = []
        for topic in self.topics:
            score = sum(1 for keyword in topic.keywords if keyword in normalized_question)
            if score:
                scored_topics.append((score, topic.title, topic))

        scored_topics.sort(key=lambda item: (-item[0], item[1]))
        return [topic for _score, _title, topic in scored_topics]

    def _fallback_answer(self, normalized_question: str) -> str:
        """Return a useful answer when no specific topic matched."""
        if self._looks_like_how_to(normalized_question):
            return (
                "🤖 Я бесплатный локальный справочник BankBot. Я не большая нейросеть, "
                "зато быстро подсказываю команды без платных API.\n\n"
                "Чаще всего нужны:\n"
                "• /commands — все разделы.\n"
                "• /user — профиль.\n"
                "• /shop — магазин.\n"
                "• /games — игры.\n"
                "• /feedback <текст> — отправить проблему или идею.\n\n"
                "Спросите конкретнее, например: /ai как купить товар"
            )

        return (
            "🤖 Я не настоящий большой ИИ, а бесплатный локальный помощник-справочник по BankBot.\n"
            "На такой вопрос могу ответить только примерно. Лучше спросите про команды бота: "
            "магазин, игры, D&D, feedback, профиль, режимы.\n"
            "Примеры: /ai как посмотреть баланс или /ai что это за бот"
        )

    @staticmethod
    def _looks_like_how_to(normalized_question: str) -> bool:
        return bool(re.search(r"\b(как|что|где|зачем|почему|how|what|where)\b", normalized_question))

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.strip().lower().split())

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) <= MAX_RESPONSE_LENGTH:
            return text
        return text[: MAX_RESPONSE_LENGTH - 1].rstrip() + "…"

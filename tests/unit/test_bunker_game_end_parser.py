"""Unit tests for BunkerGameEndParser.

Tests the parsing of BunkerRP game end messages to extract winner names.
"""

import pytest
from decimal import Decimal
from src.parsers import BunkerGameEndParser, ParserError, ParsedBunkerWinners


class TestBunkerGameEndParser:
    """Test suite for BunkerGameEndParser."""

    @pytest.fixture
    def parser(self):
        """Create a BunkerGameEndParser instance."""
        return BunkerGameEndParser()

    def test_parse_single_winner(self, parser):
        """Test parsing a game end message with a single winner."""
        message = """Прошли в бункер:
1. LucasTeam
💼Профессия: Программист
👥Био: Мужчина, 26 лет

Не прошли в бункер:
1. Crazy"""

        result = parser.parse(message)

        assert isinstance(result, ParsedBunkerWinners)
        assert result.game == "Bunker RP"
        assert len(result.winners) == 1
        assert result.winners[0] == "LucasTeam"

    def test_parse_multiple_winners(self, parser):
        """Test parsing a game end message with multiple winners."""
        message = """Прошли в бункер:
1. LucasTeam
💼Профессия: Программист
👥Био: Мужчина, 26 лет, гетеросексуален, стаж работы 1 год

2. .
💼Профессия: Судья
👥Био: Мужчина, 32 года, гомосексуален, стаж работы 14 лет

Не прошли в бункер:
1. Crazy
2. Tidal"""

        result = parser.parse(message)

        assert isinstance(result, ParsedBunkerWinners)
        assert result.game == "Bunker RP"
        assert len(result.winners) == 2
        assert result.winners[0] == "LucasTeam"
        assert result.winners[1] == "."

    def test_parse_real_example_message(self, parser):
        """Test parsing with the real example from the messages_examples file."""
        message = """BunkerRP, [13.02.2026 11:48]
Прошли в бункер:
1. LucasTeam
💼Профессия: Программист
👥Био: Мужчина, 26 лет, гетеросексуален, стаж работы 1 год
❤Здоровье: Паралич ног — Экзоскелет (носит внешний каркас, сильнее обычного человека)
🎣Хобби: Поиск пропавших животных (4 года)
📝Факт: Стал героем популярного мема
🧳Багаж: Витамины и добавки
🃏Карта 1: Замени открытую карту профессии любого игрока на случайную из колоды

2. .
💼Профессия: Судья
👥Био: Мужчина, 32 года, гомосексуален, стаж работы 14 лет
❤Здоровье: Отсутствие пальцев на руках — Кулаки (пальцев нет вообще, может только толкать и бить)
🎣Хобби: Массаж и акупунктура (7 лет)
📝Факт: Обожает запах бензина
🧳Багаж: Надувная кукла
🃏Карта 1: Замени открытую карту здоровья любого игрока на случайную из колоды

BunkerRP, [13.02.2026 11:48]
Не прошли в бункер:
1. Crazy
💼Профессия: Дерматолог
👥Био: Женщина, 33 года, гомосексуальна, стаж работы 3 года
❤Здоровье: Нечувствительность к боли — Безрассудный (прыгает с высоты, не думая о последствиях)
🎣Хобби: Боевые искуства (19 лет)
📝Факт: Перевёл сериал на жестовый язык
🧳Багаж: Полный комплект для рисования
🃏Карта 1: Получи ещё одну карту профессии

2. Tidal
💼Профессия: Кардиолог
👥Био: Женщина, 25 лет, гомосексуальна, стаж работы 4 года
❤Здоровье: Обжорство — Стресс-едок (заедает страх, паникует без еды)
🎣Хобби: Современное искуство (7 лет)
📝Факт: Был уволен за поджог офиса
🧳Багаж: Кукла Вуду
🃏Карта 1: Разыграй карту, только если ты изгнан. Сбрось любую открытую карту бункера"""

        result = parser.parse(message)

        assert isinstance(result, ParsedBunkerWinners)
        assert result.game == "Bunker RP"
        assert len(result.winners) == 2
        assert result.winners[0] == "LucasTeam"
        assert result.winners[1] == "."

    def test_parse_winner_with_spaces_in_name(self, parser):
        """Test parsing winners with spaces in their names."""
        message = """Прошли в бункер:
1. LucasTeam Luke
💼Профессия: Программист

2. Crazy Time
💼Профессия: Судья

Не прошли в бункер:
1. Tidal Wave"""

        result = parser.parse(message)

        assert len(result.winners) == 2
        assert result.winners[0] == "LucasTeam Luke"
        assert result.winners[1] == "Crazy Time"

    def test_parse_stops_at_losers_section(self, parser):
        """Test that parsing stops at 'Не прошли в бункер:' section."""
        message = """Прошли в бункер:
1. Winner1
💼Профессия: Программист

2. Winner2
💼Профессия: Судья

Не прошли в бункер:
1. Loser1
💼Профессия: Дерматолог

2. Loser2
💼Профессия: Кардиолог"""

        result = parser.parse(message)

        # Should only extract winners, not losers
        assert len(result.winners) == 2
        assert "Winner1" in result.winners
        assert "Winner2" in result.winners
        assert "Loser1" not in result.winners
        assert "Loser2" not in result.winners

    def test_parse_ignores_non_numbered_lines(self, parser):
        """Test that parser ignores lines without numbered entries."""
        message = """Прошли в бункер:
1. LucasTeam
💼Профессия: Программист
Some random text without number
Another line
2. Player2
💼Профессия: Судья

Не прошли в бункер:
1. Loser"""

        result = parser.parse(message)

        # Should only extract numbered entries
        assert len(result.winners) == 2
        assert result.winners[0] == "LucasTeam"
        assert result.winners[1] == "Player2"

    def test_parse_error_on_missing_winners_section(self, parser):
        """Test that ParserError is raised when 'Прошли в бункер:' is missing."""
        message = """Не прошли в бункер:
1. Loser1
2. Loser2"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "No winners found" in str(exc_info.value)

    def test_parse_error_on_empty_winners_section(self, parser):
        """Test that ParserError is raised when winners section is empty."""
        message = """Прошли в бункер:

Не прошли в бункер:
1. Loser1"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "No winners found" in str(exc_info.value)

    def test_parse_error_on_no_numbered_entries(self, parser):
        """Test that ParserError is raised when no numbered entries are found."""
        message = """Прошли в бункер:
Some text without numbers
More text
Random content

Не прошли в бункер:
1. Loser1"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "No winners found" in str(exc_info.value)

    def test_parse_handles_empty_message(self, parser):
        """Test that ParserError is raised for empty message."""
        message = ""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "No winners found" in str(exc_info.value)

    def test_parse_handles_whitespace_only_message(self, parser):
        """Test that ParserError is raised for whitespace-only message."""
        message = "   \n\n   \n   "

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "No winners found" in str(exc_info.value)

    def test_parse_winner_with_special_characters(self, parser):
        """Test parsing winners with special characters in names."""
        message = """Прошли в бункер:
1. Player@123
💼Профессия: Программист

2. User_Name!
💼Профессия: Судья

Не прошли в бункер:
1. Loser"""

        result = parser.parse(message)

        assert len(result.winners) == 2
        assert result.winners[0] == "Player@123"
        assert result.winners[1] == "User_Name!"

    def test_parse_without_losers_section(self, parser):
        """Test parsing when there's no 'Не прошли в бункер:' section."""
        message = """Прошли в бункер:
1. Winner1
💼Профессия: Программист

2. Winner2
💼Профессия: Судья"""

        result = parser.parse(message)

        assert len(result.winners) == 2
        assert result.winners[0] == "Winner1"
        assert result.winners[1] == "Winner2"

    def test_parse_extracts_only_player_names(self, parser):
        """Test that parser extracts only player names, not other details."""
        message = """Прошли в бункер:
1. TestPlayer
💼Профессия: Программист
👥Био: Мужчина, 26 лет
❤Здоровье: Здоров
🎣Хобби: Рыбалка
📝Факт: Интересный факт
🧳Багаж: Рюкзак
🃏Карта 1: Карта действия

Не прошли в бункер:
1. Loser"""

        result = parser.parse(message)

        assert len(result.winners) == 1
        assert result.winners[0] == "TestPlayer"
        # Ensure no other details are included
        assert "Программист" not in result.winners[0]
        assert "Мужчина" not in result.winners[0]

    def test_parse_handles_different_number_formats(self, parser):
        """Test parsing with different number formats (1., 2., etc.)."""
        message = """Прошли в бункер:
1. Player1
💼Профессия: Программист

2. Player2
💼Профессия: Судья

3. Player3
💼Профессия: Врач

10. Player10
💼Профессия: Учитель

Не прошли в бункер:
1. Loser"""

        result = parser.parse(message)

        assert len(result.winners) == 4
        assert result.winners[0] == "Player1"
        assert result.winners[1] == "Player2"
        assert result.winners[2] == "Player3"
        assert result.winners[3] == "Player10"

    def test_parse_preserves_winner_order(self, parser):
        """Test that the order of winners is preserved."""
        message = """Прошли в бункер:
1. FirstWinner
💼Профессия: Программист

2. SecondWinner
💼Профессия: Судья

3. ThirdWinner
💼Профессия: Врач

Не прошли в бункер:
1. Loser"""

        result = parser.parse(message)

        assert result.winners[0] == "FirstWinner"
        assert result.winners[1] == "SecondWinner"
        assert result.winners[2] == "ThirdWinner"

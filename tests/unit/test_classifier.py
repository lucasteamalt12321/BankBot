"""
Unit tests for MessageClassifier.

Tests all 10 message type classifications plus UNKNOWN type.
"""

import pytest
from src.classifier import MessageClassifier, MessageType


class TestMessageClassifier:
    """Test suite for MessageClassifier covering all 10 message types."""
    
    @pytest.fixture
    def classifier(self):
        """Create a MessageClassifier instance for testing."""
        return MessageClassifier()
    
    # GD Cards Tests
    
    def test_gdcards_profile_classification(self, classifier):
        """Test classification of GD Cards profile messages."""
        message = """ПРОФИЛЬ LucasTeam
───────────────
ID: 8685 (23.08.2025)
Ник: LucasTeam
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#701)
Орбы: 10 (#342)
Клан: LucasTeamGD (#50)
Титулы: Продвинутый S2
Бейджи: Нет
Любимая карта: Нету
───────────────"""
        
        result = classifier.classify(message)
        assert result == MessageType.GDCARDS_PROFILE
    
    def test_gdcards_accrual_classification(self, classifier):
        """Test classification of GD Cards accrual messages."""
        message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: LucasTeam
───────────────
Карта: "Zodiac"
Описание: Коллаб от Bianox
Категория: Демоны
───────────────
Редкость: Эпическая (21/55) (17.0%) 🟣
Очки: +3
Орбы за дроп: +10
Коллекция: 124/213 карт
───────────────"""
        
        result = classifier.classify(message)
        assert result == MessageType.GDCARDS_ACCRUAL
    
    # Shmalala Fishing Tests
    
    def test_shmalala_fishing_classification(self, classifier):
        """Test classification of Shmalala fishing messages."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: Crazy Time
Опыт: +6 (232 / 64)🔋

Вы ловили взгляд прохожей, а поймали кое-что другое.
На крючке: 🐟 Окунь (0.84 кг)

Погода: ☀️ Ясно
Место: Городское озеро

Монеты: +4 (266)💰
Энергии осталось: 6 ⚡️"""
        
        result = classifier.classify(message)
        assert result == MessageType.SHMALALA_FISHING
    
    def test_shmalala_fishing_top_classification(self, classifier):
        """Test classification of Shmalala fishing top/leaderboard messages."""
        message = """[Самые богатые в этом чате]

Sasha   5009 монет 💰
LucasTeam Luke 3891 монет 💰
Оᅠлег Чекмарев 318 монет 💰
----------
Crazy Time 266 монет 
Roman Khrushchev 213 монет"""
        
        result = classifier.classify(message)
        assert result == MessageType.SHMALALA_FISHING_TOP
    
    # Shmalala Karma Tests
    
    def test_shmalala_karma_classification(self, classifier):
        """Test classification of Shmalala karma messages."""
        message = """Лайк! Вы повысили рейтинг пользователя Никита .
Теперь его рейтинг: 11 ❤️"""
        
        result = classifier.classify(message)
        assert result == MessageType.SHMALALA_KARMA
    
    def test_shmalala_karma_top_classification(self, classifier):
        """Test classification of Shmalala karma top/leaderboard messages."""
        message = """[Самые крутые по Карме в этом чате]

Оᅠлег Чекмарев - 17 кармы ❤️
Никита   - 12 кармы ❤️
Sasha   - 9 кармы ❤️
----------
LucasTeam Luke - 8 кармы"""
        
        result = classifier.classify(message)
        assert result == MessageType.SHMALALA_KARMA_TOP
    
    # True Mafia Tests
    
    def test_truemafia_game_end_classification(self, classifier):
        """Test classification of True Mafia game end messages."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    LucasTeam Luke - 👨🏼 Мирный житель 
    Tidal Wave - 👨🏼 Мирный житель 

Остальные участники: 
    Crazy Time - 👨🏼‍⚕️ Доктор 
    . - 🤵🏻 Дон 

Игра длилась: 2 мин. 35 сек."""
        
        result = classifier.classify(message)
        assert result == MessageType.TRUEMAFIA_GAME_END
    
    def test_truemafia_profile_classification(self, classifier):
        """Test classification of True Mafia profile messages."""
        message = """👤 Tidal Wave

💵 Деньги: 10
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 1"""
        
        result = classifier.classify(message)
        assert result == MessageType.TRUEMAFIA_PROFILE
    
    # BunkerRP Tests
    
    def test_bunkerrp_game_end_classification(self, classifier):
        """Test classification of BunkerRP game end messages."""
        message = """Прошли в бункер:
1. LucasTeam
💼Профессия: Программист
👥Био: Мужчина, 26 лет, гетеросексуален, стаж работы 1 год
❤Здоровье: Паралич ног — Экзоскелет
🎣Хобби: Поиск пропавших животных (4 года)
📝Факт: Стал героем популярного мема
🧳Багаж: Витамины и добавки
🃏Карта 1: Замени открытую карту профессии

2. .
💼Профессия: Судья
👥Био: Мужчина, 32 года, гомосексуален, стаж работы 14 лет"""
        
        result = classifier.classify(message)
        assert result == MessageType.BUNKERRP_GAME_END
    
    def test_bunkerrp_profile_classification(self, classifier):
        """Test classification of BunkerRP profile messages."""
        message = """👤 LucasTeam

💵 Деньги: 300
💎 Кристаллики: 0

Экстры:
🛡 Защита от изгнания: 0
🃏 Вторая карта действий: 0

🎯 Побед: 7 (с финалом: 1)
🎲 Всего игр: 16 (с финалом: 1)"""
        
        result = classifier.classify(message)
        assert result == MessageType.BUNKERRP_PROFILE
    
    # Unknown Message Tests
    
    def test_unknown_message_classification(self, classifier):
        """Test classification of unknown/unrecognized messages."""
        message = "This is just a random message with no game markers."
        
        result = classifier.classify(message)
        assert result == MessageType.UNKNOWN
    
    def test_empty_message_classification(self, classifier):
        """Test classification of empty messages."""
        message = ""
        
        result = classifier.classify(message)
        assert result == MessageType.UNKNOWN
    
    # Edge Cases and Priority Tests
    
    def test_gdcards_profile_requires_both_markers(self, classifier):
        """Test that GD Cards profile requires both ПРОФИЛЬ and Орбы: markers."""
        # Only ПРОФИЛЬ without Орбы:
        message_without_orbs = "ПРОФИЛЬ TestUser\nID: 123"
        result = classifier.classify(message_without_orbs)
        assert result == MessageType.UNKNOWN
        
        # Only Орбы: without ПРОФИЛЬ
        message_without_profile = "Орбы: 100\nSome other text"
        result = classifier.classify(message_without_profile)
        assert result == MessageType.UNKNOWN
    
    def test_truemafia_game_end_requires_both_markers(self, classifier):
        """Test that True Mafia game end requires both markers."""
        # Only "Игра окончена!" without "Победители:"
        message_without_winners = "Игра окончена!\nSome other text"
        result = classifier.classify(message_without_winners)
        assert result == MessageType.UNKNOWN
        
        # Only "Победители:" without "Игра окончена!"
        message_without_game_end = "Победители:\nPlayer1\nPlayer2"
        result = classifier.classify(message_without_game_end)
        assert result == MessageType.UNKNOWN
    
    def test_truemafia_profile_requires_all_three_markers(self, classifier):
        """Test that True Mafia profile requires all three markers."""
        # Missing one marker
        message_missing_marker = """👤 TestUser
💎 Камни: 0
🛡 Защита: 0"""
        result = classifier.classify(message_missing_marker)
        assert result == MessageType.UNKNOWN
    
    def test_bunkerrp_profile_requires_all_three_markers(self, classifier):
        """Test that BunkerRP profile requires all three markers."""
        # Missing one marker
        message_missing_marker = """👤 TestUser
💎 Кристаллики: 0
🛡 Защита: 0"""
        result = classifier.classify(message_missing_marker)
        assert result == MessageType.UNKNOWN
    
    def test_classification_priority_gdcards_profile_over_accrual(self, classifier):
        """Test that GD Cards profile is classified before accrual if both markers present."""
        # This shouldn't happen in practice, but tests priority
        # Profile check comes first in the classifier and requires both ПРОФИЛЬ and Орбы:
        message = """🃏 НОВАЯ КАРТА 🃏
ПРОФИЛЬ TestUser
Орбы: 100"""
        
        result = classifier.classify(message)
        assert result == MessageType.GDCARDS_PROFILE
    
    def test_classification_priority_shmalala_fishing_over_top(self, classifier):
        """Test that Shmalala fishing is classified before fishing top."""
        # This shouldn't happen in practice, but tests priority
        message = """🎣 [Рыбалка] 🎣
[Самые богатые в этом чате]
Монеты: +5"""
        
        result = classifier.classify(message)
        assert result == MessageType.SHMALALA_FISHING
    
    def test_classification_priority_shmalala_karma_over_top(self, classifier):
        """Test that Shmalala karma is classified before karma top."""
        # This shouldn't happen in practice, but tests priority
        message = """Лайк! Вы повысили рейтинг пользователя TestUser.
[Самые крутые по Карме в этом чате]"""
        
        result = classifier.classify(message)
        assert result == MessageType.SHMALALA_KARMA
    
    # Case Sensitivity Tests
    
    def test_case_sensitive_gdcards_profile(self, classifier):
        """Test that GD Cards profile marker is case-sensitive."""
        # Lowercase version should not match
        message = "профиль TestUser\nОрбы: 100"
        result = classifier.classify(message)
        assert result == MessageType.UNKNOWN
    
    def test_case_sensitive_truemafia_game_end(self, classifier):
        """Test that True Mafia game end marker is case-sensitive."""
        # Different case should not match
        message = "игра окончена!\nПобедители:\nPlayer1"
        result = classifier.classify(message)
        assert result == MessageType.UNKNOWN
    
    # Whitespace and Special Character Tests
    
    def test_classification_with_extra_whitespace(self, classifier):
        """Test that classification works with extra whitespace."""
        message = """  🃏 НОВАЯ КАРТА 🃏  
        
        Игрок: TestUser
        Очки: +5"""
        
        result = classifier.classify(message)
        assert result == MessageType.GDCARDS_ACCRUAL
    
    def test_classification_with_unicode_characters(self, classifier):
        """Test that classification works with various Unicode characters."""
        message = """Лайк! Вы повысили рейтинг пользователя Никита .
Теперь его рейтинг: 11 ❤️"""
        
        result = classifier.classify(message)
        assert result == MessageType.SHMALALA_KARMA
    
    # Multiple Message Type Markers (should not happen, but test priority)
    
    def test_multiple_game_markers_respects_priority(self, classifier):
        """Test that when multiple game markers are present, priority is respected."""
        # GD Cards accrual should take priority (appears first in classify method)
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: TestUser
🎣 [Рыбалка] 🎣
Рыбак: TestUser"""
        
        result = classifier.classify(message)
        assert result == MessageType.GDCARDS_ACCRUAL

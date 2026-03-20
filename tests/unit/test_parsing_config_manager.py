"""
Unit тесты для ParsingConfigManager (Task 7.2.3)
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from database.database import ParsingRule
from core.managers.parsing_config_manager import ParsingConfigManager


@pytest.fixture
def mock_session():
    """Создает мок сессии"""
    session = MagicMock()
    session.query = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def manager(mock_session):
    """Создает ParsingConfigManager с мок сессией"""
    return ParsingConfigManager(session=mock_session)


class TestParsingConfigManager:
    """Тесты ParsingConfigManager"""

    def test_get_rule(self, manager, mock_session):
        """Тест: получение правила по имени бота и паттерну"""
        
        # Настраиваем мок
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_rule.bot_name = "test_bot"
        mock_rule.pattern = "test_pattern"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        rule = manager.get_rule("test_bot", "test_pattern")
        
        assert rule is not None
        assert rule.id == 1
        mock_session.query.assert_called()

    def test_get_rule_not_found(self, manager, mock_session):
        """Тест: получение несуществующего правила"""
        
        # Настраиваем мок
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        rule = manager.get_rule("nonexistent", "pattern")
        
        assert rule is None

    def test_get_rule_by_id(self, manager, mock_session):
        """Тест: получение правила по ID"""
        
        # Настраиваем мок
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        rule = manager.get_rule_by_id(1)
        
        assert rule is not None
        assert rule.id == 1

    def test_get_all_rules(self, manager, mock_session):
        """Тест: получение всех активных правил"""
        
        # Настраиваем мок
        mock_rule1 = MagicMock(spec=ParsingRule)
        mock_rule1.id = 1
        mock_rule2 = MagicMock(spec=ParsingRule)
        mock_rule2.id = 2
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_rule1, mock_rule2]
        
        rules = manager.get_all_rules()
        
        assert len(rules) == 2
        assert rules[0].id == 1
        assert rules[1].id == 2

    def test_get_rules_by_bot(self, manager, mock_session):
        """Тест: получение правил для конкретного бота"""
        
        # Настраиваем мок
        mock_rule1 = MagicMock(spec=ParsingRule)
        mock_rule1.id = 1
        mock_rule1.bot_name = "test_bot"
        mock_rule2 = MagicMock(spec=ParsingRule)
        mock_rule2.id = 2
        mock_rule2.bot_name = "other_bot"
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_rule1, mock_rule2]
        
        rules = manager.get_rules_by_bot("test_bot")
        
        assert len(rules) == 1
        assert rules[0].bot_name == "test_bot"

    def test_add_rule(self, manager, mock_session):
        """Тест: добавление нового правила"""
        
        # Настраиваем мок
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        result = manager.add_rule(
            bot_name="test_bot",
            pattern="test_pattern",
            multiplier=Decimal("1.5"),
            currency_type="coins"
        )
        
        assert result is not None
        mock_session.add.assert_called()
        mock_session.commit.assert_called()

    def test_add_rule_duplicate(self, manager, mock_session):
        """Тест: добавление дублирующего правила"""
        
        # Настраиваем мок - правило уже существует
        mock_rule = MagicMock(spec=ParsingRule)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        result = manager.add_rule(
            bot_name="test_bot",
            pattern="test_pattern",
            multiplier=Decimal("1.5"),
            currency_type="coins"
        )
        
        assert result is None
        mock_session.add.assert_not_called()

    def test_update_rule(self, manager, mock_session):
        """Тест: обновление правила"""
        
        # Настраиваем мок
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        result = manager.update_rule(1, multiplier=Decimal("2.0"))
        
        assert result is True
        assert mock_rule.multiplier == Decimal("2.0")
        mock_session.commit.assert_called()

    def test_update_rule_not_found(self, manager, mock_session):
        """Тест: обновление несуществующего правила"""
        
        # Настраиваем мок
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        result = manager.update_rule(999, multiplier=Decimal("2.0"))
        
        assert result is False
        mock_session.commit.assert_not_called()

    def test_delete_rule(self, manager, mock_session):
        """Тест: удаление правила"""
        
        # Настраиваем мок
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        result = manager.delete_rule(1)
        
        assert result is True
        mock_session.delete.assert_called()
        mock_session.commit.assert_called()

    def test_delete_rule_not_found(self, manager, mock_session):
        """Тест: удаление несуществующего правила"""
        
        # Настраиваем мок
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        result = manager.delete_rule(999)
        
        assert result is False
        mock_session.delete.assert_not_called()

    def test_activate_rule(self, manager, mock_session):
        """Тест: активация правила"""
        
        # Настраиваем мок
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_rule.is_active = False
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        result = manager.activate_rule(1)
        
        assert result is True
        assert mock_rule.is_active == True
        mock_session.commit.assert_called()

    def test_deactivate_rule(self, manager, mock_session):
        """Тест: деактивация правила"""
        
        # Настраиваем мок
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_rule.is_active = True
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        result = manager.deactivate_rule(1)
        
        assert result is True
        assert mock_rule.is_active == False
        mock_session.commit.assert_called()

    def test_update_coefficient(self, manager, mock_session):
        """Тест: обновление коэффициента"""
        
        # Настраиваем мок
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_rule.multiplier = Decimal("1.0")
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        result = manager.update_coefficient(1, Decimal("2.5"))
        
        assert result is True
        assert mock_rule.multiplier == Decimal("2.5")
        mock_session.commit.assert_called()

    def test_get_coefficients_by_bot(self, manager, mock_session):
        """Тест: получение коэффициентов для бота"""
        
        # Настраиваем мок
        mock_rule1 = MagicMock(spec=ParsingRule)
        mock_rule1.pattern = "pattern1"
        mock_rule1.multiplier = Decimal("1.5")
        mock_rule1.is_active = True
        mock_rule2 = MagicMock(spec=ParsingRule)
        mock_rule2.pattern = "pattern2"
        mock_rule2.multiplier = Decimal("2.0")
        mock_rule2.is_active = False
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_rule1, mock_rule2]
        
        coefficients = manager.get_coefficients_by_bot("test_bot")
        
        assert len(coefficients) == 1
        assert coefficients["pattern1"] == Decimal("1.5")

    def test_export_rules(self, manager, mock_session):
        """Тест: экспорт правил"""
        
        # Настраиваем мок
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_rule.bot_name = "test_bot"
        mock_rule.pattern = "test_pattern"
        mock_rule.multiplier = Decimal("1.5")
        mock_rule.currency_type = "coins"
        mock_rule.is_active = True
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_rule]
        
        exported = manager.export_rules()
        
        assert len(exported) == 1
        assert exported[0]['bot_name'] == "test_bot"
        assert exported[0]['multiplier'] == 1.5

    def test_import_rules(self, manager, mock_session):
        """Тест: импорт правил"""
        
        # Настраиваем мок
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        rules_data = [
            {
                'bot_name': 'test_bot',
                'pattern': 'test_pattern',
                'multiplier': 1.5,
                'currency_type': 'coins',
                'is_active': True
            }
        ]
        
        imported = manager.import_rules(rules_data)
        
        assert imported == 1
        mock_session.add.assert_called()

    def test_import_rules_overwrite(self, manager, mock_session):
        """Тест: импорт правил с перезаписью"""
        
        # Настраиваем мок - правило уже существует
        mock_rule = MagicMock(spec=ParsingRule)
        mock_rule.id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_rule
        
        rules_data = [
            {
                'bot_name': 'test_bot',
                'pattern': 'test_pattern',
                'multiplier': 2.0,
                'currency_type': 'coins',
                'is_active': True
            }
        ]
        
        imported = manager.import_rules(rules_data, overwrite=True)
        
        assert imported == 1
        mock_session.commit.assert_called()

    def test_import_rules_missing_fields(self, manager, mock_session):
        """Тест: импорт правил с пропущенными полями"""
        
        rules_data = [
            {
                'bot_name': 'test_bot',
                # pattern missing
            }
        ]
        
        imported = manager.import_rules(rules_data)
        
        assert imported == 0
        mock_session.add.assert_not_called()

    def test_context_manager(self, mock_session):
        """Тест: использование контекстного менеджера"""
        
        with ParsingConfigManager(session=mock_session) as manager:
            # Используем менеджер
            pass
        
        # Сессия не должна быть закрыта, так как мы передали свою
        mock_session.close.assert_not_called()

"""Unit tests for the coefficients migration script."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from scripts.migrate_coefficients import (
    load_coefficients_json,
    migrate_coefficients,
    GAME_NAME_MAPPING,
    PARSER_CLASS_MAPPING
)


class TestLoadCoefficientsJson:
    """Tests for load_coefficients_json function."""

    def test_load_valid_json(self, tmp_path):
        """Test loading a valid coefficients.json file."""
        # Create a temporary JSON file
        test_data = {
            "GD Cards": 2,
            "Shmalala": 1
        }
        json_file = tmp_path / "coefficients.json"
        json_file.write_text(json.dumps(test_data))

        # Load and verify
        result = load_coefficients_json(str(json_file))
        assert result == test_data

    def test_load_nonexistent_file(self):
        """Test loading a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_coefficients_json("/nonexistent/path/coefficients.json")

    def test_load_invalid_json(self, tmp_path):
        """Test loading a file with invalid JSON."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            load_coefficients_json(str(json_file))

    def test_load_empty_json(self, tmp_path):
        """Test loading an empty JSON object."""
        json_file = tmp_path / "empty.json"
        json_file.write_text("{}")

        result = load_coefficients_json(str(json_file))
        assert result == {}


class TestGameNameMapping:
    """Tests for game name mapping configuration."""

    def test_all_games_have_mapping(self):
        """Test that all expected games have name mappings."""
        expected_games = ["GD Cards", "Shmalala", "Shmalala Karma", "True Mafia", "Bunker RP"]

        for game in expected_games:
            assert game in GAME_NAME_MAPPING

    def test_mapped_names_are_lowercase(self):
        """Test that all mapped names are lowercase."""
        for mapped_name in GAME_NAME_MAPPING.values():
            assert mapped_name == mapped_name.lower()

    def test_mapped_names_use_underscores(self):
        """Test that multi-word games use underscores."""
        assert GAME_NAME_MAPPING["Shmalala Karma"] == "shmalala_karma"

    def test_all_mapped_games_have_parser(self):
        """Test that all mapped game names have corresponding parser classes."""
        for mapped_name in GAME_NAME_MAPPING.values():
            assert mapped_name in PARSER_CLASS_MAPPING


class TestParserClassMapping:
    """Tests for parser class mapping configuration."""

    def test_parser_classes_follow_naming_convention(self):
        """Test that parser class names follow the naming convention."""
        for game_name, parser_class in PARSER_CLASS_MAPPING.items():
            # Parser class should end with "Parser"
            assert parser_class.endswith("Parser")
            # Parser class should be in PascalCase
            assert parser_class[0].isupper()


class TestMigrateCoefficients:
    """Integration tests for the migrate_coefficients function."""

    @patch('scripts.migrate_coefficients.SessionLocal')
    @patch('scripts.migrate_coefficients.load_coefficients_json')
    def test_migrate_new_rules(self, mock_load_json, mock_session_local):
        """Test migrating coefficients when no rules exist."""
        # Setup mocks
        mock_load_json.return_value = {
            "GD Cards": 2,
            "Shmalala": 1
        }

        mock_session = Mock()
        mock_session_local.return_value = mock_session

        mock_rule1 = Mock(id=1, game_name="gdcards", coefficient=2.0, enabled=True)
        mock_rule2 = Mock(id=2, game_name="shmalala", coefficient=1.0, enabled=True)

        mock_manager = Mock()
        mock_manager.get_rule.return_value = None  # No existing rules
        mock_manager.create_rule.side_effect = [mock_rule1, mock_rule2]
        mock_manager.get_all_rules.return_value = {
            "gdcards": mock_rule1,
            "shmalala": mock_rule2
        }

        with patch('scripts.migrate_coefficients.ParsingConfigManager', return_value=mock_manager):
            result = migrate_coefficients()

        # Verify create_rule was called for each game
        assert mock_manager.create_rule.call_count == 2
        assert result is True

    @patch('scripts.migrate_coefficients.SessionLocal')
    @patch('scripts.migrate_coefficients.load_coefficients_json')
    def test_migrate_existing_rules_no_changes(self, mock_load_json, mock_session_local):
        """Test migrating when rules exist with same coefficients."""
        # Setup mocks
        mock_load_json.return_value = {
            "GD Cards": 2
        }

        mock_session = Mock()
        mock_session_local.return_value = mock_session

        existing_rule = Mock(id=1, coefficient=2.0)
        mock_manager = Mock()
        mock_manager.get_rule.return_value = existing_rule
        mock_manager.get_all_rules.return_value = {"gdcards": existing_rule}

        with patch('scripts.migrate_coefficients.ParsingConfigManager', return_value=mock_manager):
            result = migrate_coefficients()

        # Verify no create or update was called
        mock_manager.create_rule.assert_not_called()
        mock_manager.update_coefficient.assert_not_called()
        assert result is True

    @patch('scripts.migrate_coefficients.SessionLocal')
    @patch('scripts.migrate_coefficients.load_coefficients_json')
    def test_migrate_existing_rules_with_changes(self, mock_load_json, mock_session_local):
        """Test migrating when rules exist with different coefficients."""
        # Setup mocks
        mock_load_json.return_value = {
            "GD Cards": 3  # Different from existing
        }

        mock_session = Mock()
        mock_session_local.return_value = mock_session

        existing_rule = Mock(id=1, coefficient=2.0)
        mock_manager = Mock()
        mock_manager.get_rule.return_value = existing_rule
        mock_manager.get_all_rules.return_value = {"gdcards": existing_rule}

        with patch('scripts.migrate_coefficients.ParsingConfigManager', return_value=mock_manager):
            result = migrate_coefficients()

        # Verify update was called
        mock_manager.update_coefficient.assert_called_once_with("gdcards", 3.0)
        assert result is True

    @patch('scripts.migrate_coefficients.SessionLocal')
    @patch('scripts.migrate_coefficients.load_coefficients_json')
    def test_migrate_handles_file_not_found(self, mock_load_json, mock_session_local):
        """Test migration handles missing coefficients.json gracefully."""
        mock_load_json.side_effect = FileNotFoundError("File not found")

        result = migrate_coefficients()

        assert result is False

    @patch('scripts.migrate_coefficients.SessionLocal')
    @patch('scripts.migrate_coefficients.load_coefficients_json')
    def test_migrate_handles_json_decode_error(self, mock_load_json, mock_session_local):
        """Test migration handles invalid JSON gracefully."""
        mock_load_json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        result = migrate_coefficients()

        assert result is False

    @patch('scripts.migrate_coefficients.SessionLocal')
    @patch('scripts.migrate_coefficients.load_coefficients_json')
    def test_migrate_handles_database_error(self, mock_load_json, mock_session_local):
        """Test migration handles database errors gracefully."""
        mock_load_json.return_value = {"GD Cards": 2}

        mock_session = Mock()
        mock_session_local.return_value = mock_session

        # Simulate database error
        with patch('scripts.migrate_coefficients.BaseRepository', side_effect=Exception("DB Error")):
            result = migrate_coefficients()

        assert result is False

    @patch('scripts.migrate_coefficients.SessionLocal')
    @patch('scripts.migrate_coefficients.load_coefficients_json')
    def test_migrate_closes_session(self, mock_load_json, mock_session_local):
        """Test that database session is always closed."""
        mock_load_json.return_value = {"GD Cards": 2}

        mock_session = Mock()
        mock_session_local.return_value = mock_session

        mock_manager = Mock()
        mock_manager.get_rule.return_value = None
        mock_manager.create_rule.return_value = Mock(id=1)

        with patch('scripts.migrate_coefficients.ParsingConfigManager', return_value=mock_manager):
            migrate_coefficients()

        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch('scripts.migrate_coefficients.SessionLocal')
    @patch('scripts.migrate_coefficients.load_coefficients_json')
    def test_migrate_partial_failure(self, mock_load_json, mock_session_local):
        """Test migration continues after individual game errors."""
        mock_load_json.return_value = {
            "GD Cards": 2,
            "Shmalala": 1
        }

        mock_session = Mock()
        mock_session_local.return_value = mock_session

        mock_manager = Mock()
        # First call raises error, second succeeds
        mock_manager.get_rule.side_effect = [Exception("DB Error"), None]
        mock_manager.create_rule.return_value = Mock(id=2)
        mock_manager.get_all_rules.return_value = {}

        with patch('scripts.migrate_coefficients.ParsingConfigManager', return_value=mock_manager):
            result = migrate_coefficients()

        # Should complete but report errors
        assert result is False  # Because there was at least one error
        # Second game should still be processed
        mock_manager.create_rule.assert_called_once()


class TestMigrationScriptIntegration:
    """Integration tests using real database (if available)."""

    @pytest.mark.integration
    def test_full_migration_flow(self, tmp_path):
        """Test complete migration flow with temporary database."""
        # This test would require setting up a temporary database
        # and is marked as integration test
        pytest.skip("Integration test - requires database setup")

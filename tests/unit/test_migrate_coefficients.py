"""Unit tests for the coefficients migration script.

The migration script exposes:
- ``load_coefficients_from_file`` - safe JSON loader (returns ``{}`` on errors)
- ``migrate_coefficients`` - applies coefficients to the DB, returns a stats dict
- ``DEFAULT_COEFFICIENTS`` - fallback mapping used when no file is present
"""

import json
import pytest
from pathlib import Path
from decimal import Decimal
from unittest.mock import Mock, patch

from scripts.migrate_coefficients import (
    load_coefficients_from_file,
    migrate_coefficients,
    DEFAULT_COEFFICIENTS,
)


class TestLoadCoefficientsFromFile:
    """Tests for load_coefficients_from_file function."""

    def test_load_valid_json(self, tmp_path):
        """Test loading a valid coefficients.json file."""
        test_data = {"gdcards": {"coefficient": 2}, "shmalala": {"coefficient": 1}}
        json_file = tmp_path / "coefficients.json"
        json_file.write_text(json.dumps(test_data))

        result = load_coefficients_from_file(Path(json_file))
        assert result == test_data

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading a file that doesn't exist returns empty dict."""
        missing = tmp_path / "does_not_exist.json"
        result = load_coefficients_from_file(missing)
        assert result == {}

    def test_load_invalid_json(self, tmp_path):
        """Test loading a file with invalid JSON returns empty dict."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{ invalid json }")

        result = load_coefficients_from_file(Path(json_file))
        assert result == {}

    def test_load_empty_json(self, tmp_path):
        """Test loading an empty JSON object."""
        json_file = tmp_path / "empty.json"
        json_file.write_text("{}")

        result = load_coefficients_from_file(Path(json_file))
        assert result == {}


class TestDefaultCoefficients:
    """Tests for the default coefficients configuration."""

    def test_expected_games_present(self):
        """Test that all expected games have coefficient configs."""
        expected_games = ["gdcards", "shmalala", "truemafia", "bunkerrp"]
        for game in expected_games:
            assert game in DEFAULT_COEFFICIENTS

    def test_coefficients_are_decimal(self):
        """Test that all coefficients are Decimal values."""
        for config in DEFAULT_COEFFICIENTS.values():
            assert isinstance(config["coefficient"], Decimal)

    def test_currency_type_is_defined(self):
        """Test that each config defines a currency type."""
        for config in DEFAULT_COEFFICIENTS.values():
            assert "currency_type" in config


class TestMigrateCoefficients:
    """Tests for the migrate_coefficients function."""

    def _fake_get_db(self, mock_db):
        def _gen():
            yield mock_db
        return _gen

    @patch('scripts.migrate_coefficients.load_coefficients_from_file')
    @patch('scripts.migrate_coefficients.get_db')
    def test_migrate_creates_new_rules(self, mock_get_db, mock_load):
        """Test migrating coefficients when no rules exist."""
        mock_load.return_value = {
            "gdcards": {"pattern": ".*", "coefficient": 2, "currency_type": "coins"},
            "shmalala": {"pattern": ".*", "coefficient": 1, "currency_type": "coins"},
        }
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.side_effect = self._fake_get_db(mock_db)

        stats = migrate_coefficients()

        assert stats["total"] == 2
        assert stats["created"] == 2
        assert stats["errors"] == 0
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()

    @patch('scripts.migrate_coefficients.load_coefficients_from_file')
    @patch('scripts.migrate_coefficients.get_db')
    def test_migrate_skips_existing_rules(self, mock_get_db, mock_load):
        """Test migrating when rules already exist (no force)."""
        mock_load.return_value = {"gdcards": {"pattern": ".*", "coefficient": 2}}
        existing = Mock()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        mock_get_db.side_effect = self._fake_get_db(mock_db)

        stats = migrate_coefficients()

        assert stats["created"] == 0
        assert stats["skipped"] == 1
        assert stats["errors"] == 0
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()

    @patch('scripts.migrate_coefficients.load_coefficients_from_file')
    @patch('scripts.migrate_coefficients.get_db')
    def test_migrate_force_updates_existing(self, mock_get_db, mock_load):
        """Test migrating with force updates existing rules."""
        mock_load.return_value = {"gdcards": {"pattern": ".*", "coefficient": 3}}
        existing = Mock()
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        mock_get_db.side_effect = self._fake_get_db(mock_db)

        stats = migrate_coefficients(force=True)

        assert stats["updated"] == 1
        assert stats["created"] == 0
        assert existing.multiplier == Decimal("3")
        mock_db.commit.assert_called_once()

    @patch('scripts.migrate_coefficients.load_coefficients_from_file')
    @patch('scripts.migrate_coefficients.get_db')
    def test_migrate_dry_run_rolls_back(self, mock_get_db, mock_load):
        """Test dry run does not commit and rolls back."""
        mock_load.return_value = {"gdcards": {"pattern": ".*", "coefficient": 2}}
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.side_effect = self._fake_get_db(mock_db)

        stats = migrate_coefficients(dry_run=True)

        assert stats["created"] == 1
        mock_db.commit.assert_not_called()
        mock_db.rollback.assert_called_once()

    @patch('scripts.migrate_coefficients.load_coefficients_from_file')
    @patch('scripts.migrate_coefficients.get_db')
    def test_migrate_handles_database_error(self, mock_get_db, mock_load):
        """Test migration handles database errors gracefully."""
        mock_load.return_value = {"gdcards": {"pattern": ".*", "coefficient": 2}}
        mock_db = Mock()
        mock_db.query.side_effect = Exception("DB Error")
        mock_get_db.side_effect = self._fake_get_db(mock_db)

        stats = migrate_coefficients()

        assert stats["errors"] == 1
        mock_db.rollback.assert_called_once()

    @patch('scripts.migrate_coefficients.load_coefficients_from_file')
    @patch('scripts.migrate_coefficients.get_db')
    def test_migrate_closes_session(self, mock_get_db, mock_load):
        """Test that database session is always closed."""
        mock_load.return_value = {"gdcards": {"pattern": ".*", "coefficient": 2}}
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.side_effect = self._fake_get_db(mock_db)

        migrate_coefficients()

        mock_db.close.assert_called_once()

    @patch('scripts.migrate_coefficients.load_coefficients_from_file')
    @patch('scripts.migrate_coefficients.get_db')
    def test_migrate_uses_defaults_when_empty(self, mock_get_db, mock_load):
        """Test migration falls back to defaults when load returns empty."""
        mock_load.return_value = {}
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.side_effect = self._fake_get_db(mock_db)

        stats = migrate_coefficients()

        assert stats["total"] == len(DEFAULT_COEFFICIENTS)
        assert stats["created"] == len(DEFAULT_COEFFICIENTS)
        mock_db.commit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])

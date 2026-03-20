"""Unit tests for StartupValidator."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.startup_validator import StartupValidator


class TestStartupValidatorEnvFile:
    """Тесты валидации .env файла."""
    
    def test_validate_env_file_exists(self, tmp_path, monkeypatch):
        """Проверка при существующем .env файле."""
        env_file = tmp_path / "config" / ".env"
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text("BOT_TOKEN=test")
        
        monkeypatch.chdir(tmp_path)
        result = StartupValidator.validate_env_file()
        assert result is True
    
    def test_validate_env_file_not_exists(self, tmp_path, monkeypatch):
        """Проверка при отсутствии .env файла."""
        monkeypatch.chdir(tmp_path)
        result = StartupValidator.validate_env_file()
        assert result is False
    
    def test_validate_env_file_fallback(self, tmp_path, monkeypatch):
        """Проверка с резервным путем .env."""
        env_file = tmp_path / ".env"
        env_file.write_text("BOT_TOKEN=test")
        
        monkeypatch.chdir(tmp_path)
        result = StartupValidator.validate_env_file()
        assert result is True


class TestStartupValidatorRequiredSettings:
    """Тесты валидации обязательных настроек."""
    
    def test_validate_required_settings_valid(self):
        """Проверка с валидными настройками."""
        with patch('src.config.settings') as mock_settings:
            mock_settings.BOT_TOKEN = "test_token"
            mock_settings.ADMIN_TELEGRAM_ID = 123456
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            
            result, missing = StartupValidator.validate_required_settings()
            assert result is True
            assert missing == []


class TestStartupValidatorDatabase:
    """Тесты валидации подключения к БД."""
    
    def test_validate_database_connection_success(self):
        """Проверка при успешном подключении."""
        mock_session = MagicMock()
        mock_session.execute = MagicMock()
        
        with patch('database.database.get_db', return_value=mock_session):
            result = StartupValidator.validate_database_connection()
            assert result is True
            mock_session.execute.assert_called_once_with("SELECT 1")
            mock_session.close.assert_called_once()
    
    def test_validate_database_connection_failure(self):
        """Проверка при ошибке подключения."""
        with patch('database.database.get_db', side_effect=Exception("DB error")):
            result = StartupValidator.validate_database_connection()
            assert result is False
    
    def test_validate_database_connection_import_error(self):
        """Проверка при отсутствии get_db."""
        with patch('database.database.get_db', side_effect=ImportError):
            result = StartupValidator.validate_database_connection()
            assert result is False


class TestStartupValidatorDirectoryStructure:
    """Тесты валидации структуры директорий."""
    
    def test_validate_directory_structure_exists(self, tmp_path, monkeypatch):
        """Проверка при существующих директориях."""
        (tmp_path / "data").mkdir()
        (tmp_path / "logs").mkdir()
        (tmp_path / "config").mkdir()
        
        monkeypatch.chdir(tmp_path)
        result = StartupValidator.validate_directory_structure()
        assert result is True
    
    def test_validate_directory_structure_creates_missing(self, tmp_path, monkeypatch):
        """Проверка создания отсутствующих директорий."""
        monkeypatch.chdir(tmp_path)
        result = StartupValidator.validate_directory_structure()
        assert result is True
        assert (tmp_path / "data").exists()
        assert (tmp_path / "logs").exists()
        assert (tmp_path / "config").exists()


class TestStartupValidatorFull:
    """Тесты полной валидации."""
    
    def test_validate_all_success(self):
        """Проверка при успешной валидации."""
        with patch.object(StartupValidator, 'validate_env_file', return_value=True):
            with patch.object(StartupValidator, 'validate_required_settings', return_value=(True, [])):
                with patch.object(StartupValidator, 'validate_directory_structure', return_value=True):
                    with patch.object(StartupValidator, 'validate_database_connection', return_value=True):
                        result = StartupValidator.validate_all()
                        assert result is True
    
    def test_validate_all_failure(self):
        """Проверка при провале валидации."""
        with patch.object(StartupValidator, 'validate_env_file', return_value=False):
            with patch.object(StartupValidator, 'validate_required_settings', return_value=(True, [])):
                with patch.object(StartupValidator, 'validate_directory_structure', return_value=True):
                    with patch.object(StartupValidator, 'validate_database_connection', return_value=True):
                        result = StartupValidator.validate_all()
                        assert result is False


class TestValidateStartup:
    """Тесты удобной функции validate_startup."""
    
    def test_validate_startup(self):
        """Проверка функции validate_startup."""
        with patch.object(StartupValidator, 'validate_all', return_value=True):
            from src.startup_validator import validate_startup
            result = validate_startup()
            assert result is True

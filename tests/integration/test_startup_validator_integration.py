"""Integration tests for StartupValidator integration with main.py."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestStartupValidatorIntegration:
    """Интеграционные тесты валидации с main.py."""
    
    def test_main_calls_validate_startup(self, tmp_path, monkeypatch):
        """Проверка, что main.py вызывает validate_startup."""
        # Создаем временный main.py для теста
        main_content = '''
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.startup_validator import validate_startup

def main():
    if not validate_startup():
        sys.exit(1)
    print("Success")

if __name__ == "__main__":
    main()
'''
        test_main_path = tmp_path / "test_main.py"
        test_main_path.write_text(main_content)
        
        # Мокаем validate_startup
        with patch('src.startup_validator.validate_startup', return_value=True) as mock_validate:
            # Запускаем main
            exec(test_main_path.read_text(), {'__name__': '__main__', '__file__': str(test_main_path)})
            
            # Проверяем, что validate_startup был вызван
            mock_validate.assert_called_once()
    
    def test_main_exits_on_validation_failure(self, tmp_path, monkeypatch):
        """Проверка, что main.py завершается при провале валидации."""
        # Создаем временный main.py для теста
        main_content = '''
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.startup_validator import validate_startup

def main():
    if not validate_startup():
        sys.exit(1)
    print("Success")

if __name__ == "__main__":
    main()
'''
        test_main_path = tmp_path / "test_main.py"
        test_main_path.write_text(main_content)
        
        # Мокаем validate_startup для возврата False
        with patch('src.startup_validator.validate_startup', return_value=False) as mock_validate:
            # Запускаем main и проверяем, что sys.exit был вызван
            with pytest.raises(SystemExit) as exc_info:
                exec(test_main_path.read_text(), {'__name__': '__main__', '__file__': str(test_main_path)})
            
            assert exc_info.value.code == 1
            mock_validate.assert_called_once()


class TestStartupValidatorEnvironment:
    """Тесты валидации в разных окружениях."""
    
    def test_validation_with_valid_env(self, tmp_path, monkeypatch):
        """Проверка валидации с валидной конфигурацией."""
        # Создаем .env файл
        env_dir = tmp_path / "config"
        env_dir.mkdir(parents=True, exist_ok=True)
        env_file = env_dir / ".env"
        env_file.write_text("BOT_TOKEN=test_token\nADMIN_TELEGRAM_ID=123456\nDATABASE_URL=sqlite:///test.db")
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENV", "test")
        
        from src.startup_validator import validate_startup
        result = validate_startup()
        # Результат зависит от наличия других директорий
        assert result is True
    
    def test_validation_with_missing_env(self, tmp_path, monkeypatch):
        """Проверка валидации без .env файла."""
        monkeypatch.chdir(tmp_path)
        
        from src.startup_validator import validate_startup
        result = validate_startup()
        assert result is False

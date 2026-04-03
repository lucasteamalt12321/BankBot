"""Startup validation system for the Telegram bot."""

from pathlib import Path
from typing import List, Tuple

from src.config import settings
from src.logging_config import get_logger

logger = get_logger(__name__)


class StartupValidator:
    """
    Валидатор конфигурации при запуске бота.
    
    Проверяет наличие необходимых файлов и корректность настроек
    перед запуском приложения.
    """
    
    @staticmethod
    def validate_env_file() -> bool:
        """
        Проверяет существование .env файла.
        
        Returns:
            True если файл найден, False если нет
        """
        env_paths = [
            Path("config/.env"),
            Path(".env"),
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                logger.info(f"✅ .env файл найден: {env_path}")
                return True
        
        logger.error(
            "❌ .env файл не найден!\n"
            "Пожалуйста, создайте файл config/.env на основе config/.env.example\n"
            "и заполните необходимые значения."
        )
        return False
    
    @staticmethod
    def validate_required_settings() -> Tuple[bool, List[str]]:
        """
        Проверяет наличие обязательных настроек.
        
        Returns:
            Кортеж (успех, список отсутствующих настроек)
        """
        # Проверяем, что настройки не пустые (для строк) или не нулевые (для int)
        required_settings = {
            'BOT_TOKEN': settings.BOT_TOKEN,
            'ADMIN_TELEGRAM_ID': settings.ADMIN_TELEGRAM_ID,
            'DATABASE_URL': settings.DATABASE_URL,
        }
        
        # Проверяем, что значения не пустые/нулевые
        missing = []
        for name, value in required_settings.items():
            if isinstance(value, str):
                if not value or value == "":
                    missing.append(name)
            elif isinstance(value, int):
                if value <= 0:
                    missing.append(name)
            else:
                if not value:
                    missing.append(name)
        
        if missing:
            logger.error(
                f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing)}\n"
                "Пожалуйста, проверьте ваш config/.env файл."
            )
            return False, missing
        
        logger.info("✅ Все обязательные настройки присутствуют")
        return True, []
    
    @staticmethod
    def validate_database_connection() -> bool:
        """
        Проверяет подключение к базе данных.
        
        Returns:
            True если подключение успешно, False если нет
        """
        try:
            from database.database import SessionLocal
            from sqlalchemy import text
            session = SessionLocal()
            try:
                # Простая проверка - попытка выполнить запрос
                session.execute(text("SELECT 1"))
                logger.info("✅ Подключение к базе данных успешно")
                return True
            finally:
                session.close()
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к базе данных: {e}")
            return False
    
    @staticmethod
    def validate_directory_structure() -> bool:
        """
        Проверяет наличие необходимых директорий.
        
        Returns:
            True если все директории существуют, False если нет
        """
        required_dirs = [
            Path("data"),
            Path("logs"),
            Path("config"),
        ]
        
        missing = []
        for dir_path in required_dirs:
            if not dir_path.exists():
                missing.append(dir_path)
                logger.warning(f"⚠️ Директория не найдена: {dir_path}")
        
        if missing:
            logger.info(f"ℹ️ Создание отсутствующих директорий: {', '.join(str(d) for d in missing)}")
            for dir_path in missing:
                dir_path.mkdir(parents=True, exist_ok=True)
        
        return True
    
    @classmethod
    def validate_all(cls) -> bool:
        """
        Выполняет полную валидацию конфигурации.
        
        Returns:
            True если все проверки пройдены, False если есть ошибки
        """
        logger.info("🔍 Начало валидации конфигурации...")
        
        validations = [
            ("Файл конфигурации", cls.validate_env_file),
            ("Обязательные настройки", cls.validate_required_settings),
            ("Структура директорий", cls.validate_directory_structure),
            ("Подключение к БД", cls.validate_database_connection),
        ]
        
        results = []
        for name, validator in validations:
            try:
                result = validator()
                if isinstance(result, tuple):
                    result = result[0]  # Берем первый элемент кортежа (bool)
                results.append((name, result))
            except Exception as e:
                logger.error(f"❌ Ошибка валидации {name}: {e}")
                results.append((name, False))
        
        # Итоговый результат
        all_passed = all(result for _, result in results)
        
        if all_passed:
            logger.info("✅ Все проверки пройдены успешно")
        else:
            failed = [name for name, result in results if not result]
            logger.error(f"❌ Валидация не пройдена: {', '.join(failed)}")
        
        return all_passed


def validate_startup() -> bool:
    """
    Удобная функция для валидации при запуске.
    
    Returns:
        True если все проверки пройдены, False если есть ошибки
    """
    return StartupValidator.validate_all()

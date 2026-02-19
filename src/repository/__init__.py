"""Repository package for database operations."""

from src.repository.base import BaseRepository

# Импортируем DatabaseRepository из родительского модуля src.repository (файл repository.py)
# Это нужно для обратной совместимости
import importlib.util
import os

# Получаем путь к файлу repository.py в папке src
repo_file_path = os.path.join(os.path.dirname(__file__), '..', 'repository.py')
repo_file_path = os.path.abspath(repo_file_path)

if os.path.exists(repo_file_path):
    spec = importlib.util.spec_from_file_location("_repository_module", repo_file_path)
    if spec and spec.loader:
        _repository_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_repository_module)
        DatabaseRepository = _repository_module.DatabaseRepository
        SQLiteRepository = _repository_module.SQLiteRepository
    else:
        # Fallback
        DatabaseRepository = BaseRepository
        SQLiteRepository = None
else:
    # Fallback
    DatabaseRepository = BaseRepository
    SQLiteRepository = None

__all__ = ["BaseRepository", "DatabaseRepository", "SQLiteRepository"]

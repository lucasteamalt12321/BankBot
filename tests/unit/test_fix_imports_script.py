"""
Unit tests for the fix_imports.py script.
"""
import pytest
import tempfile
from pathlib import Path
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

from fix_imports import ImportFixer, IMPORT_REPLACEMENTS


class TestImportFixer:
    """Test the ImportFixer class."""
    
    def test_import_replacements_defined(self):
        """Test that import replacements are properly defined."""
        assert len(IMPORT_REPLACEMENTS) > 0
        assert r'from utils\.admin_system import' in IMPORT_REPLACEMENTS
        assert r'from utils\.simple_db import' in IMPORT_REPLACEMENTS
        assert r'from utils\.admin_middleware import' in IMPORT_REPLACEMENTS
    
    def test_fix_admin_system_import(self):
        """Test fixing admin_system imports."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('from utils.admin.admin_system import AdminSystem\n')
            f.write('admin = AdminSystem()\n')
            temp_path = Path(f.name)
        
        try:
            fixer = ImportFixer(dry_run=False)
            result = fixer.fix_imports_in_file(temp_path)
            
            assert result is True
            content = temp_path.read_text()
            assert 'from utils.admin.admin_system import AdminSystem' in content
            assert 'from utils.admin.admin_system import' not in content
        finally:
            temp_path.unlink()
    
    def test_fix_simple_db_import(self):
        """Test fixing simple_db imports."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('from utils.database.simple_db import register_user, get_user_by_id\n')
            f.write('user = register_user("test")\n')
            temp_path = Path(f.name)
        
        try:
            fixer = ImportFixer(dry_run=False)
            result = fixer.fix_imports_in_file(temp_path)
            
            assert result is True
            content = temp_path.read_text()
            assert 'from utils.database.simple_db import' in content
            assert 'from utils.database.simple_db import' not in content
        finally:
            temp_path.unlink()
    
    def test_fix_admin_middleware_import(self):
        """Test fixing admin_middleware imports."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('from utils.admin.admin_middleware import auto_registration_middleware\n')
            f.write('middleware = auto_registration_middleware\n')
            temp_path = Path(f.name)
        
        try:
            fixer = ImportFixer(dry_run=False)
            result = fixer.fix_imports_in_file(temp_path)
            
            assert result is True
            content = temp_path.read_text()
            assert 'from utils.admin.admin_middleware import' in content
            assert 'from utils.admin.admin_middleware import' not in content
        finally:
            temp_path.unlink()
    
    def test_fix_import_statement(self):
        """Test fixing import statements (not from...import)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('import utils.database.simple_db\n')
            f.write('utils.simple_db.register_user("test")\n')
            temp_path = Path(f.name)
        
        try:
            fixer = ImportFixer(dry_run=False)
            result = fixer.fix_imports_in_file(temp_path)
            
            assert result is True
            content = temp_path.read_text()
            assert 'import utils.database.simple_db' in content
            assert 'import utils.database.simple_db' not in content
        finally:
            temp_path.unlink()
    
    def test_no_changes_needed(self):
        """Test that files with correct imports are not modified."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('from utils.admin.admin_system import AdminSystem\n')
            f.write('from utils.database.simple_db import register_user\n')
            temp_path = Path(f.name)
        
        try:
            fixer = ImportFixer(dry_run=False)
            result = fixer.fix_imports_in_file(temp_path)
            
            assert result is False
        finally:
            temp_path.unlink()
    
    def test_dry_run_mode(self):
        """Test that dry-run mode doesn't modify files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            original_content = 'from utils.admin.admin_system import AdminSystem\n'
            f.write(original_content)
            temp_path = Path(f.name)
        
        try:
            fixer = ImportFixer(dry_run=True)
            result = fixer.fix_imports_in_file(temp_path)
            
            assert result is True
            content = temp_path.read_text()
            assert content == original_content  # File should not be modified
        finally:
            temp_path.unlink()
    
    def test_multiple_imports_in_one_file(self):
        """Test fixing multiple different imports in one file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('from utils.admin.admin_system import AdminSystem\n')
            f.write('from utils.database.simple_db import register_user\n')
            f.write('from utils.admin.admin_middleware import auto_registration_middleware\n')
            temp_path = Path(f.name)
        
        try:
            fixer = ImportFixer(dry_run=False)
            result = fixer.fix_imports_in_file(temp_path)
            
            assert result is True
            content = temp_path.read_text()
            assert 'from utils.admin.admin_system import' in content
            assert 'from utils.database.simple_db import' in content
            assert 'from utils.admin.admin_middleware import' in content
            assert 'from utils.admin.admin_system import' not in content
            assert 'from utils.database.simple_db import' not in content
            assert 'from utils.admin.admin_middleware import' not in content
        finally:
            temp_path.unlink()
    
    def test_find_python_files(self):
        """Test finding Python files in a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create some Python files
            (tmpdir_path / 'test1.py').write_text('# test')
            (tmpdir_path / 'test2.py').write_text('# test')
            (tmpdir_path / 'not_python.txt').write_text('# test')
            
            # Create subdirectory with Python file
            subdir = tmpdir_path / 'subdir'
            subdir.mkdir()
            (subdir / 'test3.py').write_text('# test')
            
            # Create excluded directory
            excluded = tmpdir_path / '__pycache__'
            excluded.mkdir()
            (excluded / 'test4.py').write_text('# test')
            
            fixer = ImportFixer()
            files = fixer.find_python_files(tmpdir_path)
            
            assert len(files) == 3  # Should find test1, test2, test3 but not test4
            assert all(f.suffix == '.py' for f in files)
            assert not any('__pycache__' in str(f) for f in files)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

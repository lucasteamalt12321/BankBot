"""
Unit tests for the fix_config_imports.py script.

**Validates: Requirements 1.3**
"""

import pytest
import tempfile
from pathlib import Path
import sys
import os

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'scripts'))

from fix_config_imports import ImportFixer, IMPORT_REPLACEMENTS


class TestImportFixer:
    """Test the ImportFixer class."""
    
    def test_import_replacements_defined(self):
        """Test that import replacements are properly defined."""
        assert 'from utils\\.config import' in IMPORT_REPLACEMENTS
        assert 'from utils\\.core\\.config import' in IMPORT_REPLACEMENTS
        assert IMPORT_REPLACEMENTS['from utils\\.config import'] == 'from src.config import'
        assert IMPORT_REPLACEMENTS['from utils\\.core\\.config import'] == 'from src.config import'
    
    def test_find_python_files_excludes_venv(self):
        """Test that .venv and venv directories are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create test structure
            (tmppath / 'test.py').write_text('# test')
            (tmppath / '.venv').mkdir()
            (tmppath / '.venv' / 'test.py').write_text('# venv test')
            (tmppath / 'venv').mkdir()
            (tmppath / 'venv' / 'test.py').write_text('# venv test')
            
            fixer = ImportFixer(dry_run=True)
            files = fixer.find_python_files(tmppath)
            
            # Should only find the root test.py
            assert len(files) == 1
            assert files[0].name == 'test.py'
            assert '.venv' not in str(files[0])
            assert 'venv' not in str(files[0])
    
    def test_fix_imports_utils_config(self):
        """Test fixing imports from src.config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / 'test.py'
            
            # Write test content with OLD import
            test_file.write_text('from src.config import settings\n')
            
            fixer = ImportFixer(dry_run=False)
            modified = fixer.fix_imports_in_file(test_file)
            
            assert modified is True
            content = test_file.read_text()
            assert 'from src.config import settings' in content
            assert 'from src.config import' not in content
    
    def test_fix_imports_utils_core_config(self):
        """Test fixing imports from src.config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / 'test.py'
            
            # Write test content with OLD import
            test_file.write_text('from src.config import settings\n')
            
            fixer = ImportFixer(dry_run=False)
            modified = fixer.fix_imports_in_file(test_file)
            
            assert modified is True
            content = test_file.read_text()
            assert 'from src.config import settings' in content
            assert 'from src.config import' not in content
    
    def test_no_changes_needed(self):
        """Test that files with correct imports are not modified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / 'test.py'
            
            # Write test content with correct import
            test_file.write_text('from src.config import settings\n')
            
            fixer = ImportFixer(dry_run=False)
            modified = fixer.fix_imports_in_file(test_file)
            
            assert modified is False
    
    def test_dry_run_mode(self):
        """Test that dry-run mode doesn't modify files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / 'test.py'
            
            original_content = 'from src.config import settings\n'
            test_file.write_text(original_content)
            
            fixer = ImportFixer(dry_run=True)
            modified = fixer.fix_imports_in_file(test_file)
            
            assert modified is True
            # File should not be changed in dry-run mode
            content = test_file.read_text()
            assert content == original_content
    
    def test_multiple_imports_in_file(self):
        """Test fixing multiple imports in a single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / 'test.py'
            
            # Write test content with multiple OLD imports
            test_file.write_text(
                'from src.config import settings\n'
                'from src.config import TRANSACTION_SECURITY\n'
                'from src.models import User\n'
            )
            
            fixer = ImportFixer(dry_run=False)
            modified = fixer.fix_imports_in_file(test_file)
            
            assert modified is True
            content = test_file.read_text()
            assert 'from src.config import settings' in content
            assert 'from src.config import TRANSACTION_SECURITY' in content
            assert 'from src.models import User' in content
            assert 'from src.config import' not in content
            assert 'from src.config import' not in content
    
    def test_preserves_other_imports(self):
        """Test that other imports are not affected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / 'test.py'
            
            # Write test content with OLD config import
            test_file.write_text(
                'from src.config import settings\n'
                'from utils.admin.admin_system import AdminManager\n'
                'from database.database import get_session\n'
            )
            
            fixer = ImportFixer(dry_run=False)
            modified = fixer.fix_imports_in_file(test_file)
            
            assert modified is True
            content = test_file.read_text()
            assert 'from src.config import settings' in content
            # These should remain unchanged
            assert 'from utils.admin.admin_system import AdminManager' in content
            assert 'from database.database import get_session' in content
    
    def test_statistics_tracking(self):
        """Test that statistics are tracked correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create multiple test files - some with old imports, some with new
            (tmppath / 'test1.py').write_text('from src.config import settings\n')
            (tmppath / 'test2.py').write_text('from src.config import settings\n')  # Already correct
            (tmppath / 'test3.py').write_text('from src.config import settings\n')
            
            fixer = ImportFixer(dry_run=False)
            stats = fixer.process_files(tmppath)
            
            assert stats['scanned'] == 3
            assert stats['modified'] == 2  # test1.py and test3.py
            assert stats['changes'] == 2


class TestImportReplacements:
    """Test the import replacement patterns."""
    
    def test_all_patterns_have_replacements(self):
        """Test that all patterns have corresponding replacements."""
        for pattern, replacement in IMPORT_REPLACEMENTS.items():
            assert pattern is not None
            assert replacement is not None
            assert len(pattern) > 0
            assert len(replacement) > 0
    
    def test_replacements_target_src_config(self):
        """Test that all replacements target src.config."""
        for pattern, replacement in IMPORT_REPLACEMENTS.items():
            assert 'src.config' in replacement


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

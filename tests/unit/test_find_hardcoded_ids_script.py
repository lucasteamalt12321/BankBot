"""
Unit tests for the find_hardcoded_ids.py script.
"""

import pytest
from pathlib import Path
import sys
import tempfile
import os

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from find_hardcoded_ids import find_hardcoded_ids, HARDCODED_ID


class TestFindHardcodedIds:
    """Test suite for find_hardcoded_ids script."""
    
    def test_finds_hardcoded_id_in_file(self):
        """Test that the script finds hardcoded ID in a Python file."""
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create a test directory
            test_dir = tmpdir_path / "bot"
            test_dir.mkdir()
            
            # Create a test file with hardcoded ID
            test_file = test_dir / "test.py"
            test_file.write_text(f"admin_id = {HARDCODED_ID}\n")
            
            # Run the search
            results = find_hardcoded_ids(tmpdir_path)
            
            # Verify results
            assert len(results) == 1
            assert results[0][0] == test_file
            assert results[0][1] == 1
            assert HARDCODED_ID in results[0][2]
    
    def test_finds_multiple_occurrences(self):
        """Test that the script finds multiple occurrences in the same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            test_dir = tmpdir_path / "core"
            test_dir.mkdir()
            
            test_file = test_dir / "test.py"
            test_file.write_text(
                f"admin_id = {HARDCODED_ID}\n"
                f"fallback_id = {HARDCODED_ID}\n"
            )
            
            results = find_hardcoded_ids(tmpdir_path)
            
            assert len(results) == 2
            assert all(r[0] == test_file for r in results)
    
    def test_ignores_files_without_hardcoded_id(self):
        """Test that files without the hardcoded ID are not reported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            test_dir = tmpdir_path / "utils"
            test_dir.mkdir()
            
            test_file = test_dir / "test.py"
            test_file.write_text("admin_id = settings.ADMIN_TELEGRAM_ID\n")
            
            results = find_hardcoded_ids(tmpdir_path)
            
            assert len(results) == 0
    
    def test_skips_excluded_directories(self):
        """Test that excluded directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create a directory that should be excluded
            venv_dir = tmpdir_path / "bot" / ".venv"
            venv_dir.mkdir(parents=True)
            
            test_file = venv_dir / "test.py"
            test_file.write_text(f"admin_id = {HARDCODED_ID}\n")
            
            results = find_hardcoded_ids(tmpdir_path)
            
            # Should not find anything because .venv is excluded
            assert len(results) == 0
    
    def test_handles_unicode_files(self):
        """Test that the script handles files with unicode content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            test_dir = tmpdir_path / "src"
            test_dir.mkdir()
            
            test_file = test_dir / "test.py"
            test_file.write_text(
                f"# Комментарий на русском\nadmin_id = {HARDCODED_ID}\n",
                encoding='utf-8'
            )
            
            results = find_hardcoded_ids(tmpdir_path)
            
            assert len(results) == 1
            assert HARDCODED_ID in results[0][2]
    
    def test_real_codebase_finds_occurrences(self):
        """Test that the script finds occurrences in the real codebase."""
        # This test runs on the actual project
        project_root = Path(__file__).parent.parent.parent
        results = find_hardcoded_ids(project_root)
        
        # We know there are hardcoded IDs in the codebase
        # (based on the requirements, there should be 20+)
        assert len(results) > 0
        
        # Verify the structure of results
        for file_path, line_num, line_content in results:
            assert isinstance(file_path, Path)
            assert isinstance(line_num, int)
            assert line_num > 0
            assert isinstance(line_content, str)
            assert HARDCODED_ID in line_content

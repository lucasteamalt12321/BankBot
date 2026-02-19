#!/usr/bin/env python3
"""
Script to find hardcoded admin Telegram ID (2091908459) in the codebase.

This script scans all Python files in the project and reports locations
where the hardcoded admin ID appears. This is part of the security refactoring
to move all sensitive data to environment variables.

Usage:
    python scripts/find_hardcoded_ids.py

Output:
    - Lists all files containing the hardcoded ID
    - Shows line numbers and content for each occurrence
    - Provides total count of occurrences found

The script searches in: bot/, core/, database/, src/, utils/, tests/
Excludes: .git/, .venv/, __pycache__/, .pytest_cache/, .hypothesis/
"""

import re
from pathlib import Path
from typing import List, Tuple


# The hardcoded ID we're looking for
HARDCODED_ID = "2091908459"

# Directories to search
SEARCH_DIRS = ["bot", "core", "database", "src", "utils", "tests"]

# Directories to exclude
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".hypothesis"}


def find_hardcoded_ids(root_dir: Path = Path(".")) -> List[Tuple[Path, int, str]]:
    """
    Find all occurrences of the hardcoded admin ID in Python files.
    
    Args:
        root_dir: Root directory to start searching from
        
    Returns:
        List of tuples (file_path, line_number, line_content)
    """
    results = []
    
    for search_dir in SEARCH_DIRS:
        dir_path = root_dir / search_dir
        if not dir_path.exists():
            continue
            
        # Find all Python files
        for py_file in dir_path.rglob("*.py"):
            # Skip excluded directories
            if any(excluded in py_file.parts for excluded in EXCLUDE_DIRS):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, start=1):
                        if HARDCODED_ID in line:
                            results.append((py_file, line_num, line.rstrip()))
            except (UnicodeDecodeError, PermissionError) as e:
                print(f"Warning: Could not read {py_file}: {e}")
                
    return results


def print_results(results: List[Tuple[Path, int, str]]) -> None:
    """
    Print the search results in a readable format.
    
    Args:
        results: List of tuples (file_path, line_number, line_content)
    """
    if not results:
        print(f"✅ No hardcoded ID '{HARDCODED_ID}' found in the codebase!")
        return
    
    print(f"🔍 Found {len(results)} occurrence(s) of hardcoded ID '{HARDCODED_ID}':\n")
    
    for file_path, line_num, line_content in results:
        print(f"📄 {file_path}")
        print(f"   Line {line_num}: {line_content}")
        print()


def main():
    """Main entry point for the script."""
    print("=" * 70)
    print("Searching for hardcoded admin Telegram ID...")
    print("=" * 70)
    print()
    
    results = find_hardcoded_ids()
    print_results(results)
    
    if results:
        print("=" * 70)
        print(f"Total: {len(results)} occurrence(s) found")
        print("=" * 70)
        print("\n💡 Tip: Replace these with settings.ADMIN_TELEGRAM_ID")
        print("   from src.config import settings")


if __name__ == "__main__":
    main()

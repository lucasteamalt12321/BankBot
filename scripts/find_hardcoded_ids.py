#!/usr/bin/env python3
"""
Script to find all hardcoded Telegram IDs in the codebase.
Specifically looking for ID 2091908459 that should be replaced with settings.ADMIN_TELEGRAM_ID
"""

import re
from pathlib import Path
from typing import List, Tuple

# ID to search for (exported for tests)
TARGET_ID = "2091908459"
HARDCODED_ID = TARGET_ID  # Alias for backward compatibility with tests

# Directories to search
SEARCH_DIRS = ["src", "bot", "core", "utils", "tests"]

# File extensions to search
EXTENSIONS = [".py"]

# Directories to exclude
EXCLUDE_DIRS = [".venv", "venv", "__pycache__", ".git", ".pytest_cache", "node_modules"]

# Patterns to exclude (already using settings)
EXCLUDE_PATTERNS = [
    r"settings\.ADMIN_TELEGRAM_ID",
    r"config\.ADMIN_TELEGRAM_ID",
]


def should_exclude_line(line: str) -> bool:
    """Check if line should be excluded from results."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, line):
            return True
    return False


def should_exclude_path(path: Path) -> bool:
    """Check if path should be excluded from search."""
    # Check if any parent directory is in the exclude list
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def find_hardcoded_ids(root_dir: Path = Path(".")) -> List[Tuple[Path, int, str]]:
    """
    Find all occurrences of hardcoded ID in Python files.
    
    Returns:
        List of tuples (file_path, line_number, line_content)
    """
    results = []
    
    for search_dir in SEARCH_DIRS:
        dir_path = root_dir / search_dir
        if not dir_path.exists():
            continue
            
        for ext in EXTENSIONS:
            for file_path in dir_path.rglob(f"*{ext}"):
                # Skip excluded directories
                if should_exclude_path(file_path):
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if TARGET_ID in line and not should_exclude_line(line):
                                results.append((file_path, line_num, line.strip()))
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    
    return results


def main():
    """Main function to find and display hardcoded IDs."""
    print(f"Searching for hardcoded ID: {TARGET_ID}")
    print(f"Directories: {', '.join(SEARCH_DIRS)}")
    print("-" * 80)
    
    results = find_hardcoded_ids()
    
    if not results:
        print("✅ No hardcoded IDs found!")
        return
    
    print(f"\n❌ Found {len(results)} occurrences:\n")
    
    # Group by file
    by_file = {}
    for file_path, line_num, line_content in results:
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append((line_num, line_content))
    
    # Display results
    for file_path in sorted(by_file.keys()):
        print(f"\n📄 {file_path}")
        for line_num, line_content in by_file[file_path]:
            print(f"   Line {line_num}: {line_content}")
    
    print(f"\n{'=' * 80}")
    print(f"Total files affected: {len(by_file)}")
    print(f"Total occurrences: {len(results)}")
    print(f"\nReplace with: settings.ADMIN_TELEGRAM_ID")
    print(f"Make sure to import: from src.config import settings")


if __name__ == "__main__":
    main()

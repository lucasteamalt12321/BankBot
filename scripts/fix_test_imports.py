#!/usr/bin/env python3
"""
Script to fix imports in test files.

This script updates old import patterns to new ones:
- utils.config -> src.config
- utils.core.config -> src.config
- utils.admin_system -> utils.admin.admin_system
- utils.simple_db -> utils.database.simple_db

Usage:
    python scripts/fix_test_imports.py [--dry-run] [path]

Arguments:
    path: Path to directory or file to fix (default: tests/)
    --dry-run: Show what would be changed without making changes
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple


# Mapping of old imports to new imports
IMPORT_MAPPINGS = {
    # Config imports
    r'from utils\.config import (.+)': r'from src.config import \1',
    r'import utils\.config': r'import src.config',
    r'from utils\.core\.config import (.+)': r'from src.config import \1',
    r'import utils\.core\.config': r'import src.config',
    
    # Admin system imports
    r'from utils\.admin_system import (.+)': r'from utils.admin.admin_system import \1',
    r'import utils\.admin_system': r'import utils.admin.admin_system',
    
    # Simple DB imports
    r'from utils\.simple_db import (.+)': r'from utils.database.simple_db import \1',
    r'import utils\.simple_db': r'import utils.database.simple_db',
    
    # Usage patterns in code
    r'utils\.config\.': r'src.config.',
    r'utils\.core\.config\.': r'src.config.',
    r'utils\.admin_system\.': r'utils.admin.admin_system.',
    r'utils\.simple_db\.': r'utils.database.simple_db.',
}


def fix_imports_in_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, List[str]]:
    """
    Fix imports in a single file.
    
    Args:
        file_path: Path to the file to fix
        dry_run: If True, don't write changes
        
    Returns:
        Tuple of (changed, list of changes made)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        changes = []
        
        # Apply each mapping
        for old_pattern, new_pattern in IMPORT_MAPPINGS.items():
            matches = list(re.finditer(old_pattern, content))
            if matches:
                content = re.sub(old_pattern, new_pattern, content)
                for match in matches:
                    old_text = match.group(0)
                    new_text = re.sub(old_pattern, new_pattern, old_text)
                    changes.append(f"  {old_text} -> {new_text}")
        
        # Check if anything changed
        if content != original_content:
            if not dry_run:
                file_path.write_text(content, encoding='utf-8')
            return True, changes
        
        return False, []
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False, []


def fix_imports_in_directory(directory: Path, dry_run: bool = False) -> None:
    """
    Fix imports in all Python files in a directory recursively.
    
    Args:
        directory: Path to the directory
        dry_run: If True, don't write changes
    """
    total_files = 0
    changed_files = 0
    
    # Find all Python files
    python_files = list(directory.rglob('*.py'))
    
    print(f"Found {len(python_files)} Python files in {directory}")
    print()
    
    for file_path in python_files:
        # Skip __pycache__ directories
        if '__pycache__' in str(file_path):
            continue
            
        total_files += 1
        changed, changes = fix_imports_in_file(file_path, dry_run)
        
        if changed:
            changed_files += 1
            print(f"{'[DRY RUN] ' if dry_run else ''}Fixed: {file_path}")
            for change in changes:
                print(change)
            print()
    
    print(f"\nSummary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Files changed: {changed_files}")
    print(f"  Files unchanged: {total_files - changed_files}")
    
    if dry_run:
        print("\nThis was a dry run. No files were modified.")
        print("Run without --dry-run to apply changes.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fix imports in test files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='tests',
        help='Path to directory or file to fix (default: tests/)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making changes'
    )
    
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if not path.exists():
        print(f"Error: Path {path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    if path.is_file():
        changed, changes = fix_imports_in_file(path, args.dry_run)
        if changed:
            print(f"{'[DRY RUN] ' if args.dry_run else ''}Fixed: {path}")
            for change in changes:
                print(change)
        else:
            print(f"No changes needed in {path}")
    else:
        fix_imports_in_directory(path, args.dry_run)


if __name__ == '__main__':
    main()

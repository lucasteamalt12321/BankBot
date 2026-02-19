#!/usr/bin/env python3
"""
Script to automatically update deprecated imports to use the new module structure.

This script replaces imports from:
- utils.admin_system -> utils.admin.admin_system
- utils.simple_db -> utils.database.simple_db

Usage:
    python scripts/fix_imports.py [--dry-run] [--path PATH]

Options:
    --dry-run    Preview changes without modifying files
    --path PATH  Specific file or directory to process (default: entire project)
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import argparse


# Import patterns to replace
IMPORT_REPLACEMENTS = {
    # Pattern: (old_pattern, new_replacement)
    r'from utils\.admin_system import': 'from utils.admin.admin_system import',
    r'import utils\.admin_system': 'import utils.admin.admin_system',
    r'from utils\.simple_db import': 'from utils.database.simple_db import',
    r'import utils\.simple_db': 'import utils.database.simple_db',
    r'from utils\.admin_middleware import': 'from utils.admin.admin_middleware import',
    r'import utils\.admin_middleware': 'import utils.admin.admin_middleware',
}


class ImportFixer:
    """Handles fixing imports in Python files."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.files_modified = 0
        self.files_scanned = 0
        self.changes_made: List[Tuple[Path, str, str]] = []
    
    def find_python_files(self, path: Path) -> List[Path]:
        """Find all Python files in the given path."""
        if path.is_file():
            return [path] if path.suffix == '.py' else []
        
        # Exclude certain directories
        exclude_dirs = {'.venv', 'venv', '__pycache__', '.git', '.pytest_cache', 
                       '.hypothesis', 'node_modules', 'backups', '.kiro'}
        
        python_files = []
        for py_file in path.rglob('*.py'):
            # Check if any parent directory is in exclude list
            if not any(excluded in py_file.parts for excluded in exclude_dirs):
                python_files.append(py_file)
        
        return python_files
    
    def fix_imports_in_file(self, file_path: Path) -> bool:
        """
        Fix imports in a single file.
        
        Returns:
            True if file was modified, False otherwise
        """
        try:
            content = file_path.read_text(encoding='utf-8')
            original_content = content
            modified = False
            
            # Apply import replacements
            for old_pattern, new_replacement in IMPORT_REPLACEMENTS.items():
                if re.search(old_pattern, content):
                    content = re.sub(old_pattern, new_replacement, content)
                    print(f"  ✓ Replaced: {old_pattern} -> {new_replacement}")
                    modified = True
            
            # Check if file was modified
            if modified:
                if not self.dry_run:
                    file_path.write_text(content, encoding='utf-8')
                
                self.changes_made.append((file_path, original_content, content))
                return True
            
            return False
            
        except Exception as e:
            print(f"  ✗ Error processing {file_path}: {e}", file=sys.stderr)
            return False
    
    def show_diff(self, file_path: Path, old_content: str, new_content: str):
        """Show a simple diff of changes."""
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        print(f"\n{'='*60}")
        print(f"Changes in: {file_path}")
        print('='*60)
        
        for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines), 1):
            if old_line != new_line:
                print(f"Line {i}:")
                print(f"  - {old_line}")
                print(f"  + {new_line}")
    
    def process_files(self, path: Path) -> Dict[str, int]:
        """
        Process all Python files in the given path.
        
        Returns:
            Dictionary with statistics
        """
        python_files = self.find_python_files(path)
        self.files_scanned = len(python_files)
        
        print(f"\n🔍 Found {self.files_scanned} Python files to scan")
        print(f"{'='*60}\n")
        
        for py_file in python_files:
            print(f"Processing: {py_file}")
            if self.fix_imports_in_file(py_file):
                self.files_modified += 1
                print(f"  ✓ Modified")
            else:
                print(f"  - No changes needed")
        
        return {
            'scanned': self.files_scanned,
            'modified': self.files_modified,
            'changes': len(self.changes_made)
        }
    
    def print_summary(self):
        """Print summary of changes."""
        print(f"\n{'='*60}")
        print("Summary")
        print('='*60)
        print(f"Files scanned: {self.files_scanned}")
        print(f"Files modified: {self.files_modified}")
        print(f"Total changes: {len(self.changes_made)}")
        
        if self.dry_run:
            print("\n⚠️  DRY RUN MODE - No files were actually modified")
            print("Run without --dry-run to apply changes")
        else:
            print("\n✅ Changes applied successfully")
        
        if self.changes_made and self.dry_run:
            print("\n📝 Preview of changes:")
            for file_path, old_content, new_content in self.changes_made[:5]:  # Show first 5
                self.show_diff(file_path, old_content, new_content)
            
            if len(self.changes_made) > 5:
                print(f"\n... and {len(self.changes_made) - 5} more files")


def main():
    """Main entry point."""
    # Fix encoding for Windows console
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    parser = argparse.ArgumentParser(
        description='Fix deprecated imports to use new module structure',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes for entire project
  python scripts/fix_imports.py --dry-run
  
  # Apply changes to entire project
  python scripts/fix_imports.py
  
  # Apply changes to specific directory
  python scripts/fix_imports.py --path tests/
  
  # Preview changes for specific file
  python scripts/fix_imports.py --dry-run --path tests/unit/test_example.py
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    
    parser.add_argument(
        '--path',
        type=str,
        default='.',
        help='Specific file or directory to process (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Resolve path
    target_path = Path(args.path).resolve()
    
    if not target_path.exists():
        print(f"❌ Error: Path does not exist: {target_path}", file=sys.stderr)
        sys.exit(1)
    
    print("🔧 Import Fixer")
    print('='*60)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print(f"Target: {target_path}")
    print('='*60)
    
    # Create fixer and process files
    fixer = ImportFixer(dry_run=args.dry_run)
    stats = fixer.process_files(target_path)
    
    # Print summary
    fixer.print_summary()
    
    # Exit with appropriate code
    if stats['modified'] > 0 and not args.dry_run:
        print("\n💡 Next steps:")
        print("  1. Review the changes: git diff")
        print("  2. Run tests: pytest")
        print("  3. Check for any remaining issues")
        sys.exit(0)
    elif stats['modified'] > 0 and args.dry_run:
        sys.exit(0)
    else:
        print("\n✨ No changes needed - all imports are already up to date!")
        sys.exit(0)


if __name__ == '__main__':
    main()

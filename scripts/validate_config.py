#!/usr/bin/env python3
"""Validation script for configuration files."""

import json
import sys
from pathlib import Path


def validate_coefficients_json(config_path: str) -> bool:
    """
    Validate coefficients.json format and content.
    
    Args:
        config_path: Path to coefficients.json file
        
    Returns:
        True if valid, False otherwise
    """
    print(f"Validating {config_path}...")
    
    # Check file exists
    if not Path(config_path).exists():
        print(f"❌ Error: File not found: {config_path}")
        return False
    
    # Load and parse JSON
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON format: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: Failed to read file: {e}")
        return False
    
    # Validate structure
    if not isinstance(data, dict):
        print("❌ Error: Root element must be a JSON object")
        return False
    
    # Expected games and coefficients
    expected_games = {
        "GD Cards": 2,
        "Shmalala": 1,
        "Shmalala Karma": 10,
        "True Mafia": 15,
        "Bunker RP": 20
    }
    
    # Check all expected games are present
    missing_games = set(expected_games.keys()) - set(data.keys())
    if missing_games:
        print(f"❌ Error: Missing games: {', '.join(missing_games)}")
        return False
    
    # Check for unexpected games
    extra_games = set(data.keys()) - set(expected_games.keys())
    if extra_games:
        print(f"⚠️  Warning: Unexpected games: {', '.join(extra_games)}")
    
    # Validate each game's coefficient
    errors = []
    for game, expected_coef in expected_games.items():
        actual_coef = data.get(game)
        
        # Check type
        if not isinstance(actual_coef, int):
            errors.append(f"  - {game}: coefficient must be an integer, got {type(actual_coef).__name__}")
            continue
        
        # Check value
        if actual_coef != expected_coef:
            print(f"⚠️  Warning: {game}: expected coefficient {expected_coef}, got {actual_coef}")
        
        # Check positive
        if actual_coef <= 0:
            errors.append(f"  - {game}: coefficient must be positive, got {actual_coef}")
    
    if errors:
        print("❌ Validation errors:")
        for error in errors:
            print(error)
        return False
    
    # Success
    print("✅ Validation successful!")
    print(f"   Found {len(data)} games with valid coefficients")
    for game, coef in sorted(data.items()):
        print(f"   - {game}: {coef}")
    
    return True


def main():
    """Main validation function."""
    config_path = "config/coefficients.json"
    
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    success = validate_coefficients_json(config_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

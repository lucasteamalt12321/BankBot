#!/usr/bin/env python3
"""
Script to remove admin command implementations from bot/bot.py
Task 10.2.1 - Переместить admin команды
"""

def remove_admin_commands():
    with open('bot/bot.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the start and end markers
    start_marker = "    # ===== Админ-команды =====\n"
    end_marker = "    # ===== Обработка сообщений =====\n"
    
    start_idx = None
    end_idx = None
    
    for i, line in enumerate(lines):
        if line == start_marker and start_idx is None:
            start_idx = i
        elif line == end_marker and start_idx is not None:
            end_idx = i
            break
    
    if start_idx is not None and end_idx is not None:
        # Keep the markers but remove everything in between
        replacement = [
            start_marker,
            "    # Task 10.2.1: Admin commands moved to bot/commands/admin_commands.py\n",
            "    # All admin command handlers are now registered dynamically via _register_admin_commands()\n",
            "    # See AdminCommands class for implementations\n",
            "\n",
            end_marker
        ]
        
        new_lines = lines[:start_idx] + replacement + lines[end_idx+1:]
        
        with open('bot/bot.py', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"✅ Removed {end_idx - start_idx - 1} lines of admin command implementations")
        print(f"   Start: line {start_idx + 1}")
        print(f"   End: line {end_idx + 1}")
    else:
        print("❌ Could not find admin commands section markers")
        print(f"   Start marker found: {start_idx is not None}")
        print(f"   End marker found: {end_idx is not None}")

if __name__ == '__main__':
    remove_admin_commands()

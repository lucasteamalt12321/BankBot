#!/usr/bin/env python3
"""Создание таблицы bot_balances"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import create_tables

print("Creating all tables (including bot_balances)...")
create_tables()
print("✅ All tables created successfully")

#!/usr/bin/env python3
"""
Миграция: Добавление таблицы parsing_rules_config для унифицированной конфигурации парсинга

Эта миграция создает новую таблицу parsing_rules_config, которая заменяет
старый подход с coefficients.json и ADVANCED_CURRENCY_CONFIG.

Новая таблица хранит:
- game_name: уникальное имя игры (например, 'gdcards', 'shmalala')
- parser_class: имя класса парсера для использования
- coefficient: коэффициент множителя для расчета очков
- enabled: активно ли это правило парсинга
- config: дополнительная JSON конфигурация для парсера
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import inspect, text
from database.database import engine
from src.models.parsing_rule import ParsingRule

def run_migration():
    """Создает таблицу parsing_rules_config если её нет"""
    inspector = inspect(engine)

    if 'parsing_rules_config' not in inspector.get_table_names():
        print("Creating parsing_rules_config table...")
        ParsingRule.__table__.create(engine)
        print("✅ Table parsing_rules_config created successfully")

        # Добавляем начальные данные для существующих игр
        print("Adding initial parsing rules...")
        with engine.connect() as conn:
            # Данные из coefficients.json и существующей конфигурации
            initial_rules = [
                {
                    'game_name': 'gdcards',
                    'parser_class': 'GDCardsParser',
                    'coefficient': 1.0,
                    'enabled': True,
                    'config': '{}'
                },
                {
                    'game_name': 'shmalala',
                    'parser_class': 'ShmalalaParser',
                    'coefficient': 1.0,
                    'enabled': True,
                    'config': '{}'
                },
                {
                    'game_name': 'truemafia',
                    'parser_class': 'TrueMafiaParser',
                    'coefficient': 1.0,
                    'enabled': True,
                    'config': '{}'
                },
                {
                    'game_name': 'bunkerrp',
                    'parser_class': 'BunkerRPParser',
                    'coefficient': 1.0,
                    'enabled': True,
                    'config': '{}'
                }
            ]

            for rule in initial_rules:
                conn.execute(
                    text("""
                        INSERT OR IGNORE INTO parsing_rules_config 
                        (game_name, parser_class, coefficient, enabled, config)
                        VALUES (:game_name, :parser_class, :coefficient, :enabled, :config)
                    """),
                    rule
                )
            conn.commit()
            print(f"✅ Added {len(initial_rules)} initial parsing rules")
    else:
        print("ℹ️ Table parsing_rules_config already exists")

if __name__ == "__main__":
    run_migration()

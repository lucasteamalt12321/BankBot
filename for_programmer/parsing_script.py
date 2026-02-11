"""
Скрипт парсинга игровых сообщений
Интегрирован в систему core/parsers/simple_parser.py
"""

# Пример использования парсера
message = ""  # любое сообщение
user = ""
amount = 0

if "🃏 НОВАЯ КАРТА 🃏" in message:
    lines = message.splitlines()
    for line in lines:
        if "Игрок:" in line:
            _, user = line.split(":", 1)
            user = user.strip()
        if "Очки:" in line and "+" in line:
            _, n = line.split("+", 1)
            amount = int(n.strip())

elif "🎣 [Рыбалка] 🎣" in message:
    lines = message.splitlines()
    for line in lines:
        if "Рыбак:" in line:
            _, user = line.split(":", 1)
            user = user.strip()
        if "Монеты:" in line and "+" in line:
            _, a = line.split("+", 1)
            n, _ = a.split("(", 1)
            amount = int(n.strip())

# Этот скрипт интегрирован в систему парсинга
# Используйте функции из core/parsers/simple_parser.py:
# - parse_card_message(text) для парсинга карт
# - parse_fishing_message(text) для парсинга рыбалки
# - parse_game_message(text) для автоматического определения типа
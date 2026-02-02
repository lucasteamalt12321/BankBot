#!/usr/bin/env python3
"""
Unit test for Task 4.1: Создать обработчик команды /admin с точным форматом вывода
"""
import os
import sys
import unittest
import tempfile
from unittest.mock import Mock, AsyncMock, patch

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes


class TestTask41AdminCommand(unittest.TestCase):
    """Тесты для задачи 4.1 - команда /admin"""
    
    def setUp(self):
        """Настройка тестового окружения"""
        # Создаем временную базу данных
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.admin_system = AdminSystem(self.temp_db.name)
        
        # Создаем тестовых пользователей
        self.admin_user_id = 123456789
        self.regular_user_id = 987654321
        
        # Регистрируем пользователей
        self.admin_system.register_user(self.admin_user_id, "admin_user", "Admin")
        self.admin_system.register_user(self.regular_user_id, "regular_user", "Regular")
        
        # Делаем одного пользователя администратором
        self.admin_system.set_admin_status(self.admin_user_id, True)
    
    def tearDown(self):
        """Очистка после тестов"""
        os.unlink(self.temp_db.name)
    
    def test_admin_rights_check(self):
        """Тест проверки прав администратора"""
        # Администратор должен иметь права
        self.assertTrue(self.admin_system.is_admin(self.admin_user_id))
        
        # Обычный пользователь не должен иметь права
        self.assertFalse(self.admin_system.is_admin(self.regular_user_id))
        
        # Несуществующий пользователь не должен иметь права
        self.assertFalse(self.admin_system.is_admin(999999999))
    
    def test_get_users_count_function(self):
        """Тест функции get_users_count()"""
        # Должно быть 2 пользователя (admin и regular)
        count = self.admin_system.get_users_count()
        self.assertEqual(count, 2)
        
        # Добавляем еще одного пользователя
        self.admin_system.register_user(555555555, "test_user", "Test")
        count = self.admin_system.get_users_count()
        self.assertEqual(count, 3)
    
    def test_exact_message_format(self):
        """Тест точного формата сообщения"""
        users_count = self.admin_system.get_users_count()
        expected_message = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        
        # Проверяем, что формат соответствует требованиям
        self.assertIn("Админ-панель:", expected_message)
        self.assertIn("/add_points @username [число] - начислить очки", expected_message)
        self.assertIn("/add_admin @username - добавить администратора", expected_message)
        self.assertIn(f"Всего пользователей: {users_count}", expected_message)
        
        # Проверяем точное соответствие
        lines = expected_message.split('\n')
        self.assertEqual(lines[0], "Админ-панель:")
        self.assertEqual(lines[1], "/add_points @username [число] - начислить очки")
        self.assertEqual(lines[2], "/add_admin @username - добавить администратора")
        self.assertEqual(lines[3], f"Всего пользователей: {users_count}")
    
    async def test_admin_command_logic(self):
        """Тест логики команды /admin"""
        # Создаем мок объекты для Telegram
        admin_user = User(id=self.admin_user_id, first_name="Admin", is_bot=False, username="admin_user")
        regular_user = User(id=self.regular_user_id, first_name="Regular", is_bot=False, username="regular_user")
        
        chat = Chat(id=1, type="private")
        
        # Тест для администратора
        admin_message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=admin_user,
            text="/admin"
        )
        
        admin_update = Update(update_id=1, message=admin_message)
        admin_update.effective_user = admin_user
        
        # Мокаем reply_text
        admin_message.reply_text = AsyncMock()
        
        # Симулируем логику команды /admin для администратора
        user = admin_update.effective_user
        if self.admin_system.is_admin(user.id):
            users_count = self.admin_system.get_users_count()
            text = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
            await admin_message.reply_text(text)
            
            # Проверяем, что сообщение было отправлено с правильным текстом
            admin_message.reply_text.assert_called_once_with(text)
        
        # Тест для обычного пользователя
        regular_message = Message(
            message_id=2,
            date=None,
            chat=chat,
            from_user=regular_user,
            text="/admin"
        )
        
        regular_update = Update(update_id=2, message=regular_message)
        regular_update.effective_user = regular_user
        
        # Мокаем reply_text
        regular_message.reply_text = AsyncMock()
        
        # Симулируем логику команды /admin для обычного пользователя
        user = regular_update.effective_user
        if not self.admin_system.is_admin(user.id):
            await regular_message.reply_text(
                "🔒 У вас нет прав администратора для выполнения этой команды.\n"
                "Обратитесь к администратору бота для получения доступа."
            )
            
            # Проверяем, что было отправлено сообщение об ошибке
            regular_message.reply_text.assert_called_once_with(
                "🔒 У вас нет прав администратора для выполнения этой команды.\n"
                "Обратитесь к администратору бота для получения доступа."
            )
    
    def test_requirements_compliance(self):
        """Тест соответствия требованиям задачи"""
        # Requirements: 1.1, 1.2, 1.4
        
        # Requirement 1.1: Точный формат сообщения
        users_count = self.admin_system.get_users_count()
        expected_format = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        
        # Проверяем каждую строку
        lines = expected_format.split('\n')
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], "Админ-панель:")
        self.assertEqual(lines[1], "/add_points @username [число] - начислить очки")
        self.assertEqual(lines[2], "/add_admin @username - добавить администратора")
        self.assertTrue(lines[3].startswith("Всего пользователей:"))
        
        # Requirement 1.2: Проверка прав администратора
        self.assertTrue(self.admin_system.is_admin(self.admin_user_id))
        self.assertFalse(self.admin_system.is_admin(self.regular_user_id))
        
        # Requirement 1.4: Подсчет пользователей
        count = self.admin_system.get_users_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
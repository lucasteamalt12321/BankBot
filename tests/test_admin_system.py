# test_admin_system.py - Тесты для системы администрирования
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem, admin_required, PermissionError, UserNotFoundError


class TestAdminSystem(unittest.TestCase):
    """Тесты для класса AdminSystem"""
    
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
    
    def test_is_admin_true(self):
        """Тест проверки прав администратора - положительный случай"""
        result = self.admin_system.is_admin(self.admin_user_id)
        self.assertTrue(result)
    
    def test_is_admin_false(self):
        """Тест проверки прав администратора - отрицательный случай"""
        result = self.admin_system.is_admin(self.regular_user_id)
        self.assertFalse(result)
    
    def test_is_admin_nonexistent_user(self):
        """Тест проверки прав для несуществующего пользователя"""
        result = self.admin_system.is_admin(999999999)
        self.assertFalse(result)
    
    def test_register_user(self):
        """Тест регистрации нового пользователя"""
        new_user_id = 555555555
        result = self.admin_system.register_user(new_user_id, "new_user", "New User")
        self.assertTrue(result)
        
        # Проверяем, что пользователь создан
        user = self.admin_system.get_user_by_username("new_user")
        self.assertIsNotNone(user)
        self.assertEqual(user['id'], new_user_id)
        self.assertFalse(user['is_admin'])
    
    def test_register_existing_user(self):
        """Тест регистрации существующего пользователя"""
        result = self.admin_system.register_user(self.admin_user_id, "admin_user", "Admin")
        self.assertTrue(result)  # Должен вернуть True для существующего пользователя
    
    def test_get_user_by_username(self):
        """Тест поиска пользователя по username"""
        user = self.admin_system.get_user_by_username("admin_user")
        self.assertIsNotNone(user)
        self.assertEqual(user['id'], self.admin_user_id)
        self.assertTrue(user['is_admin'])
    
    def test_get_user_by_username_with_at(self):
        """Тест поиска пользователя по username с символом @"""
        user = self.admin_system.get_user_by_username("@admin_user")
        self.assertIsNotNone(user)
        self.assertEqual(user['id'], self.admin_user_id)
    
    def test_get_user_by_username_not_found(self):
        """Тест поиска несуществующего пользователя"""
        user = self.admin_system.get_user_by_username("nonexistent")
        self.assertIsNone(user)
    
    def test_update_balance(self):
        """Тест обновления баланса пользователя"""
        new_balance = self.admin_system.update_balance(self.regular_user_id, 100.0)
        self.assertEqual(new_balance, 100.0)
        
        # Проверяем отрицательное изменение
        new_balance = self.admin_system.update_balance(self.regular_user_id, -50.0)
        self.assertEqual(new_balance, 50.0)
    
    def test_update_balance_nonexistent_user(self):
        """Тест обновления баланса несуществующего пользователя"""
        result = self.admin_system.update_balance(999999999, 100.0)
        self.assertIsNone(result)
    
    def test_set_admin_status(self):
        """Тест установки статуса администратора"""
        result = self.admin_system.set_admin_status(self.regular_user_id, True)
        self.assertTrue(result)
        
        # Проверяем, что статус изменился
        is_admin = self.admin_system.is_admin(self.regular_user_id)
        self.assertTrue(is_admin)
    
    def test_set_admin_status_nonexistent_user(self):
        """Тест установки статуса администратора для несуществующего пользователя"""
        result = self.admin_system.set_admin_status(999999999, True)
        self.assertFalse(result)
    
    def test_get_users_count(self):
        """Тест получения количества пользователей"""
        count = self.admin_system.get_users_count()
        self.assertEqual(count, 2)  # admin_user и regular_user
    
    def test_add_transaction(self):
        """Тест добавления транзакции"""
        transaction_id = self.admin_system.add_transaction(
            self.regular_user_id, 100.0, 'add', self.admin_user_id
        )
        self.assertIsNotNone(transaction_id)
        self.assertIsInstance(transaction_id, int)


class TestAdminDecorator(unittest.IsolatedAsyncioTestCase):
    """Тесты для декоратора admin_required"""
    
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
    
    async def test_admin_decorator_allows_admin(self):
        """Тест декоратора - разрешает доступ администратору"""
        @admin_required(self.admin_system)
        async def test_command(update, context):
            return "success"
        
        # Создаем мок объекты
        user = Mock(spec=User)
        user.id = self.admin_user_id
        user.username = "admin_user"
        
        message = Mock(spec=Message)
        message.reply_text = AsyncMock()
        
        update = Mock(spec=Update)
        update.effective_user = user
        update.message = message
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Выполняем команду
        result = await test_command(update, context)
        
        # Проверяем результат
        self.assertEqual(result, "success")
        message.reply_text.assert_not_called()
    
    async def test_admin_decorator_blocks_regular_user(self):
        """Тест декоратора - блокирует доступ обычному пользователю"""
        @admin_required(self.admin_system)
        async def test_command(update, context):
            return "success"
        
        # Создаем мок объекты
        user = Mock(spec=User)
        user.id = self.regular_user_id
        user.username = "regular_user"
        
        message = Mock(spec=Message)
        message.reply_text = AsyncMock()
        
        update = Mock(spec=Update)
        update.effective_user = user
        update.message = message
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Выполняем команду
        result = await test_command(update, context)
        
        # Проверяем результат
        self.assertIsNone(result)
        message.reply_text.assert_called_once()
        
        # Проверяем, что было отправлено сообщение об ошибке доступа
        call_args = message.reply_text.call_args[0][0]
        self.assertIn("У вас нет прав администратора", call_args)
    
    async def test_admin_decorator_handles_no_user(self):
        """Тест декоратора - обрабатывает отсутствие пользователя"""
        @admin_required(self.admin_system)
        async def test_command(update, context):
            return "success"
        
        # Создаем мок объекты без пользователя
        message = Mock(spec=Message)
        message.reply_text = AsyncMock()
        
        update = Mock(spec=Update)
        update.effective_user = None
        update.message = message
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Выполняем команду
        result = await test_command(update, context)
        
        # Проверяем результат
        self.assertIsNone(result)
        message.reply_text.assert_called_once()
        
        # Проверяем, что было отправлено сообщение об ошибке
        call_args = message.reply_text.call_args[0][0]
        self.assertIn("Не удалось определить пользователя", call_args)


if __name__ == '__main__':
    unittest.main()
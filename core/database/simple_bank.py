"""
Простая банковская система для обработки результатов парсинга
"""

import structlog
from sqlalchemy.orm import Session
from database.database import User, Transaction
from utils.core.user_manager import UserManager
from core.parsers.simple_parser import ParsedFishing
from typing import Optional, Dict

logger = structlog.get_logger()


class SimpleBankSystem:
    """Простая банковская система"""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_manager = UserManager(db)
    
    def process_fishing_result(self, fishing_result: ParsedFishing) -> Dict:
        """
        Обрабатывает результат парсинга рыбалки и начисляет монеты
        
        Args:
            fishing_result: Результат парсинга рыбалки
            
        Returns:
            Словарь с результатом операции
        """
        try:
            # Получаем или создаем пользователя по имени
            user = self.user_manager.get_or_create_user_by_name(fishing_result.fisher_name)
            
            if not user:
                logger.error(f"Не удалось найти или создать пользователя: {fishing_result.fisher_name}")
                return {
                    'success': False,
                    'error': f'Пользователь не найден: {fishing_result.fisher_name}',
                    'fisher_name': fishing_result.fisher_name
                }
            
            # Сохраняем старый баланс
            old_balance = user.balance
            
            # Начисляем монеты (1:1 конвертация)
            user.balance += fishing_result.coins
            
            # Создаем запись транзакции
            transaction = Transaction(
                user_id=user.id,
                amount=fishing_result.coins,
                transaction_type='fishing_reward',
                description=f'Рыбалка Shmalala: {fishing_result.fisher_name}',
                metadata={
                    'source': 'shmalala_fishing',
                    'fisher_name': fishing_result.fisher_name,
                    'raw_message': fishing_result.raw_message
                }
            )
            
            self.db.add(transaction)
            self.db.commit()
            
            logger.info(
                "Монеты успешно начислены",
                user_id=user.id,
                fisher_name=fishing_result.fisher_name,
                coins=fishing_result.coins,
                old_balance=old_balance,
                new_balance=user.balance,
                transaction_id=transaction.id
            )
            
            return {
                'success': True,
                'user_id': user.id,
                'fisher_name': fishing_result.fisher_name,
                'coins': fishing_result.coins,
                'old_balance': old_balance,
                'new_balance': user.balance,
                'transaction_id': transaction.id
            }
            
        except Exception as e:
            logger.error(f"Ошибка при обработке результата рыбалки: {e}")
            self.db.rollback()
            return {
                'success': False,
                'error': str(e),
                'fisher_name': fishing_result.fisher_name
            }
    
    def process_message(self, text: str) -> Optional[Dict]:
        """
        Обрабатывает текст сообщения и начисляет монеты если это рыбалка
        
        Args:
            text: Текст сообщения
            
        Returns:
            Результат обработки или None если сообщение не распознано
        """
        from core.parsers.simple_parser import parse_shmalala_message
        
        # Парсим сообщение
        fishing_result = parse_shmalala_message(text)
        
        if fishing_result:
            # Обрабатываем результат
            return self.process_fishing_result(fishing_result)
        
        return None
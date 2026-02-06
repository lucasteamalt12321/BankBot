# error_handling.py
"""
Система обработки ошибок и логирования
"""
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from database.database import User, Transaction
import structlog

logger = structlog.get_logger()


class ErrorLog:
    """Модель для хранения информации об ошибках"""
    
    def __init__(self, error_type: str, message: str, traceback_info: str, 
                 user_id: Optional[int] = None, context: Optional[Dict] = None):
        self.error_type = error_type
        self.message = message
        self.traceback_info = traceback_info
        self.user_id = user_id
        self.context = context or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь для логирования"""
        return {
            'error_type': self.error_type,
            'message': self.message,
            'traceback': self.traceback_info,
            'user_id': self.user_id,
            'context': self.context,
            'timestamp': self.timestamp.isoformat()
        }


class ErrorHandlingSystem:
    """Система обработки ошибок"""
    
    def __init__(self, db: Session):
        self.db = db
        self.error_logs = []
        self.max_error_logs = 1000  # Максимальное количество хранимых ошибок в памяти
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        self.system_logger = logging.getLogger('MetaGamePlatform')
    
    def log_error(self, error: Exception, user_id: Optional[int] = None, 
                  context: Optional[Dict] = None) -> ErrorLog:
        """Логирование ошибки"""
        error_type = type(error).__name__
        message = str(error)
        traceback_info = traceback.format_exc()
        
        error_log = ErrorLog(
            error_type=error_type,
            message=message,
            traceback_info=traceback_info,
            user_id=user_id,
            context=context or {}
        )
        
        # Добавляем в список ошибок (ограничиваем размер)
        self.error_logs.append(error_log)
        if len(self.error_logs) > self.max_error_logs:
            self.error_logs.pop(0)
        
        # Логируем с помощью structlog
        logger.error(
            "System error occurred",
            error_type=error_type,
            message=message,
            user_id=user_id,
            context=context or {},
            traceback=traceback_info
        )
        
        # Также логируем с помощью стандартного логгера
        self.system_logger.error(
            f"Error: {error_type} - {message}",
            extra={
                'user_id': user_id,
                'context': context,
                'traceback': traceback_info
            }
        )
        
        return error_log
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict]:
        """Получение последних ошибок"""
        recent_errors = self.error_logs[-limit:]
        return [error.to_dict() for error in recent_errors]
    
    def get_error_statistics(self) -> Dict:
        """Получение статистики по ошибкам"""
        if not self.error_logs:
            return {
                'total_errors': 0,
                'error_types': {},
                'most_common_error': None,
                'errors_today': 0,
                'errors_this_week': 0
            }
        
        from collections import Counter
        from datetime import datetime, timedelta
        
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        
        error_types = [error.error_type for error in self.error_logs]
        type_counts = Counter(error_types)
        
        # Ошибки за сегодня
        errors_today = sum(1 for error in self.error_logs 
                          if error.timestamp.date() == today)
        
        # Ошибки за неделю
        errors_this_week = sum(1 for error in self.error_logs 
                              if error.timestamp.date() >= week_ago)
        
        most_common = type_counts.most_common(1)[0] if type_counts else (None, 0)
        
        return {
            'total_errors': len(self.error_logs),
            'error_types': dict(type_counts),
            'most_common_error': {
                'type': most_common[0],
                'count': most_common[1]
            },
            'errors_today': errors_today,
            'errors_this_week': errors_this_week
        }
    
    def handle_security_event(self, event_type: str, user_id: Optional[int] = None, 
                            details: Optional[Dict] = None) -> ErrorLog:
        """Обработка событий безопасности"""
        message = f"Security event: {event_type}"
        if details:
            message += f" - Details: {details}"
        
        error_log = ErrorLog(
            error_type='SECURITY_EVENT',
            message=message,
            traceback_info='',
            user_id=user_id,
            context={'event_type': event_type, 'details': details or {}}
        )
        
        # Добавляем в список ошибок
        self.error_logs.append(error_log)
        if len(self.error_logs) > self.max_error_logs:
            self.error_logs.pop(0)
        
        # Логируем событие безопасности
        logger.warning(
            "Security event detected",
            event_type=event_type,
            user_id=user_id,
            details=details or {}
        )
        
        return error_log
    
    def validate_input(self, input_data: str, max_length: int = 1000) -> bool:
        """Валидация входных данных"""
        if not input_data:
            self.handle_security_event('EMPTY_INPUT', context={'max_length': max_length})
            return False
        
        if len(input_data) > max_length:
            self.handle_security_event('INPUT_TOO_LONG', context={
                'input_length': len(input_data),
                'max_length': max_length
            })
            return False
        
        # Проверка на потенциальные SQL-инъекции
        sql_injection_patterns = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'SELECT', 
                                  'UNION', 'EXEC', 'SCRIPT', '<script']
        
        input_upper = input_data.upper()
        for pattern in sql_injection_patterns:
            if pattern in input_upper:
                self.handle_security_event('POTENTIAL_SQL_INJECTION', context={
                    'pattern': pattern,
                    'input': input_data[:100]  # Ограничиваем длину для безопасности
                })
                return False
        
        return True
    
    def validate_user_action(self, user_id: int, action: str, 
                           context: Optional[Dict] = None) -> bool:
        """Валидация действий пользователя"""
        # Проверяем, существует ли пользователь
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            self.handle_security_event('INVALID_USER_ACTION', user_id=user_id, 
                                     details={'action': action, 'context': context})
            return False
        
        # В реальной системе здесь будет больше проверок
        # Например: частота действий, разрешенные действия и т.д.
        
        return True
    
    def cleanup_error_logs(self, days_to_keep: int = 30) -> int:
        """Очистка старых логов ошибок из памяти"""
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        old_logs_count = len(self.error_logs)
        
        self.error_logs = [log for log in self.error_logs if log.timestamp >= cutoff_date]
        
        cleaned_count = old_logs_count - len(self.error_logs)
        
        logger.info(f"Cleaned up {cleaned_count} old error logs")
        return cleaned_count
    
    def get_error_by_type(self, error_type: str) -> List[Dict]:
        """Получение ошибок определенного типа"""
        matching_errors = [error for error in self.error_logs 
                          if error.error_type == error_type]
        return [error.to_dict() for error in matching_errors]


class ErrorHandler:
    """Обработчик ошибок для использования в других модулях"""
    
    def __init__(self, error_system: ErrorHandlingSystem):
        self.error_system = error_system
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Логируем исключение
            self.error_system.log_error(exc_val)
            # Возвращаем False, чтобы исключение продолжило всплытие
            return False
        return True
    
    def safe_execute(self, func, *args, user_id: Optional[int] = None, 
                     context: Optional[Dict] = None, **kwargs):
        """Безопасное выполнение функции с перехватом ошибок"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.error_system.log_error(e, user_id=user_id, context=context)
            # Возвращаем None или можно возвращать специальное значение ошибки
            return None
# monitoring_system.py
"""
Система мониторинга и алертов
"""
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil
import time
from datetime import datetime
from sqlalchemy.orm import Session
from database.database import User, Transaction
import structlog
from typing import Dict, List, Optional

logger = structlog.get_logger()


class MonitoringSystem:
    """Система мониторинга и алертов"""
    
    def __init__(self, db: Session):
        self.db = db
        self.alert_system = {
            'transaction_anomalies': True,      # Аномальные транзакции
            'system_errors': True,              # Критические ошибки
            'performance_issues': True,         # Проблемы производительности
            'security_events': True,            # Подозрительная активность
            'business_metrics': True            # Ключевые бизнес-метрики
        }
        
        self.performance_targets = {
            'message_processing': 2.0,          # < 2 секунд
            'command_response': 1.0,            # < 1 секунды
            'concurrent_users': 100,            # 100+ пользователей
            'daily_messages': 500,              # 500+ сообщений в день
            'database_size_limit': 10 * 1024 * 1024 * 1024,  # 10GB в байтах
            'uptime_target': 0.999              # 99.9% аптайм
        }
        
        self.monitoring_metrics = {
            'system_health': ['cpu', 'memory', 'disk', 'network'],
            'business_metrics': ['active_users', 'transactions', 'revenue'],
            'performance_metrics': ['response_time', 'error_rate', 'throughput'],
            'security_metrics': ['failed_logins', 'suspicious_activities']
        }
    
    def get_system_health(self) -> Dict:
        """Получение состояния системы"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        
        return {
            'timestamp': datetime.utcnow(),
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count()
            },
            'memory': {
                'percent': memory.percent,
                'total': memory.total,
                'available': memory.available,
                'used': memory.used
            },
            'disk': {
                'percent': disk.percent,
                'total': disk.total,
                'used': disk.used,
                'free': disk.free
            },
            'network': {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            },
            'processes': len(psutil.pids())
        }
    
    def get_business_metrics(self) -> Dict:
        """Получение бизнес-метрик"""
        total_users = self.db.query(User).count()
        today = datetime.utcnow().date()
        
        # Транзакции за сегодня
        from sqlalchemy import func
        today_transactions = self.db.query(Transaction).filter(
            func.date(Transaction.created_at) == today
        ).count()
        
        # Общая сумма транзакций
        total_amount = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.created_at >= today
        ).scalar() or 0
        
        # Активные пользователи за сегодня
        active_users = self.db.query(User).filter(
            User.last_activity >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        return {
            'total_users': total_users,
            'active_users_today': active_users,
            'today_transactions': today_transactions,
            'today_revenue': total_amount,
            'average_balance': self.db.query(func.avg(User.balance)).scalar() or 0
        }
    
    def check_performance_metrics(self) -> Dict:
        """Проверка метрик производительности"""
        # Проверяем производительность системы
        start_time = time.time()
        
        # Простая проверка производительности БД
        test_query_start = time.time()
        user_count = self.db.query(User).count()
        db_query_time = time.time() - test_query_start
        
        total_time = time.time() - start_time
        
        performance_issues = []
        
        if db_query_time > self.performance_targets['message_processing']:
            performance_issues.append(f"DB query time too high: {db_query_time:.2f}s")
        
        return {
            'total_check_time': total_time,
            'db_query_time': db_query_time,
            'user_count': user_count,
            'performance_issues': performance_issues,
            'is_within_limits': len(performance_issues) == 0
        }
    
    def get_security_metrics(self) -> Dict:
        """Получение метрик безопасности"""
        # В реальной системе здесь будет проверка логов безопасности
        # Пока возвращаем заглушку
        return {
            'failed_logins': 0,
            'suspicious_activities': 0,
            'security_warnings': 0,
            'last_security_check': datetime.utcnow()
        }
    
    def get_all_metrics(self) -> Dict:
        """Получение всех метрик"""
        return {
            'system_health': self.get_system_health(),
            'business_metrics': self.get_business_metrics(),
            'performance_metrics': self.check_performance_metrics(),
            'security_metrics': self.get_security_metrics()
        }
    
    def check_alerts(self) -> List[Dict]:
        """Проверка алертов и тревожных ситуаций"""
        alerts = []
        
        # Проверка метрик системы
        health = self.get_system_health()
        
        if health['cpu']['percent'] > 90:
            alerts.append({
                'type': 'high_cpu',
                'level': 'warning',
                'message': f"Высокая загрузка CPU: {health['cpu']['percent']}%",
                'timestamp': datetime.utcnow()
            })
        
        if health['memory']['percent'] > 90:
            alerts.append({
                'type': 'high_memory',
                'level': 'warning',
                'message': f"Высокое использование памяти: {health['memory']['percent']}%",
                'timestamp': datetime.utcnow()
            })
        
        # Проверка бизнес-метрик
        business = self.get_business_metrics()
        
        if business['today_transactions'] == 0:
            alerts.append({
                'type': 'no_transactions',
                'level': 'info',
                'message': "Нет транзакций за сегодня",
                'timestamp': datetime.utcnow()
            })
        
        return alerts
    
    def log_system_event(self, event_type: str, severity: str, message: str, data: Dict = None):
        """Логирование системного события"""
        logger.info(
            "System event",
            event_type=event_type,
            severity=severity,
            message=message,
            data=data or {}
        )
    
    def get_uptime(self) -> float:
        """Расчет аптайма системы (в реальной системе это будет сложнее)"""
        # Временная заглушка - в реальной системе нужно отслеживать время запуска
        return 0.999


class AlertSystem:
    """Система алертов"""
    
    def __init__(self, monitoring_system: MonitoringSystem):
        self.monitoring_system = monitoring_system
        self.active_alerts = []
        self.alert_history = []
    
    def check_and_send_alerts(self):
        """Проверка и отправка алертов"""
        alerts = self.monitoring_system.check_alerts()
        
        for alert in alerts:
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            
            # Логируем алерт
            self.monitoring_system.log_system_event(
                event_type=alert['type'],
                severity=alert['level'],
                message=alert['message'],
                data={'timestamp': alert['timestamp']}
            )
    
    def get_active_alerts(self) -> List[Dict]:
        """Получение активных алертов"""
        return self.active_alerts
    
    def clear_alert(self, alert_type: str):
        """Очистка алерта"""
        self.active_alerts = [a for a in self.active_alerts if a['type'] != alert_type]
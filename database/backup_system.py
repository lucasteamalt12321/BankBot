# backup_system.py
"""
Система резервного копирования
"""
import shutil
import os
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List
import structlog

logger = structlog.get_logger()


class BackupSystem:
    """Система резервного копирования"""
    
    def __init__(self, db_path: str = "bot.db", backup_dir: str = "backups"):
        self.db_path = db_path
        self.backup_dir = backup_dir
        
        # Создаем директорию бэкапов если её нет
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_backup(self) -> Dict:
        """Создание резервной копии базы данных"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}.zip"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Создаем ZIP архив с базой данных
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(self.db_path, os.path.basename(self.db_path))
            
            file_size = os.path.getsize(backup_path)
            
            result = {
                'success': True,
                'backup_file': backup_path,
                'timestamp': timestamp,
                'size': file_size,
                'message': f'Резервная копия создана: {backup_filename}'
            }
            
            logger.info("Backup created", backup_file=backup_path, size=file_size)
            return result
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'message': f'Ошибка при создании резервной копии: {str(e)}'
            }
            logger.error("Backup creation failed", error=str(e))
            return error_result
    
    def list_backups(self) -> List[Dict]:
        """Получение списка доступных резервных копий"""
        backups = []
        
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.zip') and filename.startswith('backup_'):
                filepath = os.path.join(self.backup_dir, filename)
                timestamp_str = filename.replace('backup_', '').replace('.zip', '')
                
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    size = os.path.getsize(filepath)
                    
                    backups.append({
                        'filename': filename,
                        'filepath': filepath,
                        'timestamp': timestamp,
                        'size': size
                    })
                except ValueError:
                    # Если не удается распознать формат даты, пропускаем файл
                    continue
        
        # Сортируем по дате (новые первыми)
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return backups
    
    def restore_backup(self, backup_filename: str) -> Dict:
        """Восстановление из резервной копии"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            if not os.path.exists(backup_path):
                return {
                    'success': False,
                    'message': f'Файл резервной копии не найден: {backup_filename}'
                }
            
            # Извлекаем базу данных из архива
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                # Проверяем, что в архиве есть нужный файл
                if os.path.basename(self.db_path) not in zipf.namelist():
                    return {
                        'success': False,
                        'message': 'Файл базы данных не найден в архиве'
                    }
                
                # Извлекаем файл во временный каталог
                temp_extract_dir = os.path.join(self.backup_dir, 'temp_restore')
                os.makedirs(temp_extract_dir, exist_ok=True)
                
                zipf.extractall(temp_extract_dir)
                
                # Перемещаем файл базы данных на место
                extracted_db_path = os.path.join(temp_extract_dir, os.path.basename(self.db_path))
                
                # Создаем резервную копию текущей базы данных перед восстановлением
                if os.path.exists(self.db_path):
                    current_backup = f"{self.db_path}.backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(self.db_path, current_backup)
                
                # Копируем восстановленную базу данных
                shutil.move(extracted_db_path, self.db_path)
                
                # Удаляем временный каталог
                shutil.rmtree(temp_extract_dir)
            
            logger.info("Backup restored", backup_file=backup_filename)
            return {
                'success': True,
                'message': f'База данных восстановлена из резервной копии: {backup_filename}'
            }
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'message': f'Ошибка при восстановлении: {str(e)}'
            }
            logger.error("Backup restoration failed", error=str(e))
            return error_result
    
    def cleanup_old_backups(self, keep_days: int = 7) -> Dict:
        """Удаление старых резервных копий"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
            deleted_count = 0
            total_size_freed = 0
            
            for filename in os.listdir(self.backup_dir):
                if filename.endswith('.zip') and filename.startswith('backup_'):
                    filepath = os.path.join(self.backup_dir, filename)
                    timestamp_str = filename.replace('backup_', '').replace('.zip', '')
                    
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        
                        if timestamp < cutoff_date:
                            file_size = os.path.getsize(filepath)
                            os.remove(filepath)
                            deleted_count += 1
                            total_size_freed += file_size
                            
                    except ValueError:
                        # Если не удается распознать формат даты, пропускаем файл
                        continue
            
            result = {
                'success': True,
                'deleted_count': deleted_count,
                'size_freed': total_size_freed,
                'message': f'Удалено {deleted_count} старых резервных копий'
            }
            
            logger.info("Old backups cleaned up", deleted_count=deleted_count, size_freed=total_size_freed)
            return result
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'message': f'Ошибка при очистке старых резервных копий: {str(e)}'
            }
            logger.error("Backup cleanup failed", error=str(e))
            return error_result
    
    def get_backup_info(self, backup_filename: str) -> Dict:
        """Получение информации о резервной копии"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            if not os.path.exists(backup_path):
                return {
                    'success': False,
                    'message': f'Файл резервной копии не найден: {backup_filename}'
                }
            
            # Получаем информацию о файле
            stat = os.stat(backup_path)
            timestamp_str = backup_filename.replace('backup_', '').replace('.zip', '')
            
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                timestamp = datetime.fromtimestamp(stat.st_mtime)
            
            # Получаем информацию из ZIP файла
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                file_list = zipf.namelist()
                file_info = []
                
                for file in file_list:
                    info = zipf.getinfo(file)
                    file_info.append({
                        'name': file,
                        'size': info.file_size,
                        'compressed_size': info.compress_size
                    })
            
            return {
                'success': True,
                'filename': backup_filename,
                'filepath': backup_path,
                'timestamp': timestamp,
                'size': stat.st_size,
                'file_count': len(file_list),
                'files': file_info
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Ошибка при получении информации о резервной копии: {str(e)}'
            }


# Функция для выполнения резервного копирования по расписанию
def scheduled_backup(db_path: str = "bot.db", backup_dir: str = "backups"):
    """Функция для выполнения регулярного резервного копирования"""
    backup_system = BackupSystem(db_path, backup_dir)
    result = backup_system.create_backup()
    
    if result['success']:
        logger.info("Scheduled backup completed", backup_file=result['backup_file'])
    else:
        logger.error("Scheduled backup failed", error=result['message'])
    
    return result
#!/usr/bin/env python3
# kill_bot_processes.py - скрипт для завершения старых процессов бота

import psutil
import os
import time

def kill_existing_bot_processes():
    """Убивает все существующие процессы, связанные с ботом"""
    current_pid = os.getpid()
    killed_processes = []
    
    print(f"Поиск старых процессов бота (текущий PID: {current_pid})...")
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Получаем командную строку процесса
            cmdline = proc.info['cmdline']
            if cmdline and len(cmdline) > 1:  # Убедимся, что есть хотя бы exe и аргумент
                cmdline_str = ' '.join(cmdline)
                # Проверяем, содержит ли команда запуск main.py
                if 'main.py' in cmdline_str and 'python' in cmdline_str.lower():
                    pid = proc.info['pid']
                    if pid != current_pid:
                        print(f"Найден старый процесс бота с PID {pid}, убиваю...")
                        proc.terminate()  # Плавное завершение
                        killed_processes.append((pid, proc))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    # Ждем завершения процессов или убиваем жестко
    for pid, proc in killed_processes:
        try:
            proc.wait(timeout=5)  # Ждем до 5 секунд
            print(f"Процесс {pid} завершен корректно")
        except psutil.TimeoutExpired:
            print(f"Процесс {pid} не завершился, убиваю жестко...")
            proc.kill()  # Жесткое завершение
            print(f"Процесс {pid} убит жестко")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"Процесс {pid} уже не существует или нет доступа")
    
    if killed_processes:
        print(f"Убито {len(killed_processes)} старых процессов бота")
        time.sleep(2)  # Даем время для полного завершения
    else:
        print("Старые процессы бота не найдены")

if __name__ == "__main__":
    kill_existing_bot_processes()
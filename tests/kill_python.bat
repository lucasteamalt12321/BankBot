@echo off
echo Stopping all Python processes...
taskkill /f /im python.exe /t 2>nul
taskkill /f /im pythonw.exe /t 2>nul
echo Done.
timeout /t 2 /nobreak >nul
Инструкция по развёртыванию зеркала на Amvera

1. Регистрируемся на https://amvera.ru/
2. Создаём проект «Импорт из Git» → выбираем репозиторий lucasteamalt12321/BankBot, ветка main
3. Amvera автоматически использует amvera.yml + Dockerfile. Конфиг уже есть в репозитории (8b3f876)
4. Переносим переменные окружения (Settings → Environment):
   - DATABASE_URL
   - BOT_TOKEN
   - WEBHOOK_SECRET
   - TELEGRAM_ADMIN_IDS (если нужен)
   - и остальные секреты из прод-конфига
5. Нажимаем «Деплой». После сборки получим домен вида https://<app>-<user>.amvera.cloud
6. Проверка: https://<домен>/health → 200
7. Для обратного вебхука Telegram можно указать этот домен вместо lthub.vercel.app (если хотим переключить зеркало)

Готовность: Procfile (gunicorn + wsgi:app) уже есть, requirements.txt содержит gunicorn==23.0.0, wsgi.py импортирует app. Локальная проверка wsgi пройдена (/health 200).

amvera.yml использует ${PORT} — совместимо с Amvera.

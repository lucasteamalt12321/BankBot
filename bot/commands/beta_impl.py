"""
Beta Commands Implementation
Minimal working implementation of 27 beta commands
"""

import logging
import random
from telegram import Update
from telegram.ext import ContextTypes
from typing import Optional
from database.database import get_db

logger = logging.getLogger(__name__)


class BetaCommandsImpl:
    """Implementation of beta commands"""
    
    def __init__(self):
        self.db_path = "data/bot.db"
    
    def _get_user_id(self, telegram_id: int) -> Optional[int]:
        """Get internal user ID from telegram ID"""
        db = next(get_db())
        try:
            from database.database import User
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            return user.id if user else None
        finally:
            db.close()
    
    # ============================================
    # ЭКОНОМИКА И ТОРГОВЛЯ
    # ============================================
    
    async def market_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /market - рыночная площадка"""
        text = """
🏪 <b>Рыночная площадка</b>

📦 <b>Активные предложения:</b>

Рынок пока пуст. Станьте первым продавцом!

💡 <b>Как продать:</b>
/sell "Название предмета" 100

📊 <b>Статистика рынка:</b>
• Всего сделок: 0
• Активных объявлений: 0
• Средняя цена: -

🔜 <b>Скоро:</b> Фильтры, поиск, категории
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def sell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /sell - выставить предмет на продажу"""
        if not context.args or len(context.args) < 2:
            text = """
❌ <b>Неверный формат!</b>

<b>Использование:</b>
/sell "Название" цена

<b>Примеры:</b>
/sell "Премиум стикеры" 150
/sell "VIP статус" 500

💡 Комиссия: 5% от суммы продажи
        """
            await update.message.reply_text(text, parse_mode='HTML')
            return
        
        # Парсинг аргументов
        try:
            # Простая реализация - последний аргумент это цена
            price = float(context.args[-1])
            item_name = ' '.join(context.args[:-1]).strip('"\'')
            
            text = f"""
✅ <b>Объявление создано!</b>

📦 <b>Товар:</b> {item_name}
💰 <b>Цена:</b> {price} монет
💸 <b>Комиссия:</b> {price * 0.05:.1f} монет
💵 <b>Вы получите:</b> {price * 0.95:.1f} монет

⏰ <b>Срок:</b> 7 дней
🔔 Вы получите уведомление при покупке

🔜 <b>Функция в разработке</b>
Объявление пока не сохранено в базе
            """
            await update.message.reply_text(text, parse_mode='HTML')
            
        except ValueError:
            await update.message.reply_text("❌ Неверная цена! Укажите число.")

    
    async def trade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /trade - предложить обмен"""
        if not context.args:
            text = """
🤝 <b>Система обмена</b>

<b>Использование:</b>
/trade @username

<b>Как это работает:</b>
1. Вы предлагаете обмен пользователю
2. Открывается окно обмена
3. Обе стороны добавляют предметы/монеты
4. Обе стороны подтверждают
5. Обмен завершается

⏰ <b>Таймаут:</b> 5 минут
🔒 <b>Безопасность:</b> Атомарная транзакция

🔜 <b>Функция в разработке</b>
            """
            await update.message.reply_text(text, parse_mode='HTML')
            return
        
        partner = context.args[0].lstrip('@')
        text = f"""
🤝 <b>Предложение обмена</b>

👤 <b>Партнер:</b> @{partner}

⏳ Ожидание подтверждения...

🔜 <b>Функция в разработке</b>
Обмен пока недоступен
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def loan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /loan - взять кредит"""
        if not context.args:
            text = """
🏦 <b>Кредитная система</b>

<b>Использование:</b>
/loan сумма

<b>Условия:</b>
• Процент: 10% в неделю
• Максимум: 3 активных кредита
• Лимит зависит от репутации

<b>Ваш лимит:</b> 1000 монет
<b>Кредитный рейтинг:</b> ⭐⭐⭐ (Хороший)

<b>Пример:</b>
/loan 500
→ Через неделю вернуть: 550 монет

🔜 <b>Функция в разработке</b>
            """
            await update.message.reply_text(text, parse_mode='HTML')
            return
        
        try:
            amount = float(context.args[0])
            interest = amount * 0.10
            total = amount + interest
            
            text = f"""
🏦 <b>Заявка на кредит</b>

💰 <b>Сумма:</b> {amount} монет
📈 <b>Процент:</b> {interest} монет (10%)
💵 <b>К возврату:</b> {total} монет

📅 <b>Срок:</b> 7 дней
⚠️ <b>Штраф за просрочку:</b> +5% в день

🔜 <b>Функция в разработке</b>
Кредит пока недоступен
            """
            await update.message.reply_text(text, parse_mode='HTML')
            
        except ValueError:
            await update.message.reply_text("❌ Неверная сумма! Укажите число.")
    
    async def repay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /repay - погасить кредит"""
        text = """
💳 <b>Погашение кредитов</b>

📊 <b>Активные кредиты:</b>
У вас нет активных кредитов

<b>Использование:</b>
/repay сумма - частичное погашение
/repay all - погасить все

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def invest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /invest - инвестировать монеты"""
        if len(context.args) < 2:
            text = """
📈 <b>Инвестиционная система</b>

<b>Использование:</b>
/invest сумма срок

<b>Доступные сроки:</b>
• 1d - 1 день (5% прибыль)
• 3d - 3 дня (8% прибыль)
• 7d - 7 дней (12% прибыль)
• 30d - 30 дней (15% прибыль)

<b>Пример:</b>
/invest 1000 7d
→ Через 7 дней получите: 1120 монет

⚠️ Досрочное снятие - потеря процентов

🔜 <b>Функция в разработке</b>
            """
            await update.message.reply_text(text, parse_mode='HTML')
            return
        
        try:
            amount = float(context.args[0])
            term = context.args[1].lower()
            
            rates = {'1d': 0.05, '3d': 0.08, '7d': 0.12, '30d': 0.15}
            if term not in rates:
                await update.message.reply_text("❌ Неверный срок! Используйте: 1d, 3d, 7d, 30d")
                return
            
            profit = amount * rates[term]
            total = amount + profit
            
            text = f"""
📈 <b>Инвестиция создана</b>

💰 <b>Сумма:</b> {amount} монет
⏰ <b>Срок:</b> {term}
📊 <b>Прибыль:</b> {profit} монет ({rates[term]*100}%)
💵 <b>Итого:</b> {total} монет

📅 <b>Дата возврата:</b> {term}

🔜 <b>Функция в разработке</b>
Инвестиция пока недоступна
            """
            await update.message.reply_text(text, parse_mode='HTML')
            
        except ValueError:
            await update.message.reply_text("❌ Неверная сумма! Укажите число.")
    
    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /portfolio - инвестиционный портфель"""
        text = """
💼 <b>Инвестиционный портфель</b>

📈 <b>Активные депозиты:</b>
Нет активных депозитов

💳 <b>Активные кредиты:</b>
Нет активных кредитов

📊 <b>Итого:</b>
• Инвестировано: 0 монет
• Ожидаемый доход: 0 монет
• Долг: 0 монет
• Чистая позиция: 0 монет

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')

    
    # ============================================
    # КВЕСТЫ И ЗАДАНИЯ
    # ============================================
    
    async def quests_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /quests - доступные квесты"""
        text = """
🎯 <b>Доступные квесты</b>

📅 <b>Ежедневные квесты:</b>
1. Первые шаги - Заработайте 100 монет
   Награда: 50 монет
   
2. Покупатель - Купите 3 предмета
   Награда: 75 монет
   
3. Социальный - Добавьте 1 друга
   Награда: 100 монет

📆 <b>Еженедельные квесты:</b>
4. Игрок - Выиграйте 5 игр
   Награда: 250 монет
   
5. Постоянство - Заходите 7 дней подряд
   Награда: 500 монет + значок "Трудяга"

<b>Использование:</b>
/quest_start номер - начать квест

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def quest_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /quest_start - начать квест"""
        if not context.args:
            await update.message.reply_text("❌ Укажите номер квеста: /quest_start 1")
            return
        
        quest_id = context.args[0]
        text = f"""
✅ <b>Квест активирован!</b>

🎯 <b>Квест #{quest_id}:</b> Первые шаги
📝 <b>Задание:</b> Заработайте 100 монет
🎁 <b>Награда:</b> 50 монет

📊 <b>Прогресс:</b> 0/100 (0%)

Используйте /quest_progress для отслеживания

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def quest_progress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /quest_progress - прогресс по квестам"""
        text = """
📊 <b>Прогресс по квестам</b>

🎯 <b>Активные квесты:</b>

1. Первые шаги
   Прогресс: 0/100 (0%)
   Награда: 50 монет

<b>Всего активных:</b> 1/5

💡 Максимум 5 активных квестов одновременно

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def quest_complete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /quest_complete - завершить квест"""
        if not context.args:
            await update.message.reply_text("❌ Укажите номер квеста: /quest_complete 1")
            return
        
        quest_id = context.args[0]
        text = f"""
🎉 <b>Квест завершен!</b>

✅ <b>Квест #{quest_id}:</b> Первые шаги

🎁 <b>Награды:</b>
• +50 монет
• +10 опыта

🔓 <b>Разблокировано:</b>
• Новый квест "Покупатель"

🔜 <b>Функция в разработке</b>
Награды пока не начисляются
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def quest_history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /quest_history - история квестов"""
        text = """
📜 <b>История квестов</b>

✅ <b>Выполнено квестов:</b> 0

🎁 <b>Получено наград:</b>
• Монеты: 0
• Значки: 0
• Опыт: 0

📊 <b>Статистика:</b>
• Процент выполнения: 0%
• Любимая категория: -

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')

    
    # ============================================
    # РЕЙТИНГИ И СОРЕВНОВАНИЯ
    # ============================================
    
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /leaderboard - таблица лидеров"""
        category = context.args[0] if context.args else 'balance'
        
        text = f"""
🏆 <b>Таблица лидеров</b>
<b>Категория:</b> {category}

<b>Топ-10:</b>
1. 👑 @user1 - 15000 монет
2. 🥈 @user2 - 12000 монет
3. 🥉 @user3 - 10000 монет
4. @user4 - 8500 монет
5. @user5 - 7200 монет
6. @user6 - 6800 монет
7. @user7 - 5900 монет
8. @user8 - 5100 монет
9. @user9 - 4700 монет
10. @user10 - 4200 монет

<b>Ваша позиция:</b> #15 (3450 монет)

<b>Категории:</b>
/leaderboard balance - по балансу
/leaderboard activity - по активности
/leaderboard achievements - по достижениям

🔜 <b>Функция в разработке</b>
Данные тестовые
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def rank_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /rank - ваш ранг"""
        text = """
⭐ <b>Ваш ранг</b>

🎖️ <b>Текущий ранг:</b> Игрок (уровень 2)

📊 <b>Прогресс:</b>
▓▓▓▓▓▓▓░░░ 3450/5000 монет (69%)

<b>До следующего ранга:</b> 1550 монет

<b>Система рангов:</b>
1. 🆕 Новичок (0-999)
2. 🎮 Игрок (1000-4999) ← Вы здесь
3. 🏅 Ветеран (5000-9999)
4. 💎 Эксперт (10000-24999)
5. 🌟 Мастер (25000-49999)
6. 👑 Легенда (50000+)

<b>Бонусы ранга "Игрок":</b>
• +5% к доходу от игр
• Доступ к специальным квестам
• Скидка 10% в магазине

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def compare_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /compare - сравнить статистику"""
        if not context.args:
            await update.message.reply_text("❌ Укажите пользователя: /compare @username")
            return
        
        partner = context.args[0].lstrip('@')
        text = f"""
📊 <b>Сравнение с @{partner}</b>

💰 <b>Баланс:</b>
   Вы: 3450 монет
   @{partner}: 5200 монет ✓

🏆 <b>Достижения:</b>
   Вы: 12 ✓
   @{partner}: 8

📈 <b>Активность:</b>
   Вы: 87%
   @{partner}: 92% ✓

🎮 <b>Игры:</b>
   Вы: 45 побед
   @{partner}: 38 побед ✓

👥 <b>Друзья:</b>
   Общих друзей: 3

🔜 <b>Функция в разработке</b>
Данные тестовые
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def tournament_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /tournament - текущие турниры"""
        text = """
🏆 <b>Текущие турниры</b>

<b>Активные турниры:</b>

1. 🎮 Еженедельный турнир по мини-играм
   💰 Призовой фонд: 10000 монет
   👥 Участников: 47/100
   📅 Начало: через 2 дня
   🎁 Призы: 1-е место 5000, 2-е 3000, 3-е 2000
   
   /tournament_join 1 - участвовать

2. 🎲 D&D Чемпионат
   💰 Призовой фонд: 5000 монет
   👥 Участников: 23/50
   📅 Начало: через 5 дней
   
   /tournament_join 2 - участвовать

<b>Правила:</b>
• Регистрация до начала турнира
• Автоматическое составление пар
• Уведомления о матчах

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def tournament_join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /tournament_join - участвовать в турнире"""
        if not context.args:
            await update.message.reply_text("❌ Укажите номер турнира: /tournament_join 1")
            return
        
        tournament_id = context.args[0]
        text = f"""
✅ <b>Регистрация на турнир</b>

🏆 <b>Турнир #{tournament_id}:</b> Еженедельный турнир
💰 <b>Призовой фонд:</b> 10000 монет
👥 <b>Участников:</b> 48/100

📅 <b>Ваш первый матч:</b>
Дата: 22.02.2026 в 18:00
Противник: будет определен

🔔 Вы получите уведомление за 1 час до начала

🔜 <b>Функция в разработке</b>
Регистрация пока недоступна
        """
        await update.message.reply_text(text, parse_mode='HTML')

    
    # ============================================
    # ПЕРСОНАЛИЗАЦИЯ
    # ============================================
    
    async def customize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /customize - настройки профиля"""
        text = """
🎨 <b>Настройки профиля</b>

<b>Текущие настройки:</b>
• Титул: Игрок
• Значок: 🎮
• Тема: classic
• Статус: Активен
• Описание: не установлено

<b>Доступные команды:</b>
/title название - изменить титул
/badge - управление значками
/theme название - изменить тему

<b>Приватность:</b>
• Профиль: Публичный
• Статистика: Публичная
• Инвентарь: Скрытый

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def title_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /title - установить титул"""
        if not context.args:
            text = """
👑 <b>Управление титулами</b>

<b>Ваши титулы:</b>
✅ Новичок (активен)
✅ Игрок
🔒 Торговец (требуется: 100 сделок)
🔒 Инвестор (требуется: 10000 монет в депозитах)
🔒 Легенда (требуется: все достижения)

<b>Использование:</b>
/title Игрок - установить титул

🔜 <b>Функция в разработке</b>
            """
            await update.message.reply_text(text, parse_mode='HTML')
            return
        
        title = ' '.join(context.args)
        text = f"""
✅ <b>Титул изменен!</b>

👑 <b>Новый титул:</b> {title}

Теперь он отображается в вашем профиле

🔜 <b>Функция в разработке</b>
Титул пока не сохраняется
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def badge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /badge - управление значками"""
        text = """
🎖️ <b>Коллекция значков</b>

<b>Ваши значки (4/50):</b>

✅ 👣 Первые шаги
   Зарегистрируйтесь в системе
   
✅ 💪 Трудяга
   Заработайте 1000 монет
   
✅ 🤝 Торговец
   Совершите 50 сделок
   
✅ 📈 Инвестор (активен)
   Создайте 10 депозитов

<b>Заблокированные:</b>
🔒 🎯 Квестер - Выполните 25 квестов
🔒 👥 Социальный - Добавьте 10 друзей
🔒 🏆 Чемпион - Выиграйте турнир
🔒 🍀 Удачливый - Выиграйте в лотерею

<b>Прогресс:</b> 8% (4/50)

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def theme_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /theme - тема оформления"""
        if not context.args:
            text = """
🎨 <b>Темы оформления</b>

<b>Доступные темы:</b>

✅ classic - Классическая (активна)
   Стандартное оформление

⬜ minimal - Минималистичная
   Простой текст без эмодзи

🌈 colorful - Красочная
   Много цветов и эмодзи

🌙 dark - Темная
   Темное оформление

🕹️ retro - Ретро
   Стиль 8-bit игр

<b>Использование:</b>
/theme dark - установить тему

🔜 <b>Функция в разработке</b>
            """
            await update.message.reply_text(text, parse_mode='HTML')
            return
        
        theme = context.args[0].lower()
        text = f"""
✅ <b>Тема изменена!</b>

🎨 <b>Новая тема:</b> {theme}

Теперь все сообщения бота будут в этом стиле

🔜 <b>Функция в разработке</b>
Тема пока не применяется
        """
        await update.message.reply_text(text, parse_mode='HTML')

    
    # ============================================
    # СТАТИСТИКА И АНАЛИТИКА
    # ============================================
    
    async def activity_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /activity - график активности"""
        text = """
📊 <b>График активности</b>

<b>Последние 7 дней:</b>
Пн ▓▓▓▓▓▓▓░░░ 70%
Вт ▓▓▓▓▓▓▓▓░░ 80%
Ср ▓▓▓▓▓▓▓▓▓░ 90%
Чт ▓▓▓▓▓░░░░░ 50%
Пт ▓▓▓▓▓▓▓▓▓▓ 100%
Сб ▓▓▓▓▓▓░░░░ 60%
Вс ▓▓▓▓▓▓▓▓░░ 80%

<b>Статистика:</b>
• Средняя активность: 76%
• Самый активный день: Пятница
• Среднее время: 2.5 часа/день
• Дней подряд: 7

<b>Лучшие дни для заработка:</b>
1. Пятница - 850 монет
2. Среда - 720 монет
3. Вторник - 680 монет

🔜 <b>Функция в разработке</b>
Данные тестовые
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def income_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /income - анализ доходов"""
        text = """
💰 <b>Анализ доходов</b>

<b>За последние 30 дней:</b>

📊 <b>По источникам:</b>
🎮 Игры: 3500 монет (45%)
   ▓▓▓▓▓▓▓▓▓░░░░░░░░░░░

📝 Парсинг: 2800 монет (36%)
   ▓▓▓▓▓▓▓░░░░░░░░░░░░░

🎁 Подарки: 900 монет (12%)
   ▓▓░░░░░░░░░░░░░░░░░░

💼 Продажи: 550 монет (7%)
   ▓░░░░░░░░░░░░░░░░░░░

<b>Итого:</b> 7750 монет

<b>Тренд:</b> ↗️ +15% к прошлому месяцу

<b>Рекомендации:</b>
• Увеличьте активность в играх
• Используйте парсинг чаще
• Продавайте неиспользуемые предметы

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def expenses_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /expenses - анализ расходов"""
        text = """
💸 <b>Анализ расходов</b>

<b>За последние 30 дней:</b>

📊 <b>По категориям:</b>
🛒 Покупки: 2100 монет (60%)
   ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░

🎁 Подарки: 800 монет (23%)
   ▓▓▓▓░░░░░░░░░░░░░░░░

💳 Комиссии: 350 монет (10%)
   ▓▓░░░░░░░░░░░░░░░░░░

📦 Прочее: 250 монет (7%)
   ▓░░░░░░░░░░░░░░░░░░░

<b>Итого:</b> 3500 монет

<b>Баланс:</b> +4250 монет (доход - расход)

<b>Рекомендации:</b>
• Сократите импульсивные покупки
• Используйте скидки и акции
• Инвестируйте свободные средства

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    # ============================================
    # БОНУСЫ И СОБЫТИЯ
    # ============================================
    
    async def events_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /events - текущие события"""
        text = """
🎉 <b>Текущие события</b>

<b>Активные события:</b>

🎄 <b>Зимняя распродажа</b>
   📅 До: 31.12.2026
   🎁 Все товары -20%
   💡 Используйте /shop для покупок

🎁 <b>Двойные награды</b>
   📅 До: 25.12.2026
   ⭐ Все награды за квесты x2
   💡 Выполняйте квесты: /quests

🍀 <b>Удачная неделя</b>
   📅 До: 27.12.2026
   🎰 Шанс выигрыша в /spin увеличен x2
   💡 Крутите колесо каждый день!

<b>Скоро:</b>
🎆 Новогодний турнир (01.01.2027)
   Призовой фонд: 50000 монет!

🔜 <b>Функция в разработке</b>
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def spin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /spin - колесо фортуны"""
        
        # Простая проверка - можно крутить раз в день
        # В реальной версии проверяем в БД
        
        rewards = [
            ("10 монет", 10),
            ("25 монет", 25),
            ("50 монет", 50),
            ("100 монет", 100),
            ("250 монет", 250),
            ("500 монет", 500),
            ("1000 монет", 1000),
            ("Значок 🎁", 0),
            ("Множитель x2", 0),
        ]
        
        reward = random.choice(rewards)
        
        text = f"""
🎰 <b>Колесо фортуны</b>

🎲 Вы крутите колесо...

✨ <b>Выпало:</b> {reward[0]}! 🎉

{f"💰 +{reward[1]} монет начислено!" if reward[1] > 0 else "🎁 Награда добавлена в инвентарь!"}

⏰ <b>Следующая попытка:</b> через 24 часа

💡 <b>Совет:</b> Заходите каждый день для бонусов!

🔜 <b>Функция в разработке</b>
Награды пока не начисляются
        """
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def lottery_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /lottery - лотерея"""
        text = """
🎫 <b>Лотерея</b>

💰 <b>Текущий джекпот:</b> 15000 монет

📊 <b>Статистика:</b>
• Билетов продано: 247
• Ваших билетов: 0
• Шанс выигрыша: 0%

📅 <b>Розыгрыш через:</b> 3 дня 5 часов

🎁 <b>Призы:</b>
1-е место: 7500 монет (50%)
2-е место: 4500 монет (30%)
3-е место: 3000 монет (20%)

💳 <b>Цена билета:</b> 50 монет

<b>Купить билет?</b>
Отправьте: /lottery buy

<b>Ваши билеты:</b>
У вас нет билетов на текущий розыгрыш

🔜 <b>Функция в разработке</b>
Покупка билетов пока недоступна
        """
        await update.message.reply_text(text, parse_mode='HTML')


# Добавляем Optional import

-- Migration: Beta Features Schema
-- Date: 2026-02-20
-- Description: Adds tables for 27 new beta commands

-- ============================================
-- ЭКОНОМИКА И ТОРГОВЛЯ
-- ============================================

-- Рыночная площадка
CREATE TABLE IF NOT EXISTS marketplace_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL,
    item_type TEXT NOT NULL, -- 'shop_item', 'custom'
    item_id INTEGER,
    item_name TEXT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active', -- 'active', 'sold', 'cancelled', 'expired'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    sold_to INTEGER,
    sold_at TIMESTAMP,
    FOREIGN KEY (seller_id) REFERENCES users(id)
);

-- Сессии обмена
CREATE TABLE IF NOT EXISTS trade_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    initiator_id INTEGER NOT NULL,
    partner_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'accepted', 'completed', 'cancelled'
    initiator_offer_coins DECIMAL(10, 2) DEFAULT 0,
    partner_offer_coins DECIMAL(10, 2) DEFAULT 0,
    initiator_confirmed BOOLEAN DEFAULT 0,
    partner_confirmed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (initiator_id) REFERENCES users(id),
    FOREIGN KEY (partner_id) REFERENCES users(id)
);

-- Предметы в обмене
CREATE TABLE IF NOT EXISTS trade_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    FOREIGN KEY (trade_session_id) REFERENCES trade_sessions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Кредиты
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    interest_rate DECIMAL(5, 2) DEFAULT 10.0, -- процент в неделю
    total_amount DECIMAL(10, 2) NOT NULL, -- сумма с процентами
    amount_paid DECIMAL(10, 2) DEFAULT 0,
    status TEXT DEFAULT 'active', -- 'active', 'paid', 'overdue'
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP NOT NULL,
    paid_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Инвестиции
CREATE TABLE IF NOT EXISTS investments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    interest_rate DECIMAL(5, 2) NOT NULL, -- процент за период
    total_return DECIMAL(10, 2) NOT NULL, -- сумма с процентами
    duration_days INTEGER NOT NULL,
    status TEXT DEFAULT 'active', -- 'active', 'completed', 'withdrawn'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    matures_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- КВЕСТЫ И ЗАДАНИЯ
-- ============================================

-- Квесты
CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    quest_type TEXT NOT NULL, -- 'daily', 'weekly', 'story'
    category TEXT NOT NULL, -- 'earn', 'spend', 'social', 'games', 'activity'
    target_type TEXT NOT NULL, -- 'earn_coins', 'buy_items', 'invite_friends', 'win_games', 'login_streak'
    target_value INTEGER NOT NULL,
    reward_coins DECIMAL(10, 2) DEFAULT 0,
    reward_badge TEXT,
    is_active BOOLEAN DEFAULT 1,
    required_level INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Прогресс пользователей по квестам
CREATE TABLE IF NOT EXISTS user_quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    quest_id INTEGER NOT NULL,
    status TEXT DEFAULT 'active', -- 'active', 'completed', 'failed'
    progress INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (quest_id) REFERENCES quests(id),
    UNIQUE(user_id, quest_id)
);

-- ============================================
-- РЕЙТИНГИ И СОРЕВНОВАНИЯ
-- ============================================

-- Турниры
CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    tournament_type TEXT NOT NULL, -- 'mini_games', 'dnd', 'trading'
    prize_pool DECIMAL(10, 2) NOT NULL,
    max_participants INTEGER DEFAULT 100,
    status TEXT DEFAULT 'registration', -- 'registration', 'active', 'completed'
    registration_ends_at TIMESTAMP NOT NULL,
    starts_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Участники турниров
CREATE TABLE IF NOT EXISTS tournament_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    score INTEGER DEFAULT 0,
    rank INTEGER,
    prize_amount DECIMAL(10, 2) DEFAULT 0,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(tournament_id, user_id)
);

-- ============================================
-- ПЕРСОНАЛИЗАЦИЯ
-- ============================================

-- Титулы
CREATE TABLE IF NOT EXISTS titles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    requirement_type TEXT NOT NULL, -- 'default', 'trades', 'investments', 'games', 'achievements'
    requirement_value INTEGER DEFAULT 0,
    icon TEXT
);

-- Титулы пользователей
CREATE TABLE IF NOT EXISTS user_titles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT 0,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (title_id) REFERENCES titles(id),
    UNIQUE(user_id, title_id)
);

-- Значки
CREATE TABLE IF NOT EXISTS badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    icon TEXT NOT NULL,
    category TEXT NOT NULL, -- 'economy', 'quests', 'social', 'games'
    requirement_type TEXT NOT NULL,
    requirement_value INTEGER DEFAULT 0
);

-- Значки пользователей
CREATE TABLE IF NOT EXISTS user_badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    badge_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT 0,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (badge_id) REFERENCES badges(id),
    UNIQUE(user_id, badge_id)
);

-- Темы оформления
CREATE TABLE IF NOT EXISTS user_themes (
    user_id INTEGER PRIMARY KEY,
    theme_name TEXT DEFAULT 'classic', -- 'classic', 'minimal', 'colorful', 'dark', 'retro'
    custom_status TEXT,
    custom_description TEXT,
    profile_emoji TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- БОНУСЫ И СОБЫТИЯ
-- ============================================

-- События
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    event_type TEXT NOT NULL, -- 'holiday', 'bonus', 'sale', 'special'
    bonus_multiplier DECIMAL(3, 2) DEFAULT 1.0,
    discount_percent INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    starts_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Колесо фортуны (история)
CREATE TABLE IF NOT EXISTS spin_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reward_type TEXT NOT NULL, -- 'coins', 'item', 'multiplier'
    reward_value TEXT NOT NULL,
    spun_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Лотерея
CREATE TABLE IF NOT EXISTS lottery_draws (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jackpot DECIMAL(10, 2) NOT NULL,
    tickets_sold INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active', -- 'active', 'completed'
    draw_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Лотерейные билеты
CREATE TABLE IF NOT EXISTS lottery_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery_draw_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    ticket_number INTEGER NOT NULL,
    is_winner BOOLEAN DEFAULT 0,
    prize_amount DECIMAL(10, 2) DEFAULT 0,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lottery_draw_id) REFERENCES lottery_draws(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- ИНДЕКСЫ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ
-- ============================================

CREATE INDEX IF NOT EXISTS idx_marketplace_status ON marketplace_listings(status);
CREATE INDEX IF NOT EXISTS idx_marketplace_seller ON marketplace_listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_trade_sessions_status ON trade_sessions(status);
CREATE INDEX IF NOT EXISTS idx_loans_user ON loans(user_id);
CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status);
CREATE INDEX IF NOT EXISTS idx_investments_user ON investments(user_id);
CREATE INDEX IF NOT EXISTS idx_investments_status ON investments(status);
CREATE INDEX IF NOT EXISTS idx_user_quests_user ON user_quests(user_id);
CREATE INDEX IF NOT EXISTS idx_user_quests_status ON user_quests(status);
CREATE INDEX IF NOT EXISTS idx_tournament_participants_tournament ON tournament_participants(tournament_id);
CREATE INDEX IF NOT EXISTS idx_spin_history_user ON spin_history(user_id);
CREATE INDEX IF NOT EXISTS idx_lottery_tickets_draw ON lottery_tickets(lottery_draw_id);
CREATE INDEX IF NOT EXISTS idx_lottery_tickets_user ON lottery_tickets(user_id);

-- ============================================
-- НАЧАЛЬНЫЕ ДАННЫЕ
-- ============================================

-- Титулы по умолчанию
INSERT OR IGNORE INTO titles (name, description, requirement_type, requirement_value, icon) VALUES
('Новичок', 'Стартовый титул для всех', 'default', 0, '🆕'),
('Торговец', 'Совершите 100 сделок на рынке', 'trades', 100, '💼'),
('Инвестор', 'Инвестируйте 10000 монет', 'investments', 10000, '💰'),
('Игрок', 'Выиграйте 100 игр', 'games', 100, '🎮'),
('Легенда', 'Получите все достижения', 'achievements', 50, '👑');

-- Значки по умолчанию
INSERT OR IGNORE INTO badges (name, description, icon, category, requirement_type, requirement_value) VALUES
('Первые шаги', 'Зарегистрируйтесь в системе', '👣', 'social', 'register', 1),
('Трудяга', 'Заработайте 1000 монет', '💪', 'economy', 'earn_coins', 1000),
('Торговец', 'Совершите 50 сделок', '🤝', 'economy', 'trades', 50),
('Инвестор', 'Создайте 10 депозитов', '📈', 'economy', 'investments', 10),
('Квестер', 'Выполните 25 квестов', '🎯', 'quests', 'complete_quests', 25),
('Социальный', 'Добавьте 10 друзей', '👥', 'social', 'friends', 10),
('Чемпион', 'Выиграйте турнир', '🏆', 'games', 'tournament_wins', 1),
('Удачливый', 'Выиграйте в лотерею', '🍀', 'economy', 'lottery_wins', 1);

-- Начальные квесты
INSERT OR IGNORE INTO quests (name, description, quest_type, category, target_type, target_value, reward_coins, reward_badge) VALUES
('Первые шаги', 'Заработайте 100 монет', 'daily', 'earn', 'earn_coins', 100, 50, NULL),
('Покупатель', 'Купите 3 предмета в магазине', 'daily', 'spend', 'buy_items', 3, 75, NULL),
('Социальный', 'Добавьте 1 друга', 'daily', 'social', 'invite_friends', 1, 100, NULL),
('Игрок', 'Выиграйте 5 игр', 'weekly', 'games', 'win_games', 5, 250, NULL),
('Постоянство', 'Заходите 7 дней подряд', 'weekly', 'activity', 'login_streak', 7, 500, 'Трудяга');

-- Создаем первый розыгрыш лотереи
INSERT OR IGNORE INTO lottery_draws (jackpot, draw_date) 
VALUES (1000, datetime('now', '+7 days'));

-- Создаем активное событие (пример)
INSERT OR IGNORE INTO events (name, description, event_type, bonus_multiplier, starts_at, ends_at) 
VALUES ('Добро пожаловать!', 'Приветственное событие для новых пользователей', 'bonus', 1.5, datetime('now'), datetime('now', '+30 days'));

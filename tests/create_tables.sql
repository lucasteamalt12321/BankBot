-- Create shop_items table
CREATE TABLE IF NOT EXISTS shop_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    price INTEGER NOT NULL DEFAULT 100,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_purchases table
CREATE TABLE IF NOT EXISTS user_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    data JSON NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (item_id) REFERENCES shop_items(id)
);

-- Create scheduled_tasks table
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message_id INTEGER NULL,
    chat_id INTEGER NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    execute_at TIMESTAMP NOT NULL,
    task_data JSON NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Insert default shop items
INSERT OR IGNORE INTO shop_items (id, name, price, description, is_active, created_at)
VALUES 
    (1, 'Безлимитные стикеры на 24 часа', 100, 'Получите возможность отправлять неограниченное количество стикеров в течение 24 часов', TRUE, datetime('now')),
    (2, 'Запрос на админ-права', 100, 'Отправить запрос владельцу бота на получение прав администратора', TRUE, datetime('now')),
    (3, 'Рассылка сообщения всем пользователям', 100, 'Отправить ваше сообщение всем пользователям бота', TRUE, datetime('now'));
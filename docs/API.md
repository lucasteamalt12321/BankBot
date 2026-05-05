# Bot API Documentation

## Telegram Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and registration |
| `/balance` | Check user balance |
| `/history` | Transaction history |
| `/profile` | User profile |
| `/stats` | Personal statistics |

### Shop Commands

| Command | Description |
|---------|-------------|
| `/shop` | View shop items |
| `/buy` | Purchase item by name |
| `/buy_N` | Purchase item by number (1-8) |
| `/inventory` | View owned items |

### Games Commands

| Command | Description |
|---------|-------------|
| `/games` | Game info |
| `/play <type>` | Create game (cities, killer_words, gd_levels) |
| `/join <id>` | Join game |
| `/startgame <id>` | Start game |
| `/turn <id> <move>` | Make game move |

### D&D Commands

| Command | Description |
|---------|-------------|
| `/dnd` | D&D info |
| `/dnd_create <name>` | Create session |
| `/dnd_join <id>` | Join session |
| `/dnd_roll <dice>` | Roll dice (e.g., d20+5) |
| `/dnd_sessions` | List sessions |

### Motivation Commands

| Command | Description |
|---------|-------------|
| `/daily` / `/bonus` | Daily bonus |
| `/challenges` | Weekly challenges |
| `/streak` | Motivation stats |

### Social Commands

| Command | Description |
|---------|-------------|
| `/friends` | Friend list |
| `/friend_add <id>` | Send friend request |
| `/friend_accept <id>` | Accept request |
| `/gift <id> <amount>` | Send coins |
| `/clan` / `/clan_create` / `/clan_join` | Clan management |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | Admin panel |
| `/admin_stats` | System statistics |
| `/admin_users` | User management |
| `/admin_adjust <id> <amount>` | Adjust balance |
| `/admin_addcoins <id> <amount>` | Add coins |
| `/admin_removecoins <id> <amount>` | Remove coins |
| `/admin_shop_add` | Add shop item |
| `/admin_shop_edit` | Edit shop item |
| `/broadcast <msg>` | Send message to all users |
| `/parsing_stats` | Parsing statistics |

---

## Internal APIs

### BalanceService

```python
from core.services.balance_service import BalanceService

service = BalanceService(session)

# Accrue coins
user = service.accrue(user_id, amount, description, source_game)

# Deduct coins (raises ValueError if insufficient)
user = service.deduct(user_id, amount, description, source_game)

# Get balance
balance = service.get_balance(user_id)
```

### ShopService

```python
from core.services.shop_service import ShopService

service = ShopService(user_repository)

# Get all items
items = service.get_all_items()

# Purchase item
result = service.purchase_item(user_id, item_id)

# Check balance
has_balance = service.check_balance(user_id, amount)
```

### UserService

```python
from core.services.user_service import UserService

service = UserService(session)

# Create user
user = service.create_user(telegram_id, username)

# Get user
user = service.get_user(user_id)

# Update balance
service.update_balance(user_id, amount)
```

### TransactionService

```python
from core.services.transaction_service import TransactionService

service = TransactionService(session)

# Log transaction
tx = service.log_transaction(user_id, amount, tx_type, description)

# Get history
history = service.get_user_transactions(user_id, limit)
```

---

## Database Models

### User
- `id` (int) - Primary key
- `telegram_id` (int) - Telegram user ID
- `username` (str) - Username
- `balance` (int) - Current balance
- `created_at` (datetime) - Registration time

### Transaction
- `id` (int) - Primary key
- `user_id` (int) - Foreign key to User
- `amount` (int) - Transaction amount (+/-)
- `transaction_type` (str) - Type (accrual, deduction, purchase)
- `description` (str) - Description
- `source_game` (str) - Game source (optional)
- `created_at` (datetime) - Transaction time

### ShopItem
- `id` (int) - Primary key
- `category_id` (int) - Foreign key to ShopCategory
- `name` (str) - Item name
- `description` (str) - Item description
- `price` (int) - Price in coins
- `item_type` (str) - Type (role, sticker, etc.)
- `is_active` (bool) - Active status

### ShopCategory
- `id` (int) - Primary key
- `name` (str) - Category name
- `sort_order` (int) - Display order
- `is_active` (bool) - Active status

---

## Configuration

Environment variables in `.env`:

```
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=sqlite:///data/bot.db
ADMIN_USER_IDS=123456789,987654321
PARSING_ENABLED=true
LOG_LEVEL=INFO
```

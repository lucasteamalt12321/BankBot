# database.py
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey, func, DECIMAL
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from utils.core.config import settings

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    balance = Column(Integer, default=0)
    daily_streak = Column(Integer, default=0)
    last_daily = Column(DateTime, nullable=True)
    total_earned = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_vip = Column(Boolean, default=False)
    vip_until = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)
    # New columns for advanced features
    sticker_unlimited = Column(Boolean, default=False)
    sticker_unlimited_until = Column(DateTime, nullable=True)
    total_purchases = Column(Integer, default=0)

    aliases = relationship("UserAlias", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    purchases = relationship("UserPurchase", back_populates="user", cascade="all, delete-orphan")
    game_players = relationship("GamePlayer", back_populates="user", cascade="all, delete-orphan")
    dnd_characters = relationship("DndCharacter", back_populates="user", cascade="all, delete-orphan")
    dnd_sessions_master = relationship("DndSession", back_populates="master", foreign_keys="DndSession.master_id", cascade="all, delete-orphan")
    dnd_dice_rolls = relationship("DndDiceRoll", back_populates="user", cascade="all, delete-orphan")
    achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("UserNotification", back_populates="user", cascade="all, delete-orphan")
    friends = relationship("Friendship", foreign_keys="Friendship.user_id", cascade="all, delete-orphan")
    friend_of = relationship("Friendship", foreign_keys="Friendship.friend_id", cascade="all, delete-orphan")
    sent_gifts = relationship("Gift", foreign_keys="Gift.sender_id", cascade="all, delete-orphan")
    received_gifts = relationship("Gift", foreign_keys="Gift.receiver_id", cascade="all, delete-orphan")
    owned_clans = relationship("Clan", back_populates="owner", cascade="all, delete-orphan")
    clan_memberships = relationship("ClanMember", back_populates="user", cascade="all, delete-orphan")
    scheduled_tasks = relationship("ScheduledTask", cascade="all, delete-orphan")


class UserAlias(Base):
    __tablename__ = "user_aliases"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    alias_type = Column(String(20))
    alias_value = Column(String(100))
    game_source = Column(String(50))
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="aliases")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    amount = Column(Integer)
    transaction_type = Column(String(50))
    source_game = Column(String(50), nullable=True)
    description = Column(Text)
    meta_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class ShopCategory(Base):
    __tablename__ = "shop_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    items = relationship("ShopItem", back_populates="category", cascade="all, delete-orphan")


class ShopItem(Base):
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("shop_categories.id", ondelete="CASCADE"))
    name = Column(String(100))
    description = Column(Text)
    price = Column(Integer)
    item_type = Column(String(50))
    meta_data = Column(JSON, nullable=True)
    purchase_limit = Column(Integer, default=0)
    cooldown_hours = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    category = relationship("ShopCategory", back_populates="items")
    purchases = relationship("UserPurchase", back_populates="item", cascade="all, delete-orphan")


class UserPurchase(Base):
    __tablename__ = "user_purchases"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    item_id = Column(Integer, ForeignKey("shop_items.id", ondelete="CASCADE"))
    purchase_price = Column(Integer)
    purchased_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    meta_data = Column(JSON, nullable=True)

    user = relationship("User", back_populates="purchases")
    item = relationship("ShopItem", back_populates="purchases")


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    message_id = Column(Integer, nullable=True)
    chat_id = Column(Integer, nullable=False)
    task_type = Column(String(50), nullable=False)
    execute_at = Column(DateTime, nullable=False)
    task_data = Column(JSON, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class GameSession(Base):
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True)
    game_type = Column(String(50))
    status = Column(String(20), default='waiting')
    current_player_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_city = Column(String(100), nullable=True)
    used_cities = Column(JSON, nullable=True)
    game_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    players = relationship("GamePlayer", back_populates="session", cascade="all, delete-orphan")
    current_player = relationship("User", foreign_keys=[current_player_id])


class GamePlayer(Base):
    __tablename__ = "game_players"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    score = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("GameSession", back_populates="players")
    user = relationship("User", back_populates="game_players")


class DndSession(Base):
    __tablename__ = "dnd_sessions"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String(100))
    description = Column(Text, nullable=True)
    max_players = Column(Integer, default=6)
    current_players = Column(Integer, default=0)
    status = Column(String(20), default='planning')
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)

    master = relationship("User", back_populates="dnd_sessions_master", foreign_keys=[master_id])
    characters = relationship("DndCharacter", back_populates="session", cascade="all, delete-orphan")
    dice_rolls = relationship("DndDiceRoll", back_populates="session", cascade="all, delete-orphan")
    quests = relationship("DndQuest", back_populates="session", cascade="all, delete-orphan")


class DndCharacter(Base):
    __tablename__ = "dnd_characters"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("dnd_sessions.id", ondelete="CASCADE"))
    player_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String(100))
    character_class = Column(String(50))
    level = Column(Integer, default=1)
    background = Column(Text, nullable=True)
    stats = Column(JSON)
    inventory = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    session = relationship("DndSession", back_populates="characters")
    user = relationship("User", back_populates="dnd_characters")
    quests = relationship("DndQuest", back_populates="character", cascade="all, delete-orphan")
    dice_rolls = relationship("DndDiceRoll", back_populates="character", cascade="all, delete-orphan")


class DndDiceRoll(Base):
    __tablename__ = "dnd_dice_rolls"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("dnd_sessions.id", ondelete="CASCADE"))
    character_id = Column(Integer, ForeignKey("dnd_characters.id", ondelete="CASCADE"), nullable=True)
    player_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    dice_type = Column(String(10))
    dice_count = Column(Integer, default=1)
    modifier = Column(Integer, default=0)
    result = Column(Integer)
    total = Column(Integer)
    purpose = Column(String(100), nullable=True)
    is_secret = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("DndSession", back_populates="dice_rolls")
    character = relationship("DndCharacter", back_populates="dice_rolls")
    user = relationship("User", back_populates="dnd_dice_rolls")


class DndQuest(Base):
    __tablename__ = "dnd_quests"

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("dnd_characters.id", ondelete="CASCADE"))
    session_id = Column(Integer, ForeignKey("dnd_sessions.id", ondelete="CASCADE"))
    title = Column(String(100))
    description = Column(Text)
    status = Column(String(20), default='active')
    reward_xp = Column(Integer, default=0)
    reward_gold = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    character = relationship("DndCharacter", back_populates="quests")
    session = relationship("DndSession", back_populates="quests")


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50))
    tier = Column(String(20))
    points = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_achievements = relationship("UserAchievement", back_populates="achievement", cascade="all, delete-orphan")


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    achievement_id = Column(Integer, ForeignKey("achievements.id", ondelete="CASCADE"))
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    progress = Column(Integer, default=100)

    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    notification_type = Column(String(50))
    title = Column(String(200))
    message = Column(Text)
    data = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="notifications")


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    friend_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id], back_populates="friends")
    friend = relationship("User", foreign_keys=[friend_id], back_populates="friend_of")


class Gift(Base):
    __tablename__ = "gifts"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    item_id = Column(Integer, ForeignKey("shop_items.id", ondelete="CASCADE"), nullable=True)
    amount = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    status = Column(String(20), default='sent')
    created_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_gifts")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_gifts")
    item = relationship("ShopItem")


class Clan(Base):
    __tablename__ = "clans"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    owner = relationship("User", back_populates="owned_clans")
    members = relationship("ClanMember", back_populates="clan", cascade="all, delete-orphan")


class ClanMember(Base):
    __tablename__ = "clan_members"

    id = Column(Integer, primary_key=True)
    clan_id = Column(Integer, ForeignKey("clans.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    role = Column(String(20), default='member')
    joined_at = Column(DateTime, default=datetime.utcnow)

    clan = relationship("Clan", back_populates="members")
    user = relationship("User", back_populates="clan_memberships")


class ParsingRule(Base):
    __tablename__ = "parsing_rules"

    id = Column(Integer, primary_key=True)
    bot_name = Column(String(50), nullable=False)
    pattern = Column(String(200), nullable=False)
    multiplier = Column(DECIMAL(10, 4), nullable=False)
    currency_type = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)


class ParsedTransaction(Base):
    __tablename__ = "parsed_transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    source_bot = Column(String(50), nullable=False)
    original_amount = Column(DECIMAL(10, 2), nullable=False)
    converted_amount = Column(DECIMAL(10, 2), nullable=False)
    currency_type = Column(String(20), nullable=False)
    parsed_at = Column(DateTime, default=datetime.utcnow)
    message_text = Column(Text)

    user = relationship("User")


class PurchaseRecord(Base):
    __tablename__ = "purchase_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    item_id = Column(Integer, ForeignKey("shop_items.id", ondelete="CASCADE"))
    price_paid = Column(DECIMAL(10, 2), nullable=False)
    purchased_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User")
    item = relationship("ShopItem")


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
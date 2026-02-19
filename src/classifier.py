from enum import Enum


class MessageType(Enum):
    # GD Cards
    GDCARDS_PROFILE = "gdcards_profile"
    GDCARDS_ACCRUAL = "gdcards_accrual"
    
    # Shmalala
    SHMALALA_FISHING = "shmalala_fishing"
    SHMALALA_FISHING_TOP = "shmalala_fishing_top"
    SHMALALA_KARMA = "shmalala_karma"
    SHMALALA_KARMA_TOP = "shmalala_karma_top"
    
    # True Mafia
    TRUEMAFIA_GAME_END = "truemafia_game_end"
    TRUEMAFIA_PROFILE = "truemafia_profile"
    
    # BunkerRP
    BUNKERRP_GAME_END = "bunkerrp_game_end"
    BUNKERRP_PROFILE = "bunkerrp_profile"
    
    UNKNOWN = "unknown"


class MessageClassifier:
    """Classifies messages by detecting key phrases."""
    
    # GD Cards markers
    GDCARDS_PROFILE_MARKER = "ПРОФИЛЬ"
    GDCARDS_ACCRUAL_MARKER = "🃏 НОВАЯ КАРТА 🃏"
    
    # Shmalala markers
    SHMALALA_FISHING_MARKER = "🎣 [Рыбалка] 🎣"
    SHMALALA_FISHING_TOP_MARKER = "[Самые богатые в этом чате]"
    SHMALALA_KARMA_MARKER = "Лайк! Вы повысили рейтинг пользователя"
    SHMALALA_KARMA_TOP_MARKER = "[Самые крутые по Карме в этом чате]"
    
    # True Mafia markers
    TRUEMAFIA_GAME_END_MARKER = "Игра окончена!"
    TRUEMAFIA_PROFILE_MARKER_1 = "💎 Камни:"
    TRUEMAFIA_PROFILE_MARKER_2 = "🎎 Активная роль:"
    
    # BunkerRP markers
    BUNKERRP_GAME_END_MARKER = "Прошли в бункер:"
    BUNKERRP_PROFILE_MARKER_1 = "💎 Кристаллики:"
    BUNKERRP_PROFILE_MARKER_2 = "🎯 Побед:"
    
    def classify(self, message: str) -> MessageType:
        """
        Classify message type based on content.
        
        Args:
            message: Raw message text
            
        Returns:
            MessageType enum value
        """
        # GD Cards
        if self.GDCARDS_PROFILE_MARKER in message and "Орбы:" in message:
            return MessageType.GDCARDS_PROFILE
        elif self.GDCARDS_ACCRUAL_MARKER in message:
            return MessageType.GDCARDS_ACCRUAL
        
        # Shmalala
        elif self.SHMALALA_FISHING_MARKER in message:
            return MessageType.SHMALALA_FISHING
        elif self.SHMALALA_FISHING_TOP_MARKER in message:
            return MessageType.SHMALALA_FISHING_TOP
        elif self.SHMALALA_KARMA_MARKER in message:
            return MessageType.SHMALALA_KARMA
        elif self.SHMALALA_KARMA_TOP_MARKER in message:
            return MessageType.SHMALALA_KARMA_TOP
        
        # True Mafia
        elif self.TRUEMAFIA_GAME_END_MARKER in message and "Победители:" in message:
            return MessageType.TRUEMAFIA_GAME_END
        elif self.TRUEMAFIA_PROFILE_MARKER_1 in message and self.TRUEMAFIA_PROFILE_MARKER_2 in message and "💵 Деньги:" in message:
            return MessageType.TRUEMAFIA_PROFILE
        
        # BunkerRP
        elif self.BUNKERRP_GAME_END_MARKER in message:
            return MessageType.BUNKERRP_GAME_END
        elif self.BUNKERRP_PROFILE_MARKER_1 in message and self.BUNKERRP_PROFILE_MARKER_2 in message and "💵 Деньги:" in message:
            return MessageType.BUNKERRP_PROFILE
        
        else:
            return MessageType.UNKNOWN

"""
ParsingConfigManager - управление конфигурацией парсинга (Task 7.2)

Этот модуль предоставляет API для управления правилами парсинга:
- Добавление/удаление правил
- Обновление коэффициентов
- Активация/деактивация правил
- Экспорт/импорт конфигурации
"""

import structlog
from typing import Any, Dict, List, Optional
from decimal import Decimal


from database.database import ParsingRule, get_db

logger = structlog.get_logger()


class ParsingConfigManager:
    """
    Менеджер конфигурации парсинга.
    
    Предоставляет API для управления правилами парсинга в базе данных.
    Поддерживает два режима:
    - Старый: через SQLAlchemy session + старая модель ParsingRule (bot_name/pattern)
    - Новый: через BaseRepository + новая модель ParsingRule (game_name/parser_class)
    """

    def __init__(self, session_or_repository=None, *, session=None):
        """
        Инициализация менеджера.
        
        Args:
            session_or_repository: SQLAlchemy сессия или BaseRepository.
                Если None, создается новая сессия.
            session: Именованный аргумент для обратной совместимости.
        """
        # Поддержка именованного аргумента session (обратная совместимость)
        if session is not None and session_or_repository is None:
            session_or_repository = session
        # Определяем режим работы
        from src.repository.base import BaseRepository
        if isinstance(session_or_repository, BaseRepository):
            # Новый режим: через BaseRepository
            self._repository = session_or_repository
            self.session = session_or_repository.session
            self._use_repository = True
            self._session_created = False
        else:
            # Старый режим: через session
            self.session = session_or_repository or next(get_db())
            self._repository = None
            self._use_repository = False
            self._session_created = session_or_repository is None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self._session_created:
            self.session.close()

    def get_rule(self, bot_name: str, pattern: str) -> Optional[ParsingRule]:
        """
        Получить правило парсинга по имени бота и паттерну.
        
        Args:
            bot_name: Имя бота
            pattern: Regex паттерн
            
        Returns:
            ParsingRule или None если не найдено
        """
        try:
            rule = self.session.query(ParsingRule).filter(
                ParsingRule.bot_name == bot_name,
                ParsingRule.pattern == pattern
            ).first()

            if rule:
                logger.debug(f"Found parsing rule for {bot_name}: {pattern}")

            return rule

        except Exception as e:
            logger.error(f"Error getting parsing rule: {e}")
            return None

    def get_rule_by_id(self, rule_id: int) -> Optional[ParsingRule]:
        """
        Получить правило парсинга по ID.
        
        Args:
            rule_id: ID правила
            
        Returns:
            ParsingRule или None если не найдено
        """
        try:
            rule = self.session.query(ParsingRule).filter(
                ParsingRule.id == rule_id
            ).first()

            if rule:
                logger.debug(f"Found parsing rule with ID {rule_id}")

            return rule

        except Exception as e:
            logger.error(f"Error getting parsing rule by ID: {e}")
            return None

    def get_all_rules(self, active_only: bool = True) -> List[ParsingRule]:
        """
        Получить все правила парсинга.
        
        Args:
            active_only: Если True, возвращает только активные правила
            
        Returns:
            Список ParsingRule
        """
        try:
            query = self.session.query(ParsingRule)

            if active_only:
                query = query.filter(ParsingRule.is_active)

            rules = query.all()
            logger.debug(f"Retrieved {len(rules)} parsing rules")

            return rules

        except Exception as e:
            logger.error(f"Error getting all parsing rules: {e}")
            return []

    def get_rules_by_bot(self, bot_name: str, active_only: bool = True) -> List[ParsingRule]:
        """
        Получить все правила для конкретного бота.
        
        Args:
            bot_name: Имя бота
            active_only: Если True, возвращает только активные правила
            
        Returns:
            Список ParsingRule
        """
        try:
            query = self.session.query(ParsingRule).filter(
                ParsingRule.bot_name == bot_name
            )

            if active_only:
                query = query.filter(ParsingRule.is_active)

            rules = query.all()
            logger.debug(f"Retrieved {len(rules)} parsing rules for {bot_name}")

            return rules

        except Exception as e:
            logger.error(f"Error getting parsing rules for {bot_name}: {e}")
            return []

    def add_rule(
        self,
        bot_name: str,
        pattern: str,
        multiplier: Decimal,
        currency_type: str,
        is_active: bool = True
    ) -> Optional[ParsingRule]:
        """
        Добавить новое правило парсинга.
        
        Args:
            bot_name: Имя бота
            pattern: Regex паттерн
            multiplier: Коэффициент конверсии
            currency_type: Тип валюты
            is_active: Активно ли правило
            
        Returns:
            Созданный ParsingRule или None если ошибка
        """
        try:
            # Проверяем, не существует ли уже такое правило
            existing = self.get_rule(bot_name, pattern)
            if existing:
                logger.warning(f"Parsing rule already exists for {bot_name}: {pattern}")
                return None

            # Создаем новое правило
            new_rule = ParsingRule(
                bot_name=bot_name,
                pattern=pattern,
                multiplier=multiplier,
                currency_type=currency_type,
                is_active=is_active
            )

            self.session.add(new_rule)
            self.session.commit()

            logger.info(f"Added new parsing rule for {bot_name}: {pattern}")

            return new_rule

        except Exception as e:
            logger.error(f"Error adding parsing rule: {e}")
            self.session.rollback()
            return None

    def update_rule(self, rule_id: int, **kwargs) -> bool:
        """
        Обновить существующее правило парсинга.
        
        Args:
            rule_id: ID правила
            **kwargs: Поля для обновления
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            rule = self.get_rule_by_id(rule_id)
            if not rule:
                logger.warning(f"Parsing rule with ID {rule_id} not found")
                return False

            # Обновляем поля
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)

            self.session.commit()

            logger.info(f"Updated parsing rule {rule_id}: {list(kwargs.keys())}")

            return True

        except Exception as e:
            logger.error(f"Error updating parsing rule: {e}")
            self.session.rollback()
            return False

    def delete_rule(self, rule_id: int) -> bool:
        """
        Удалить правило парсинга.
        
        Args:
            rule_id: ID правила
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            rule = self.get_rule_by_id(rule_id)
            if not rule:
                logger.warning(f"Parsing rule with ID {rule_id} not found")
                return False

            self.session.delete(rule)
            self.session.commit()

            logger.info(f"Deleted parsing rule {rule_id}")

            return True

        except Exception as e:
            logger.error(f"Error deleting parsing rule: {e}")
            self.session.rollback()
            return False

    def activate_rule(self, rule_id: int) -> bool:
        """
        Активировать правило парсинга.
        
        Args:
            rule_id: ID правила
            
        Returns:
            True если успешно, False если ошибка
        """
        return self.update_rule(rule_id, is_active=True)

    def deactivate_rule(self, rule_id: int) -> bool:
        """
        Деактивировать правило парсинга.
        
        Args:
            rule_id: ID правила
            
        Returns:
            True если успешно, False если ошибка
        """
        return self.update_rule(rule_id, is_active=False)

    def update_coefficient(self, rule_id: int, coefficient: Decimal) -> bool:
        """
        Обновить коэффициент правила парсинга.
        
        Args:
            rule_id: ID правила
            coefficient: Новый коэффициент
            
        Returns:
            True если успешно, False если ошибка
        """
        return self.update_rule(rule_id, multiplier=coefficient)

    def get_coefficients_by_bot(self, bot_name: str) -> Dict[str, Decimal]:
        """
        Получить все коэффициенты для бота.
        
        Args:
            bot_name: Имя бота
            
        Returns:
            Словарь {pattern: coefficient}
        """
        try:
            rules = self.get_rules_by_bot(bot_name)

            coefficients = {}
            for rule in rules:
                # Explicitly convert to Python types to satisfy type checker
                pattern = str(getattr(rule, 'pattern', ''))
                multiplier = Decimal(str(getattr(rule, 'multiplier', '0')))
                is_active = bool(getattr(rule, 'is_active', False))

                if is_active and pattern:
                    coefficients[pattern] = multiplier

            logger.debug(f"Retrieved {len(coefficients)} coefficients for {bot_name}")

            return coefficients

        except Exception as e:
            logger.error(f"Error getting coefficients for {bot_name}: {e}")
            return {}

    def export_rules(self, bot_name: Optional[str] = None) -> List[Dict]:
        """
        Экспортировать правила в формат dict.
        
        Args:
            bot_name: Имя бота (если None, экспортируются все правила)
            
        Returns:
            Список словарей с правилами
        """
        try:
            if bot_name:
                rules = self.get_rules_by_bot(bot_name, active_only=False)
            else:
                rules = self.get_all_rules(active_only=False)

            exported = []
            for rule in rules:
                # Explicitly convert to Python types to satisfy type checker
                rule_id = int(getattr(rule, 'id', 0))
                bot_name_val = str(getattr(rule, 'bot_name', ''))
                pattern_val = str(getattr(rule, 'pattern', ''))
                multiplier_val = float(str(getattr(rule, 'multiplier', '1.0')))
                currency_type_val = str(getattr(rule, 'currency_type', 'coins'))
                is_active_val = bool(getattr(rule, 'is_active', False))

                exported.append({
                    'id': rule_id,
                    'bot_name': bot_name_val,
                    'pattern': pattern_val,
                    'multiplier': multiplier_val,
                    'currency_type': currency_type_val,
                    'is_active': is_active_val
                })

            logger.info(f"Exported {len(exported)} parsing rules")

            return exported

        except Exception as e:
            logger.error(f"Error exporting parsing rules: {e}")
            return []

    def import_rules(self, rules_data: List[Dict], overwrite: bool = False) -> int:
        """
        Импортировать правила из формата dict.
        
        Args:
            rules_data: Список словарей с правилами
            overwrite: Если True, перезаписывает существующие правила
            
        Returns:
            Количество успешно импортированных правил
        """
        try:
            imported_count = 0

            for rule_data in rules_data:
                bot_name = rule_data.get('bot_name')
                pattern = rule_data.get('pattern')

                if not bot_name or not pattern:
                    logger.warning(f"Skipping rule with missing bot_name or pattern: {rule_data}")
                    continue

                # Проверяем существование
                existing = self.get_rule(bot_name, pattern)
                if existing and not overwrite:
                    logger.warning(f"Rule already exists for {bot_name}: {pattern}, skipping")
                    continue

                # Создаем или обновляем правило
                if existing:
                    self.update_rule(
                        existing.id,
                        multiplier=rule_data.get('multiplier', existing.multiplier),
                        currency_type=rule_data.get('currency_type', existing.currency_type),
                        is_active=rule_data.get('is_active', existing.is_active)
                    )
                else:
                    self.add_rule(
                        bot_name=bot_name,
                        pattern=pattern,
                        multiplier=Decimal(str(rule_data.get('multiplier', 1))),
                        currency_type=rule_data.get('currency_type', 'coins'),
                        is_active=rule_data.get('is_active', True)
                    )

                imported_count += 1

            logger.info(f"Imported {imported_count} parsing rules")

            return imported_count

        except Exception as e:
            logger.error(f"Error importing parsing rules: {e}")
            return 0

    # =========================================================================
    # Новый API (через BaseRepository + новая модель ParsingRule с game_name)
    # =========================================================================

    def create_rule(
        self,
        game_name: str,
        parser_class: str = "",
        coefficient: float = 1.0,
        enabled: bool = True,
        config: Optional[Dict] = None,
    ) -> Any:
        """
        Создать новое правило парсинга (новый API).

        Args:
            game_name: Уникальное имя игры
            parser_class: Имя класса парсера
            coefficient: Коэффициент умножения очков
            enabled: Активно ли правило
            config: Дополнительная JSON-конфигурация

        Returns:
            Созданный объект правила
        """
        if not self._use_repository:
            raise RuntimeError("create_rule требует BaseRepository. Передайте repository в конструктор.")
        return self._repository.create(
            game_name=game_name,
            parser_class=parser_class,
            coefficient=coefficient,
            enabled=enabled,
            config=config if config is not None else {},
        )

    def get_rule(self, game_name_or_bot: str, pattern: Optional[str] = None) -> Optional[Any]:  # noqa: F811
        """
        Получить правило по имени игры (новый API) или по bot_name+pattern (старый API).

        Args:
            game_name_or_bot: Имя игры (новый API) или имя бота (старый API)
            pattern: Regex паттерн (только для старого API)

        Returns:
            Объект правила или None
        """
        if self._use_repository:
            return self._repository.get_by(game_name=game_name_or_bot)
        # Старый API
        try:
            rule = self.session.query(ParsingRule).filter(
                ParsingRule.bot_name == game_name_or_bot,
                ParsingRule.pattern == pattern,
            ).first()
            return rule
        except Exception as e:
            logger.error(f"Error getting parsing rule: {e}")
            return None

    def get_all_rules(self, active_only: Optional[bool] = None) -> Any:  # noqa: F811
        """
        Получить все правила.

        Args:
            active_only: Если True — только активные; None — все (новый API возвращает dict)

        Returns:
            Новый API: dict {game_name: rule}; Старый API: list[ParsingRule]
        """
        if self._use_repository:
            rules = self._repository.get_all()
            if active_only is None:
                return {r.game_name: r for r in rules}
            return {r.game_name: r for r in rules if r.enabled == active_only}
        # Старый API
        try:
            query = self.session.query(ParsingRule)
            if active_only:
                query = query.filter(ParsingRule.is_active)  # noqa: E712
            return query.all()
        except Exception as e:
            logger.error(f"Error getting all parsing rules: {e}")
            return []

    def get_all_active_rules(self) -> Dict[str, Any]:
        """
        Получить все активные правила (новый API).

        Returns:
            dict {game_name: rule}
        """
        if not self._use_repository:
            raise RuntimeError("get_all_active_rules требует BaseRepository.")
        rules = self._repository.get_all_by(enabled=True)
        return {r.game_name: r for r in rules}

    def update_rule(self, game_name_or_id: Any = None, *, game_name: Optional[str] = None, **kwargs: Any) -> bool:  # noqa: F811
        """
        Обновить правило по имени игры (новый API) или по ID (старый API).

        Args:
            game_name_or_id: Имя игры (str, новый API) или ID (int, старый API)
            game_name: Именованный аргумент для нового API (альтернатива game_name_or_id)
            **kwargs: Поля для обновления

        Returns:
            True если успешно, False иначе
        """
        # Поддержка именованного аргумента game_name
        if game_name is not None and game_name_or_id is None:
            game_name_or_id = game_name
        if self._use_repository:
            target_name = game_name_or_id
            rule = self._repository.get_by(game_name=target_name)
            if not rule:
                return False
            updated = self._repository.update(rule.id, **kwargs)
            return updated is not None
        # Старый API (по ID)
        try:
            rule = self.get_rule_by_id(game_name_or_id)
            if not rule:
                logger.warning(f"Parsing rule with ID {game_name_or_id} not found")
                return False
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating parsing rule: {e}")
            self.session.rollback()
            return False

    def delete_rule(self, game_name_or_id: Any) -> bool:  # noqa: F811
        """
        Удалить правило по имени игры (новый API) или по ID (старый API).

        Args:
            game_name_or_id: Имя игры (str, новый API) или ID (int, старый API)

        Returns:
            True если успешно, False иначе
        """
        if self._use_repository:
            game_name = game_name_or_id
            return self._repository.delete_by(game_name=game_name)
        # Старый API (по ID)
        try:
            rule = self.get_rule_by_id(game_name_or_id)
            if not rule:
                return False
            self.session.delete(rule)
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting parsing rule: {e}")
            self.session.rollback()
            return False

    def update_coefficient(self, game_name_or_id: Any, coefficient: Any) -> bool:  # noqa: F811
        """
        Обновить коэффициент правила.

        Args:
            game_name_or_id: Имя игры (str, новый API) или ID (int, старый API)
            coefficient: Новый коэффициент

        Returns:
            True если успешно, False иначе
        """
        if self._use_repository:
            return self.update_rule(game_name_or_id, coefficient=float(coefficient))
        return self._legacy_update_rule(game_name_or_id, multiplier=Decimal(str(coefficient)))

    def _legacy_update_rule(self, rule_id: int, **kwargs: Any) -> bool:
        """Обновить правило по ID (старый API, внутренний метод)."""
        try:
            rule = self.get_rule_by_id(rule_id)
            if not rule:
                return False
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating parsing rule: {e}")
            self.session.rollback()
            return False

    def enable_rule(self, game_name: str) -> bool:
        """
        Активировать правило по имени игры (новый API).

        Args:
            game_name: Имя игры

        Returns:
            True если успешно, False иначе
        """
        if not self._use_repository:
            raise RuntimeError("enable_rule требует BaseRepository.")
        return self.update_rule(game_name, enabled=True)

    def disable_rule(self, game_name: str) -> bool:
        """
        Деактивировать правило по имени игры (новый API).

        Args:
            game_name: Имя игры

        Returns:
            True если успешно, False иначе
        """
        if not self._use_repository:
            raise RuntimeError("disable_rule требует BaseRepository.")
        return self.update_rule(game_name, enabled=False)

    def is_enabled(self, game_name: str) -> bool:
        """
        Проверить, активно ли правило (новый API).

        Args:
            game_name: Имя игры

        Returns:
            True если активно, False иначе
        """
        if not self._use_repository:
            raise RuntimeError("is_enabled требует BaseRepository.")
        rule = self._repository.get_by(game_name=game_name)
        if rule is None:
            return False
        return bool(rule.enabled)

    def get_coefficient(self, game_name: str) -> Optional[float]:
        """
        Получить коэффициент правила по имени игры (новый API).

        Args:
            game_name: Имя игры

        Returns:
            Коэффициент или None если правило не найдено
        """
        if not self._use_repository:
            raise RuntimeError("get_coefficient требует BaseRepository.")
        rule = self._repository.get_by(game_name=game_name)
        if rule is None:
            return None
        return float(rule.coefficient)

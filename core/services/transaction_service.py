"""Transaction service for business logic related to financial operations."""

import asyncio
from typing import Dict
from sqlalchemy.orm import Session
from database.database import User, Transaction
from src.repository.user_repository import UserRepository


class TransactionService:
    """
    Сервис для управления транзакциями.
    
    Обеспечивает потокобезопасные операции с балансом пользователей.
    Использует asyncio.Lock для предотвращения race conditions.
    """

    def __init__(self, user_repo: UserRepository):
        """
        Инициализация сервиса транзакций.

        Args:
            user_repo: Репозиторий для работы с пользователями
        """
        self.user_repo = user_repo
        self._locks: Dict[int, asyncio.Lock] = {}

    def _get_lock(self, user_id: int) -> asyncio.Lock:
        """
        Получить lock для конкретного пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            asyncio.Lock для пользователя
        """
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    async def add_points(
        self,
        user_id: int,
        amount: int,
        reason: str,
        source_game: str = None
    ) -> User:
        """
        Добавить очки пользователю (атомарная операция).

        Args:
            user_id: ID пользователя
            amount: Количество очков для добавления
            reason: Причина начисления
            source_game: Источник начисления (название игры)

        Returns:
            Обновленный User

        Raises:
            ValueError: Если пользователь не найден
        """
        async with self._get_lock(user_id):
            user = self.user_repo.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Обновляем баланс пользователя
            user.balance += amount
            user.total_earned += amount

            # Создаем запись транзакции
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                transaction_type="credit",
                source_game=source_game,
                description=reason
            )
            self.user_repo.session.add(transaction)

            # Фиксируем изменения
            self.user_repo.session.commit()
            self.user_repo.session.refresh(user)

            return user

    async def subtract_points(
        self,
        user_id: int,
        amount: int,
        reason: str
    ) -> User:
        """
        Списать очки у пользователя (атомарная операция).

        Args:
            user_id: ID пользователя
            amount: Количество очков для списания
            reason: Причина списания

        Returns:
            Обновленный User

        Raises:
            ValueError: Если пользователь не найден или недостаточно средств
        """
        async with self._get_lock(user_id):
            user = self.user_repo.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            if user.balance < amount:
                raise ValueError(
                    f"Insufficient balance. User has {user.balance}, "
                    f"attempting to withdraw {amount}"
                )

            # Обновляем баланс пользователя
            user.balance -= amount

            # Создаем запись транзакции
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                transaction_type="debit",
                description=reason
            )
            self.user_repo.session.add(transaction)

            # Фиксируем изменения
            self.user_repo.session.commit()
            self.user_repo.session.refresh(user)

            return user

    async def transfer_points(
        self,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        reason: str
    ) -> tuple:
        """
        Перевести очки от одного пользователя другому (атомарная операция).

        Args:
            from_user_id: ID пользователя-отправителя
            to_user_id: ID пользователя-получателя
            amount: Количество очков для перевода
            reason: Причина перевода

        Returns:
            Кортеж (sender, receiver) - обновленные пользователи

        Raises:
            ValueError: Если пользователи не найдены или недостаточно средств
        """
        # Получаем locks в определенном порядке для предотвращения deadlock
        lock1 = self._get_lock(min(from_user_id, to_user_id))
        lock2 = self._get_lock(max(from_user_id, to_user_id))

        async with lock1:
            async with lock2:
                sender = self.user_repo.get(from_user_id)
                if not sender:
                    raise ValueError(f"Sender {from_user_id} not found")

                receiver = self.user_repo.get(to_user_id)
                if not receiver:
                    raise ValueError(f"Receiver {to_user_id} not found")

                if sender.balance < amount:
                    raise ValueError(
                        f"Insufficient balance. Sender has {sender.balance}, "
                        f"attempting to transfer {amount}"
                    )

                # Списываем у отправителя
                sender.balance -= amount

                # Добавляем получателю
                receiver.balance += amount

                # Создаем записи транзакций
                sender_transaction = Transaction(
                    user_id=sender.id,
                    amount=amount,
                    transaction_type="transfer_out",
                    description=f"{reason} (to user {to_user_id})"
                )
                receiver_transaction = Transaction(
                    user_id=receiver.id,
                    amount=amount,
                    transaction_type="transfer_in",
                    description=f"{reason} (from user {from_user_id})"
                )
                self.user_repo.session.add_all(
                    [sender_transaction, receiver_transaction]
                )

                # Фиксируем изменения
                self.user_repo.session.commit()
                self.user_repo.session.refresh(sender)
                self.user_repo.session.refresh(receiver)

                return sender, receiver

    def get_user_transactions(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> list:
        """
        Получить историю транзакций пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей
            offset: Смещение для пагинации

        Returns:
            Список транзакций
        """
        return self.user_repo.session.query(Transaction).filter(
            Transaction.user_id == user_id
        ).order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()

    def get_user_total_transactions(self, user_id: int) -> int:
        """
        Получить общее количество транзакций пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Количество транзакций
        """
        return self.user_repo.session.query(Transaction).filter(
            Transaction.user_id == user_id
        ).count()

"""Transaction service — финансовые операции с Unit of Work и per-user блокировками."""

import asyncio
from typing import Dict
from database.database import User, Transaction
from src.repository.user_repository import UserRepository
from src.repository.unit_of_work import UnitOfWork


class TransactionService:
    """
    Сервис транзакций.

    Мутирующие операции (add/subtract/transfer) используют UnitOfWork —
    каждая операция открывает собственную сессию, атомарно коммитит и закрывает.
    Read-only операции используют сессию из user_repo.

    asyncio.Lock на user_id предотвращает race conditions при параллельных запросах.
    """

    def __init__(self, user_repo: UserRepository):
        """
        Args:
            user_repo: Репозиторий пользователей (для read-only запросов).
        """
        self.user_repo = user_repo
        self._locks: Dict[int, asyncio.Lock] = {}

    def _get_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    async def add_points(
        self,
        user_id: int,
        amount: int,
        reason: str,
        source_game: str = None,
    ) -> User:
        """
        Начислить очки пользователю (атомарная операция).

        Args:
            user_id: Telegram ID пользователя.
            amount: Количество очков.
            reason: Причина начисления.
            source_game: Источник (название игры).

        Returns:
            Обновлённый объект User.

        Raises:
            ValueError: Если пользователь не найден.
        """
        async with self._get_lock(user_id):
            with UnitOfWork() as uow:
                user = uow.users.get_by_telegram_id(user_id)
                if not user:
                    raise ValueError(f"User {user_id} not found")

                user.balance += amount
                user.total_earned += amount

                uow.session.add(Transaction(
                    user_id=user.id,
                    amount=amount,
                    transaction_type="credit",
                    source_game=source_game,
                    description=reason,
                ))
                uow.commit()
                uow.session.refresh(user)
                return user

    async def subtract_points(
        self,
        user_id: int,
        amount: int,
        reason: str,
    ) -> User:
        """
        Списать очки у пользователя (атомарная операция).

        Args:
            user_id: Telegram ID пользователя.
            amount: Количество очков.
            reason: Причина списания.

        Returns:
            Обновлённый объект User.

        Raises:
            ValueError: Если пользователь не найден или недостаточно средств.
        """
        async with self._get_lock(user_id):
            with UnitOfWork() as uow:
                user = uow.users.get_by_telegram_id(user_id)
                if not user:
                    raise ValueError(f"User {user_id} not found")

                if user.balance < amount:
                    raise ValueError(
                        f"Insufficient balance: has {user.balance}, need {amount}"
                    )

                user.balance -= amount

                uow.session.add(Transaction(
                    user_id=user.id,
                    amount=amount,
                    transaction_type="debit",
                    description=reason,
                ))
                uow.commit()
                uow.session.refresh(user)
                return user

    async def transfer_points(
        self,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        reason: str,
    ) -> tuple:
        """
        Перевести очки между пользователями (атомарная операция).

        Args:
            from_user_id: Telegram ID отправителя.
            to_user_id: Telegram ID получателя.
            amount: Количество очков.
            reason: Причина перевода.

        Returns:
            Кортеж (sender, receiver) — обновлённые объекты User.

        Raises:
            ValueError: Если пользователи не найдены или недостаточно средств.
        """
        # Детерминированный порядок locks — защита от deadlock
        lock1 = self._get_lock(min(from_user_id, to_user_id))
        lock2 = self._get_lock(max(from_user_id, to_user_id))

        async with lock1:
            async with lock2:
                with UnitOfWork() as uow:
                    sender = uow.users.get_by_telegram_id(from_user_id)
                    if not sender:
                        raise ValueError(f"Sender {from_user_id} not found")

                    receiver = uow.users.get_by_telegram_id(to_user_id)
                    if not receiver:
                        raise ValueError(f"Receiver {to_user_id} not found")

                    if sender.balance < amount:
                        raise ValueError(
                            f"Insufficient balance: has {sender.balance}, need {amount}"
                        )

                    sender.balance -= amount
                    receiver.balance += amount

                    uow.session.add_all([
                        Transaction(
                            user_id=sender.id,
                            amount=amount,
                            transaction_type="transfer_out",
                            description=f"{reason} (to user {to_user_id})",
                        ),
                        Transaction(
                            user_id=receiver.id,
                            amount=amount,
                            transaction_type="transfer_in",
                            description=f"{reason} (from user {from_user_id})",
                        ),
                    ])
                    uow.commit()
                    uow.session.refresh(sender)
                    uow.session.refresh(receiver)
                    return sender, receiver

    def get_user_transactions(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list:
        """
        История транзакций пользователя.

        Args:
            user_id: Внутренний ID пользователя (не Telegram).
            limit: Максимум записей.
            offset: Смещение для пагинации.

        Returns:
            Список Transaction.
        """
        return (
            self.user_repo.session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_user_total_transactions(self, user_id: int) -> int:
        """
        Общее количество транзакций пользователя.

        Args:
            user_id: Внутренний ID пользователя (не Telegram).

        Returns:
            Количество транзакций.
        """
        return (
            self.user_repo.session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .count()
        )

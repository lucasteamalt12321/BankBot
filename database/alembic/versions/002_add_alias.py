"""Add alias column to users

Revision ID: 002
Revises: 001
Create Date: 2026-04-06

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("alias", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("daily_streak", sa.Integer, default=0))
    op.add_column("users", sa.Column("last_daily", sa.DateTime, nullable=True))
    op.add_column("users", sa.Column("total_earned", sa.Integer, default=0))
    op.add_column("users", sa.Column("last_activity", sa.DateTime, nullable=True))
    op.add_column("users", sa.Column("is_vip", sa.Boolean, default=False))
    op.add_column("users", sa.Column("vip_until", sa.DateTime, nullable=True))
    op.add_column("users", sa.Column("is_admin", sa.Boolean, default=False))
    op.add_column("users", sa.Column("sticker_unlimited", sa.Boolean, default=False))
    op.add_column(
        "users", sa.Column("sticker_unlimited_until", sa.DateTime, nullable=True)
    )
    op.add_column("users", sa.Column("total_purchases", sa.Integer, default=0))


def downgrade() -> None:
    op.drop_column("users", "total_purchases")
    op.drop_column("users", "sticker_unlimited_until")
    op.drop_column("users", "sticker_unlimited")
    op.drop_column("users", "is_admin")
    op.drop_column("users", "vip_until")
    op.drop_column("users", "is_vip")
    op.drop_column("users", "last_activity")
    op.drop_column("users", "total_earned")
    op.drop_column("users", "last_daily")
    op.drop_column("users", "daily_streak")
    op.drop_column("users", "alias")

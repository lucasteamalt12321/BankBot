"""Use BIGINT Telegram IDs and persist response modes.

Revision ID: 004
Revises: 003
Create Date: 2026-05-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.alter_column(
            "users",
            "telegram_id",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=True,
        )

    op.create_table(
        "response_mode_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_response_mode_settings_global",
        "response_mode_settings",
        ["is_global"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.drop_index("ix_response_mode_settings_global", table_name="response_mode_settings")
    op.drop_table("response_mode_settings")

    if dialect == "postgresql":
        op.alter_column(
            "users",
            "telegram_id",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=True,
        )

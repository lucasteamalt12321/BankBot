"""Add linked_vk_accounts table for VK Mini App user linking.

Revision ID: 011
Revises: 010
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "linked_vk_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vk_user_id", sa.String(20), nullable=False),
        sa.Column("tg_user_id", sa.String(20), nullable=False),
        sa.Column("link_code", sa.String(10), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_linked_vk_accounts_vk_user_id", "linked_vk_accounts", ["vk_user_id"], unique=True)
    op.create_index("ix_linked_vk_accounts_tg_user_id", "linked_vk_accounts", ["tg_user_id"])
    op.create_index("ix_linked_vk_accounts_link_code", "linked_vk_accounts", ["link_code"])


def downgrade() -> None:
    op.drop_table("linked_vk_accounts")

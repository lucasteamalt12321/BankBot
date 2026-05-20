"""Add user_resources and conversion_rates tables.

Revision ID: 005
Revises: 004
Create Date: 2026-05-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bot_name", sa.String(length=50), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_user_resources_user_bot_resource", "user_resources", ["user_id", "bot_name", "resource_type"], unique=True)

    op.create_table(
        "conversion_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_name", sa.String(length=50), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("k", sa.DECIMAL(10, 4), nullable=False, server_default=sa.text("1.0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_conversion_rates_bot_resource", "conversion_rates", ["bot_name", "resource_type"], unique=True)

    # Insert default conversion rates
    op.execute("""
        INSERT INTO conversion_rates (bot_name, resource_type, k) VALUES
        ('gusya_cards', 'coins', 1.0),
        ('gdcards', 'orbs', 1.0),
        ('shmalala', 'money', 1.0)
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_conversion_rates_bot_resource", table_name="conversion_rates")
    op.drop_table("conversion_rates")
    op.drop_index("ix_user_resources_user_bot_resource", table_name="user_resources")
    op.drop_table("user_resources")

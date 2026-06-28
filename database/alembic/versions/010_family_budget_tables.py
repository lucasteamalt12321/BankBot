"""Add Family Budget tables: families, family_members, budget_transactions, transaction_details, debts, payments.

Revision ID: 010
Revises: 009
Create Date: 2026-06-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "families",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("admin_id", sa.String(length=100), nullable=False),
        sa.Column("invite_code", sa.String(length=6), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_families_invite_code", "families", ["invite_code"])
    op.create_index("ix_families_admin_id", "families", ["admin_id"])

    op.create_table(
        "family_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("joined_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_family_members_family_id", "family_members", ["family_id"])
    op.create_index("ix_family_members_user_id", "family_members", ["user_id"])

    op.create_table(
        "budget_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payer_id", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_budget_transactions_family_id", "budget_transactions", ["family_id"])

    op.create_table(
        "transaction_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("budget_transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("for_whom_id", sa.String(length=100), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
    )
    op.create_index("ix_transaction_details_transaction_id", "transaction_details", ["transaction_id"])

    op.create_table(
        "debts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("debtor_id", sa.String(length=100), nullable=False),
        sa.Column("creditor_id", sa.String(length=100), nullable=False),
        sa.Column("amount_left", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_debts_family_id", "debts", ["family_id"])
    op.create_index("ix_debts_debtor_id", "debts", ["debtor_id"])
    op.create_index("ix_debts_creditor_id", "debts", ["creditor_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("debtor_id", sa.String(length=100), nullable=False),
        sa.Column("creditor_id", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_payments_family_id", "payments", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_payments_family_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_debts_creditor_id", table_name="debts")
    op.drop_index("ix_debts_debtor_id", table_name="debts")
    op.drop_index("ix_debts_family_id", table_name="debts")
    op.drop_table("debts")
    op.drop_index("ix_transaction_details_transaction_id", table_name="transaction_details")
    op.drop_table("transaction_details")
    op.drop_index("ix_budget_transactions_family_id", table_name="budget_transactions")
    op.drop_table("budget_transactions")
    op.drop_index("ix_family_members_user_id", table_name="family_members")
    op.drop_index("ix_family_members_family_id", table_name="family_members")
    op.drop_table("family_members")
    op.drop_index("ix_families_admin_id", table_name="families")
    op.drop_index("ix_families_invite_code", table_name="families")
    op.drop_table("families")

"""Create missing tables from current SQLAlchemy metadata.

Revision ID: 003
Revises: 002
Create Date: 2026-04-06

"""

from typing import Sequence, Union

from alembic import op

from database.database import Base

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create any tables missing from the incomplete early Alembic baseline.
    existing_tables = set(bind.dialect.get_table_names(bind))
    metadata = Base.metadata

    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            table.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()

    existing_tables = set(bind.dialect.get_table_names(bind))
    metadata = Base.metadata

    # Only drop tables introduced by this migration; keep legacy baseline tables.
    baseline_tables = {"users", "transactions", "balances"}

    for table in reversed(metadata.sorted_tables):
        if table.name in existing_tables and table.name not in baseline_tables:
            table.drop(bind=bind)

"""Add D&D AI Master fields and tables.

Extends dnd_sessions, dnd_characters; adds dnd_session_logs, dnd_fixes.

Revision ID: 012
Revises: 011
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend dnd_sessions
    op.add_column("dnd_sessions", sa.Column("paused_at", sa.DateTime(), nullable=True))
    op.add_column("dnd_sessions", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column("dnd_sessions", sa.Column("book_content", sa.Text(), nullable=True))
    op.add_column("dnd_sessions", sa.Column("current_scene", sa.Text(), nullable=True))
    op.add_column("dnd_sessions", sa.Column("context_summary", sa.Text(), nullable=True))
    op.add_column("dnd_sessions", sa.Column("ai_system_prompt", sa.Text(), nullable=True))
    op.add_column("dnd_sessions", sa.Column("last_ai_response", sa.Text(), nullable=True))
    op.add_column("dnd_sessions", sa.Column("chapter_breakdown", sa.JSON(), nullable=True))

    # Extend dnd_characters
    op.add_column("dnd_characters", sa.Column("race", sa.String(length=50), nullable=True))
    op.add_column("dnd_characters", sa.Column("alignment", sa.String(length=20), nullable=True))
    op.add_column("dnd_characters", sa.Column("hit_points", sa.Integer(), server_default="10"))
    op.add_column("dnd_characters", sa.Column("max_hit_points", sa.Integer(), server_default="10"))
    op.add_column("dnd_characters", sa.Column("armor_class", sa.Integer(), server_default="10"))
    op.add_column("dnd_characters", sa.Column("spells", sa.JSON(), nullable=True))
    op.add_column("dnd_characters", sa.Column("is_active", sa.Boolean(), server_default="1"))
    op.add_column("dnd_characters", sa.Column("last_active_at", sa.DateTime(), nullable=True))

    # Create dnd_session_logs table
    op.create_table(
        "dnd_session_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("dnd_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("dnd_characters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message_type", sa.String(length=20)),
        sa.Column("content", sa.Text()),
        sa.Column("ai_context", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_session_logs_session_id", "dnd_session_logs", ["session_id"])
    op.create_index("ix_session_logs_created_at", "dnd_session_logs", ["created_at"])

    # Create dnd_fixes table
    op.create_table(
        "dnd_fixes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("dnd_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("dnd_characters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("original_context", sa.Text()),
        sa.Column("correction", sa.Text()),
        sa.Column("applied", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_dnd_fixes_session_id", "dnd_fixes", ["session_id"])


def downgrade() -> None:
    op.drop_table("dnd_fixes")
    op.drop_table("dnd_session_logs")

    columns_to_drop_characters = ["race", "alignment", "hit_points", "max_hit_points", "armor_class", "spells", "is_active", "last_active_at"]
    for col in columns_to_drop_characters:
        op.drop_column("dnd_characters", col)

    columns_to_drop_sessions = ["paused_at", "completed_at", "book_content", "current_scene", "context_summary", "ai_system_prompt", "last_ai_response", "chapter_breakdown"]
    for col in columns_to_drop_sessions:
        op.drop_column("dnd_sessions", col)

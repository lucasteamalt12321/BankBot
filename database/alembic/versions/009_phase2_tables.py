"""Add Phase 2 tables: GD, Chess, Universe, AI, Mom modules.

Revision ID: 009
Revises: 005
Create Date: 2026-05-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========== Geometry Dash Module ==========
    
    # Table: levels
    op.create_table(
        "levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("position", sa.Integer(), nullable=False, unique=True),
        sa.Column("external_link", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_levels_position", "levels", ["position"])
    
    # Table: submissions
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("level_id", sa.Integer(), sa.ForeignKey("levels.id", ondelete="CASCADE"), nullable=True),
        sa.Column("video_file_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])
    op.create_index("ix_submissions_status", "submissions", ["status"])
    op.create_index("ix_submissions_level_id", "submissions", ["level_id"])
    
    # Add check constraint for status
    op.execute("""
        ALTER TABLE submissions ADD CONSTRAINT check_submission_status 
        CHECK (status IN ('pending', 'approved', 'rejected'))
    """)
    
    # Table: player_stats
    op.create_table(
        "player_stats",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("hardest_level_id", sa.Integer(), sa.ForeignKey("levels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("total_approved", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_player_stats_hardest_level", "player_stats", ["hardest_level_id"])
    
    # Table: level_completions
    op.create_table(
        "level_completions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("level_id", sa.Integer(), sa.ForeignKey("levels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id", "level_id"),
    )
    op.create_index("ix_level_completions_level_id", "level_completions", ["level_id"])
    
    # ========== Chess Module ==========
    
    # Table: chess_accounts
    op.create_table(
        "chess_accounts",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("lichess_username", sa.String(length=50), nullable=False, unique=True),
        sa.Column("linked_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_chess_accounts_lichess_username", "chess_accounts", ["lichess_username"])
    
    # Table: user_coins (для наград за /puzzle)
    op.create_table(
        "user_coins",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_puzzle_at", sa.DateTime(), nullable=True),
    )
    
    # ========== Universe Module ==========
    
    # Table: infection_status
    op.create_table(
        "infection_status",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("virus_type", sa.String(length=50), nullable=True),
        sa.Column("infected_at", sa.DateTime(), nullable=True),
        sa.Column("tea_cooldown_until", sa.DateTime(), nullable=True),
    )
    
    # Table: daily_prayer_log
    op.create_table(
        "daily_prayer_log",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("prayer_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "prayer_date"),
    )
    op.create_index("ix_daily_prayer_log_date", "daily_prayer_log", ["prayer_date"])
    
    # ========== AI Module ==========
    
    # Table: user_preferences
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("preferred_ai_model", sa.String(length=50), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    # AI Module
    op.drop_table("user_preferences")
    
    # Universe Module
    op.drop_index("ix_daily_prayer_log_date", table_name="daily_prayer_log")
    op.drop_table("daily_prayer_log")
    op.drop_table("infection_status")
    
    # Chess Module
    op.drop_table("user_coins")
    op.drop_index("ix_chess_accounts_lichess_username", table_name="chess_accounts")
    op.drop_table("chess_accounts")
    
    # Geometry Dash Module
    op.drop_index("ix_level_completions_level_id", table_name="level_completions")
    op.drop_table("level_completions")
    op.drop_index("ix_player_stats_hardest_level", table_name="player_stats")
    op.drop_table("player_stats")
    op.drop_index("ix_submissions_level_id", table_name="submissions")
    op.drop_index("ix_submissions_status", table_name="submissions")
    op.drop_index("ix_submissions_user_id", table_name="submissions")
    op.drop_table("submissions")
    op.drop_index("ix_levels_position", table_name="levels")
    op.drop_table("levels")

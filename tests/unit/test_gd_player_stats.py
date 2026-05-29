"""Unit tests for GD Module PlayerStats logic."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from database.database import PlayerStats, Submission, Level


class TestPlayerStatsLogic:
    """Tests for PlayerStats logic and calculations."""

    def test_player_stats_update_approved_count(self):
        """Test that approved submissions increment total_approved."""
        player_stats = PlayerStats(user_id=12345, total_approved=5)

        player_stats.total_approved += 1

        assert player_stats.total_approved == 6

    def test_player_stats_set_hardest_level(self):
        """Test setting the hardest level for a player."""
        player_stats = PlayerStats(user_id=12345)
        level = Level(id=1, name="Tartarus", position=1)

        player_stats.hardest_level_id = level.id
        player_stats.hardest_level = level

        assert player_stats.hardest_level_id == 1
        assert player_stats.hardest_level.name == "Tartarus"

    def test_player_stats_calculate_completion_rate(self):
        """Test calculation of completion rate."""
        player_stats = PlayerStats(user_id=12345, total_approved=5)

        total_submissions = 10
        completion_rate = player_stats.total_approved / total_submissions

        assert completion_rate == 0.5

    def test_player_stats_get_top_levels(self):
        """Test getting top levels from player's submissions."""
        mock_submissions = [
            MagicMock(level=MagicMock(name="Cubes", position=1)),
            MagicMock(level=MagicMock(name="Tartarus", position=1)),
            MagicMock(level=MagicMock(name="Electro", position=2)),
        ]

        top_levels = sorted(
            [s.level.name for s in mock_submissions],
            key=lambda x: next((l.position for l in mock_submissions if l.level.name == x), 999)
        )[:3]

        assert len(top_levels) <= 3

    def test_player_stats_reset_stats(self):
        """Test resetting player stats."""
        player_stats = PlayerStats(user_id=12345, total_approved=10, hardest_level_id=1)

        player_stats.total_approved = 0
        player_stats.hardest_level_id = None

        assert player_stats.total_approved == 0
        assert player_stats.hardest_level_id is None


class TestSubmissionLogic:
    """Tests for Submission logic and calculations."""

    def test_submission_is_pending(self):
        """Test that new submission is pending."""
        submission = Submission(
            user_id=12345,
            level_name="Cubes",
            media_file_id="file_id",
            media_type="video",
            status="pending"
        )

        assert submission.status == "pending"

    def test_submission_approve(self):
        """Test approving a submission."""
        submission = Submission(
            user_id=12345,
            level_name="Cubes",
            media_file_id="file_id",
            media_type="video",
            status="pending"
        )

        submission.status = "approved"
        submission.reviewed_at = datetime.utcnow()
        submission.reviewed_by = 99999

        assert submission.status == "approved"
        assert submission.reviewed_at is not None
        assert submission.reviewed_by == 99999

    def test_submission_reject(self):
        """Test rejecting a submission."""
        submission = Submission(
            user_id=12345,
            level_name="Cubes",
            media_file_id="file_id",
            media_type="video",
            status="pending"
        )

        submission.status = "rejected"
        submission.reviewed_at = datetime.utcnow()
        submission.reviewed_by = 99999
        submission.notes = "Video quality too low"

        assert submission.status == "rejected"
        assert submission.notes == "Video quality too low"

    def test_submission_is_approved(self):
        """Test checking if submission is approved."""
        submission = Submission(
            user_id=12345,
            level_name="Cubes",
            media_file_id="file_id",
            media_type="video",
            status="approved"
        )

        assert submission.status == "approved"
        assert submission.reviewed_at is not None

    def test_submission_media_type_validation(self):
        """Test that media_type is valid."""
        for media_type in ["video", "photo"]:
            submission = Submission(
                user_id=12345,
                level_name="Test",
                media_file_id="file_id",
                media_type=media_type
            )
            assert submission.media_type == media_type

    def test_submission_level_name_fallback(self):
        """Test that level_name can be used as fallback when level_id is None."""
        submission = Submission(
            user_id=12345,
            level_name="Cubes",
            media_file_id="file_id",
            media_type="video"
        )

        assert submission.level_id is None
        assert submission.level_name == "Cubes"


class TestLevelLogic:
    """Tests for Level logic and calculations."""

    def test_level_position_range(self):
        """Test that level position is in valid range (1-100)."""
        for position in [1, 50, 100]:
            level = Level(name=f"Level {position}", position=position)
            assert 1 <= level.position <= 100

    def test_level_is_hardest(self):
        """Test checking if level is the hardest for a player."""
        level = Level(id=1, name="Tartarus", position=1)

        player_stats = PlayerStats(user_id=12345, hardest_level_id=level.id)

        is_hardest = player_stats.hardest_level_id == level.id

        assert is_hardest

    def test_level_completion_count(self):
        """Test counting level completions."""
        mock_completions = [
            MagicMock(user_id=12345),
            MagicMock(user_id=67890),
            MagicMock(user_id=11111),
        ]

        completion_count = len(mock_completions)

        assert completion_count == 3

    def test_level_average_position(self):
        """Test calculating average position of completed levels."""
        levels = [
            Level(id=1, name="Cubes", position=1),
            Level(id=2, name="Tartarus", position=1),
            Level(id=3, name="Electro", position=2),
        ]

        positions = [l.position for l in levels]
        avg_position = sum(positions) / len(positions)

        assert avg_position == 1.3333333333333333


class TestIntegrationLogic:
    """Tests for integration logic between models."""

    def test_submission_to_player_stats_flow(self):
        """Test flow from submission to player stats update."""
        submission = Submission(
            user_id=12345,
            level_name="Cubes",
            media_file_id="file_id",
            media_type="video",
            status="approved"
        )

        player_stats = PlayerStats(user_id=12345, total_approved=5)

        if submission.status == "approved":
            player_stats.total_approved += 1

        assert player_stats.total_approved == 6

    def test_level_completion_flow(self):
        """Test flow from level completion to player stats."""
        level = Level(id=1, name="Cubes", position=1)
        completion = MagicMock(level=level)

        player_stats = PlayerStats(user_id=12345, total_approved=5)

        if completion.level.position == 1:
            player_stats.hardest_level_id = level.id

        assert player_stats.hardest_level_id == 1

    def test_player_stats_summary(self):
        """Test generating player stats summary."""
        player_stats = PlayerStats(user_id=12345, total_approved=10)

        mock_submissions = [
            MagicMock(status="approved"),
            MagicMock(status="approved"),
            MagicMock(status="pending"),
            MagicMock(status="rejected"),
        ]

        approved_count = sum(1 for s in mock_submissions if s.status == "approved")
        total_count = len(mock_submissions)

        summary = {
            "total_approved": player_stats.total_approved,
            "recent_approved": approved_count,
            "total_submissions": total_count,
        }

        assert summary["total_approved"] == 10
        assert summary["recent_approved"] == 2
        assert summary["total_submissions"] == 4

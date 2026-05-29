"""Unit tests for GD Module database models."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from database.database import Submission, PlayerStats, Level, LevelCompletion


class TestSubmissionModel:
    """Tests for Submission model."""

    def test_submission_creation(self):
        """Test Submission model creation with required fields."""
        submission = Submission(
            user_id=12345,
            level_name="Cubes",
            media_file_id="video_file_id_123",
            media_type="video",
            status="pending",
            submitted_at=datetime.utcnow()
        )

        assert submission.user_id == 12345
        assert submission.level_name == "Cubes"
        assert submission.media_file_id == "video_file_id_123"
        assert submission.media_type == "video"
        assert submission.status == "pending"
        assert submission.submitted_at is not None

    def test_submission_optional_fields(self):
        """Test Submission model with optional fields."""
        submission = Submission(
            user_id=12345,
            level_id=1,
            level_name="Tartarus",
            media_file_id="photo_file_id_456",
            media_type="photo",
            status="approved",
            reviewed_at=datetime.utcnow(),
            reviewed_by=99999,
            notes="Looks good!"
        )

        assert submission.level_id == 1
        assert submission.level_name == "Tartarus"
        assert submission.media_type == "photo"
        assert submission.status == "approved"
        assert submission.reviewed_at is not None
        assert submission.reviewed_by == 99999
        assert submission.notes == "Looks good!"

    def test_submission_default_values(self):
        """Test Submission model default values."""
        submission = Submission(
            user_id=12345,
            level_name="Test",
            media_file_id="file_id",
            media_type="video"
        )

        assert submission.status == "pending"
        assert submission.submitted_at is not None
        assert submission.level_id is None
        assert submission.reviewed_at is None
        assert submission.reviewed_by is None
        assert submission.notes is None

    def test_submission_relationships(self):
        """Test Submission model relationships."""
        level = Level(id=1, name="Cubes", position=1)
        submission = Submission(
            user_id=12345,
            level_id=1,
            level_name="Cubes",
            media_file_id="file_id",
            media_type="video"
        )
        submission.level = level

        assert submission.level == level
        assert submission.level.name == "Cubes"


class TestPlayerStatsModel:
    """Tests for PlayerStats model."""

    def test_player_stats_creation(self):
        """Test PlayerStats model creation."""
        player_stats = PlayerStats(
            user_id=12345,
            total_approved=5
        )

        assert player_stats.user_id == 12345
        assert player_stats.total_approved == 5
        assert player_stats.hardest_level_id is None

    def test_player_stats_default_values(self):
        """Test PlayerStats model default values."""
        player_stats = PlayerStats(user_id=12345)

        assert player_stats.total_approved == 0
        assert player_stats.hardest_level_id is None

    def test_player_stats_relationship(self):
        """Test PlayerStats model relationship with Level."""
        level = Level(id=1, name="Tartarus", position=1)
        player_stats = PlayerStats(user_id=12345, hardest_level_id=1)
        player_stats.hardest_level = level

        assert player_stats.hardest_level == level
        assert player_stats.hardest_level.name == "Tartarus"


class TestLevelModel:
    """Tests for Level model."""

    def test_level_creation(self):
        """Test Level model creation."""
        level = Level(
            name="Cubes",
            position=1,
            external_link="https://geometry-dash.fandom.com/wiki/Cubes"
        )

        assert level.name == "Cubes"
        assert level.position == 1
        assert level.external_link == "https://geometry-dash.fandom.com/wiki/Cubes"
        assert level.created_at is not None

    def test_level_default_values(self):
        """Test Level model default values."""
        level = Level(name="Test", position=10)

        assert level.external_link is None
        assert level.created_at is not None

    def test_level_relationships(self):
        """Test Level model relationships."""
        level = Level(id=1, name="Cubes", position=1)
        submission = Submission(
            user_id=12345,
            level_id=1,
            level_name="Cubes",
            media_file_id="file_id",
            media_type="video"
        )
        completion = LevelCompletion(user_id=12345, level_id=1)

        level.submissions = [submission]
        level.completions = [completion]

        assert len(level.submissions) == 1
        assert len(level.completions) == 1
        assert level.submissions[0].level == level
        assert level.completions[0].level == level


class TestLevelCompletionModel:
    """Tests for LevelCompletion model."""

    def test_level_completion_creation(self):
        """Test LevelCompletion model creation."""
        completion = LevelCompletion(
            user_id=12345,
            level_id=1,
            completed_at=datetime.utcnow()
        )

        assert completion.user_id == 12345
        assert completion.level_id == 1
        assert completion.completed_at is not None

    def test_level_completion_default_values(self):
        """Test LevelCompletion model default values."""
        completion = LevelCompletion(user_id=12345, level_id=1)

        assert completion.completed_at is not None

    def test_level_completion_relationship(self):
        """Test LevelCompletion model relationship with Level."""
        level = Level(id=1, name="Cubes", position=1)
        completion = LevelCompletion(user_id=12345, level_id=1)
        completion.level = level

        assert completion.level == level
        assert completion.level.name == "Cubes"


class TestModelValidation:
    """Tests for model validation logic."""

    def test_submission_media_type_validation(self):
        """Test that media_type is either video or photo."""
        for media_type in ["video", "photo"]:
            submission = Submission(
                user_id=12345,
                level_name="Test",
                media_file_id="file_id",
                media_type=media_type
            )
            assert submission.media_type == media_type

    def test_submission_status_validation(self):
        """Test that status can be pending, approved, or rejected."""
        for status in ["pending", "approved", "rejected"]:
            submission = Submission(
                user_id=12345,
                level_name="Test",
                media_file_id="file_id",
                media_type="video",
                status=status
            )
            assert submission.status == status

    def test_level_position_range(self):
        """Test that level position is in valid range (1-100)."""
        for position in [1, 50, 100]:
            level = Level(name=f"Level {position}", position=position)
            assert level.position == position

    def test_player_stats_positive_values(self):
        """Test that player stats have non-negative values."""
        player_stats = PlayerStats(user_id=12345, total_approved=10)
        assert player_stats.total_approved >= 0

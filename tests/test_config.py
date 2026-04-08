"""Tests for configuration — verify no personal paths in defaults."""

from yt_transcript.config import Settings


def test_no_personal_paths_in_defaults():
    """Default settings must not contain personal machine paths."""
    s = Settings(
        _env_file=None,  # don't load .env
    )
    # notes_dir should default to None (disabled)
    assert s.notes_dir is None
    assert s.notes_enabled is False

    # Database URL should not contain a personal username
    assert "justin" not in s.database_url
    assert "justin" not in s.database_url_sync

    # ASR URL should not reference personal machines
    assert "studio.local" not in s.asr_worker_url

    # No path should reference a personal home directory
    for field_name in ["database_url", "database_url_sync", "asr_worker_url"]:
        value = str(getattr(s, field_name))
        assert "/Users/" not in value
        assert "Justyn" not in value
        assert "obsidian" not in value.lower()


def test_notes_enabled_when_configured():
    s = Settings(
        _env_file=None,
        notes_dir="/tmp/test-notes",
    )
    assert s.notes_enabled is True


def test_notes_disabled_when_not_configured():
    s = Settings(
        _env_file=None,
    )
    assert s.notes_enabled is False

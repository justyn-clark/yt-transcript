"""Tests for health check endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from yt_transcript.api.app import app

    return TestClient(app)


def test_health_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_ready_db_ok(client):
    """Readiness check passes when DB is reachable."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()

    with patch("yt_transcript.api.app.async_session", return_value=mock_session):
        with patch("yt_transcript.api.app.settings") as mock_settings:
            mock_settings.database_enabled = True
            mock_settings.notes_enabled = False
            response = client.get("/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"


def test_health_ready_db_down(client):
    """Readiness check fails when DB is unreachable."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(side_effect=ConnectionRefusedError("connection refused"))

    with patch("yt_transcript.api.app.async_session", return_value=mock_session):
        with patch("yt_transcript.api.app.settings") as mock_settings:
            mock_settings.database_enabled = True
            mock_settings.notes_enabled = False
            response = client.get("/health/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert "failed" in data["checks"]["database"]


def test_health_ready_notes_configured_writable(client):
    """Readiness check reports notes_dir as ok when writable."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()

    with patch("yt_transcript.api.app.async_session", return_value=mock_session):
        with patch("yt_transcript.api.app.settings") as mock_settings:
            mock_settings.database_enabled = True
            mock_settings.notes_enabled = True
            mock_settings.notes_dir = "/tmp/test-notes"
            with patch("yt_transcript.api.app.check_notes_dir_writable", return_value=True):
                response = client.get("/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["checks"]["notes_dir"] == "ok"


def test_health_ready_notes_not_configured(client):
    """Readiness check reports notes_dir as not_configured when unset."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()

    with patch("yt_transcript.api.app.async_session", return_value=mock_session):
        with patch("yt_transcript.api.app.settings") as mock_settings:
            mock_settings.database_enabled = True
            mock_settings.notes_enabled = False
            response = client.get("/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["checks"]["notes_dir"] == "not_configured"


def test_health_ready_skips_db_when_capability_disabled(client):
    """Readiness stays healthy for ingest-only deployments."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(side_effect=ConnectionRefusedError("connection refused"))

    with patch("yt_transcript.api.app.async_session", return_value=mock_session):
        with patch("yt_transcript.api.app.settings") as mock_settings:
            mock_settings.database_enabled = False
            mock_settings.notes_enabled = False
            response = client.get("/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "not_required"

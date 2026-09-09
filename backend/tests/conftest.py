import os

# Ensure required env vars exist before app modules import Settings().
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_pytest_only")
os.environ.setdefault("ELEVENLABS_API_KEY", "test_key")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import get_user_repository
from app.services.voice_service import get_voice_repository


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Each test starts with clean in-memory repositories."""
    get_user_repository()._by_id.clear()
    get_user_repository()._by_email.clear()
    get_voice_repository()._voices.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "founder@finraksha.ai", "password": "supersecure123", "full_name": "Test Founder"},
    )
    resp = client.post(
        "/api/v1/auth/login-json", json={"email": "founder@finraksha.ai", "password": "supersecure123"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

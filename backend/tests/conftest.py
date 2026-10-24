"""Tests run against SQLite + local storage with the LLM and PDF renderer faked out,
so they need no MySQL, S3, Groq key or Chromium."""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = f"{_tmp}/storage"
os.environ["JWT_SECRET"] = "test-secret-that-is-at-least-32-bytes-long"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.schemas import Profile  # noqa: E402


class FakeLLM:
    def parse_resume(self, text: str) -> Profile:
        return Profile.model_validate({
            "basics": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
            "summary": "Mathematician and first programer.",
            "skills": ["Python", "Analysis"],
        })

    def correct_profile(self, profile: Profile) -> Profile:
        p = profile.model_copy(deep=True)
        p.summary = p.summary.replace("programer", "programmer")
        return p


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.workers.tasks.get_llm_client", lambda: FakeLLM())
    monkeypatch.setattr("app.services.export_service.html_to_pdf", lambda html: b"%PDF-1.4 fake")
    yield


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    client.post("/auth/signup", json={"email": "ada@example.com", "password": "password123"})
    tokens = client.post("/auth/login", json={"email": "ada@example.com", "password": "password123"}).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}

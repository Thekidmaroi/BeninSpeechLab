import pytest


@pytest.fixture(autouse=True)
def admin_credentials(monkeypatch):
    monkeypatch.setenv("BENINSPEECH_ADMIN_PASSWORD", "test-password-not-for-production")
    monkeypatch.setenv("BENINSPEECH_SESSION_SECRET", "test-only-session-secret-long-enough-1234567890")


def login_admin(client):
    response = client.post("/v1/admin/login", json={"password": "test-password-not-for-production"}, follow_redirects=False)
    assert response.status_code == 303
    csrf = client.get("/v1/admin/session")
    assert csrf.status_code == 200
    return {"X-CSRF-Token": csrf.json()["csrf_token"]}

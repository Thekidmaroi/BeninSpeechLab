"""Regression tests for BeninSpeechLab's role-based access controls."""
import pytest
from fastapi.testclient import TestClient

from beninspeechlab.api import app
from beninspeechlab.security import COOKIE, issue_session


@pytest.fixture(autouse=True)
def session_secret(monkeypatch):
    monkeypatch.setenv("BENINSPEECH_SESSION_SECRET", "role-test-secret-" + "x" * 48)


@pytest.mark.parametrize(
    "role,stats_status,export_status",
    [
        ("super_admin", 200, 200),
        ("manager", 200, 403),
        ("annotator", 403, 403),
    ],
)
def test_role_restrictions(role, stats_status, export_status, monkeypatch, tmp_path):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    with TestClient(app) as client:
        client.cookies.set(COOKIE, issue_session(role))
        assert client.get("/v1/admin/session").json()["role"] == role
        assert client.get("/v1/stats").status_code == stats_status
        # An authorized export may return 422 for an empty corpus; only test
        # that authorization does not reject the super_admin.
        result = client.get("/v1/export/asr")
        if export_status == 200:
            assert result.status_code != 403
        else:
            assert result.status_code == export_status


@pytest.mark.parametrize("role", ["super_admin", "manager", "annotator"])
def test_every_role_can_read_recordings(role, monkeypatch, tmp_path):
    monkeypatch.setenv("BENINSPEECH_DATA", str(tmp_path))
    with TestClient(app) as client:
        client.cookies.set(COOKIE, issue_session(role))
        assert client.get("/v1/recordings").status_code == 200


def test_unauthenticated_requests_are_rejected():
    with TestClient(app) as client:
        assert client.get("/v1/admin/session").status_code == 401
        assert client.get("/v1/recordings").status_code == 401
        assert client.get("/v1/stats").status_code == 401
        assert client.get("/v1/export/asr").status_code == 401


@pytest.mark.parametrize("role", ["super_admin", "manager", "annotator"])
def test_review_requires_csrf(role):
    with TestClient(app) as client:
        client.cookies.set(COOKIE, issue_session(role))
        response = client.patch(
            "/v1/recordings/nonexistent/review",
            json={"transcript": "test", "status": "approved"},
        )
        assert response.status_code == 403


def test_annotator_cannot_approve_even_with_valid_csrf():
    with TestClient(app) as client:
        client.cookies.set(COOKIE, issue_session("annotator"))
        csrf = client.get("/v1/admin/session").json()["csrf_token"]
        response = client.patch(
            "/v1/recordings/nonexistent/review",
            json={"transcript": "test", "status": "approved"},
            headers={"x-csrf-token": csrf},
        )
        assert response.status_code == 403


@pytest.mark.parametrize(
    "role,expected",
    [
        ("super_admin", {"read_stats", "read_recordings", "review_recordings", "approve_recordings", "export_corpus"}),
        ("manager", {"read_stats", "read_recordings", "review_recordings", "approve_recordings"}),
        ("annotator", {"read_recordings", "review_recordings"}),
    ],
)
def test_session_exposes_effective_permissions(role, expected):
    with TestClient(app) as client:
        client.cookies.set(COOKIE, issue_session(role))
        response = client.get("/v1/admin/session")
        assert response.status_code == 200
        assert set(response.json()["permissions"]) == expected


@pytest.mark.parametrize("role", ["manager", "annotator"])
def test_only_super_admin_can_list_users(role):
    with TestClient(app) as client:
        client.cookies.set(COOKIE, issue_session(role))
        assert client.get("/v1/admin/users").status_code == 403


def test_super_admin_users_requires_service_account_configuration(monkeypatch):
    monkeypatch.delenv("BENINSPEECH_KC_ADMIN_CLIENT_ID", raising=False)
    monkeypatch.delenv("BENINSPEECH_KC_ADMIN_CLIENT_SECRET", raising=False)
    with TestClient(app) as client:
        client.cookies.set(COOKIE, issue_session("super_admin"))
        assert client.get("/v1/admin/users").status_code == 503

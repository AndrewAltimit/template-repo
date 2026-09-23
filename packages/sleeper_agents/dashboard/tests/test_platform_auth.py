"""Tests for dashboard authentication, registration policy and job-launch permissions."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.authentication import (  # noqa: E402
    MIN_PASSWORD_LENGTH,
    AuthManager,
    registration_enabled,
    user_can_launch_jobs,
    validate_new_credentials,
)

STRONG_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def auth(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHBOARD_ADMIN_PASSWORD", "admin-initial-password-1")
    monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)
    return AuthManager(db_path=tmp_path / "users.db")


class TestRegistrationPolicy:
    def test_registration_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)
        assert registration_enabled() is False

    @pytest.mark.parametrize("value", ["true", "1", "YES", "on"])
    def test_registration_enabled_by_env(self, monkeypatch, value):
        monkeypatch.setenv("ALLOW_REGISTRATION", value)
        assert registration_enabled() is True

    def test_self_register_refused_when_disabled(self, auth):
        ok, message = auth.self_register("mallory", STRONG_PASSWORD)
        assert ok is False
        assert "disabled" in message
        assert not auth.user_exists("mallory")

    def test_self_register_creates_non_admin_when_enabled(self, auth, monkeypatch):
        monkeypatch.setenv("ALLOW_REGISTRATION", "true")
        ok, _ = auth.self_register("alice", STRONG_PASSWORD)
        assert ok is True
        assert auth.user_exists("alice")
        assert auth.is_admin("alice") is False

    @pytest.mark.parametrize("username", ["", "   ", " padded"])
    def test_self_register_rejects_bad_usernames(self, auth, monkeypatch, username):
        monkeypatch.setenv("ALLOW_REGISTRATION", "true")
        ok, _ = auth.self_register(username, STRONG_PASSWORD)
        assert ok is False
        assert [u["username"] for u in auth.list_users()] == ["admin"]

    @pytest.mark.parametrize("password", ["", "short", "x" * (MIN_PASSWORD_LENGTH - 1)])
    def test_self_register_rejects_short_passwords(self, auth, monkeypatch, password):
        monkeypatch.setenv("ALLOW_REGISTRATION", "true")
        ok, message = auth.self_register("bob", password)
        assert ok is False
        assert str(MIN_PASSWORD_LENGTH) in message
        assert not auth.user_exists("bob")

    def test_register_user_rejects_empty_credentials(self, auth):
        assert auth.register_user("", "") is False
        assert auth.register_user("carol", "") is False
        assert not auth.user_exists("")
        assert not auth.user_exists("carol")

    def test_validate_new_credentials_accepts_good_input(self):
        assert validate_new_credentials("dave", STRONG_PASSWORD) is None


class TestAdminAndPermissions:
    def test_default_admin_is_admin_and_uses_env_password(self, auth):
        assert auth.is_admin("admin") is True
        assert auth.authenticate("admin", "admin-initial-password-1") is True

    def test_admin_password_is_random_when_env_unset(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DASHBOARD_ADMIN_PASSWORD", raising=False)
        manager = AuthManager(db_path=tmp_path / "other.db")
        assert manager.user_exists("admin")
        for guess in ("admin123", "admin", "password", ""):
            assert manager.authenticate("admin", guess) is False

    def test_unknown_user_is_not_admin(self, auth):
        assert auth.is_admin("nobody") is False

    @pytest.mark.parametrize(
        "state,expected",
        [
            ({"authenticated": True, "is_admin": True}, True),
            ({"authenticated": True, "is_admin": False}, False),
            ({"authenticated": True}, False),
            ({"authenticated": False, "is_admin": True}, False),
            ({}, False),
        ],
    )
    def test_only_authenticated_admins_can_launch_jobs(self, state, expected):
        assert user_can_launch_jobs(state) is expected

    def test_change_password_enforces_minimum_length(self, auth):
        assert auth.change_password("admin", "admin-initial-password-1", "short") is False
        assert auth.authenticate("admin", "admin-initial-password-1") is True
        assert auth.change_password("admin", "admin-initial-password-1", STRONG_PASSWORD) is True
        assert auth.authenticate("admin", STRONG_PASSWORD) is True

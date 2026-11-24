import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_are_safe_for_local_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.postgres_password is None


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("POSTGRES_PASSWORD", "not-a-real-secret")
    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.log_level == "WARNING"
    assert settings.postgres_password is not None
    assert settings.postgres_password.get_secret_value() == "not-a-real-secret"
    assert "not-a-real-secret" not in repr(settings)


def test_unknown_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError, match="log_level"):
        Settings(_env_file=None)


def test_trusted_proxy_settings(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", '["172.30.50.2/32", "2001:db8::/64"]')
    settings = Settings(_env_file=None)
    assert [str(network) for network in settings.trusted_proxies] == [
        "172.30.50.2/32", "2001:db8::/64",
    ]


@pytest.mark.parametrize("cidr", ["0.0.0.0/0", "::/0", "invalid"])
def test_invalid_trusted_proxy(cidr):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, trusted_proxies=[cidr])


@pytest.mark.parametrize("setting", ["stale_queued_minutes", "recovery_interval_seconds"])
def test_invalid_recovery_setting(setting):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{setting: 0})

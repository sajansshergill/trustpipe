from __future__ import annotations

import pytest

from config.preflight import missing_or_placeholder_snowflake_env, require_snowflake_env


def test_missing_or_placeholder_snowflake_env_reports_template_values() -> None:
    invalid = missing_or_placeholder_snowflake_env(
        {
            "SNOWFLAKE_ACCOUNT": "xy12345.us-east-1",
            "SNOWFLAKE_USER": "trustpipe_svc",
            "SNOWFLAKE_PASSWORD": "changeme",
        }
    )

    assert invalid == ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"]


def test_missing_or_placeholder_snowflake_env_accepts_realistic_values() -> None:
    invalid = missing_or_placeholder_snowflake_env(
        {
            "SNOWFLAKE_ACCOUNT": "abc12345.us-east-1",
            "SNOWFLAKE_USER": "svc_trustpipe",
            "SNOWFLAKE_PASSWORD": "not-a-template-password",
        }
    )

    assert invalid == []


def test_require_snowflake_env_raises_for_missing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(EnvironmentError, match="Snowflake credentials are not configured"):
        require_snowflake_env()

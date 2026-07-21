"""Runtime preflight checks for external services."""
from __future__ import annotations

import argparse
import os
import sys


PLACEHOLDER_VALUES = {
    "SNOWFLAKE_ACCOUNT": {"", "xy12345.us-east-1", "changeme", "dummy"},
    "SNOWFLAKE_USER": {"", "trustpipe_svc", "changeme", "dummy"},
    "SNOWFLAKE_PASSWORD": {"", "changeme", "dummy"},
}


def missing_or_placeholder_snowflake_env(environ: dict[str, str] | None = None) -> list[str]:
    """Return Snowflake env vars that are missing or still set to template values."""
    environ = environ or os.environ
    invalid: list[str] = []
    for key, placeholders in PLACEHOLDER_VALUES.items():
        value = environ.get(key, "")
        if value in placeholders:
            invalid.append(key)
    return invalid


def require_snowflake_env() -> None:
    invalid = missing_or_placeholder_snowflake_env()
    if invalid:
        joined = ", ".join(invalid)
        raise EnvironmentError(
            "Snowflake credentials are not configured. Update .env with real values for: "
            f"{joined}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snowflake", action="store_true", help="validate Snowflake env vars")
    args = parser.parse_args()

    try:
        if args.snowflake:
            require_snowflake_env()
    except EnvironmentError as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

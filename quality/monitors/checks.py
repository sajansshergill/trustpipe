"""Operational monitors: freshness, volume, and schema drift.

These checks are designed to run on a schedule and return structured
MonitorResult records that can feed alerts or the reliability scorecard.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib import import_module
from typing import Any

from config.settings import SnowflakeConfig, load_contracts

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorResult:
    monitor: str
    target: str
    status: str
    detail: str


def _cursor() -> Any:
    cfg = SnowflakeConfig.from_env()
    snowflake_connector = import_module("snowflake.connector")
    return snowflake_connector.connect(
        account=cfg.account,
        user=cfg.user,
        password=cfg.password,
        role=cfg.role,
        warehouse=cfg.warehouse,
        database=cfg.database,
        schema="RAW",
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def check_freshness() -> list[MonitorResult]:
    """Compare the latest source timestamp against each source's freshness SLA."""
    contracts = load_contracts()
    timestamp_columns = {
        "yellow_trips": "TPEP_PICKUP_DATETIME",
        "weather": "OBSERVED_AT",
        "ride_stream": "PICKUP_TS",
    }
    results: list[MonitorResult] = []
    conn = _cursor()
    with conn, conn.cursor() as cur:
        for source, spec in contracts.items():
            sla_hours = spec.get("freshness_sla_hours")
            timestamp_column = timestamp_columns.get(source)
            if not sla_hours or not timestamp_column:
                continue

            cur.execute(f"select max({timestamp_column}) from raw.{source}")
            latest = cur.fetchone()[0]
            if latest is None:
                results.append(MonitorResult("freshness", source, "fail", "table empty"))
                continue

            age_hours = (datetime.now(timezone.utc) - _as_utc(latest)) / timedelta(hours=1)
            status = "ok" if age_hours <= sla_hours else "fail"
            results.append(
                MonitorResult(
                    "freshness",
                    source,
                    status,
                    f"{age_hours:.1f}h old (SLA {sla_hours}h)",
                )
            )
    return results


def check_volume() -> list[MonitorResult]:
    """Compare yesterday's yellow-trip row count against the expected band."""
    contracts = load_contracts()
    spec = contracts["yellow_trips"]
    results: list[MonitorResult] = []
    conn = _cursor()
    with conn, conn.cursor() as cur:
        cur.execute(
            "select count(*) from raw.yellow_trips "
            "where tpep_pickup_datetime >= dateadd('day', -1, current_timestamp())"
        )
        count = cur.fetchone()[0]

    low = spec["expected_daily_row_min"]
    high = spec["expected_daily_row_max"]
    status = "ok" if low <= count <= high else "warn"
    results.append(
        MonitorResult("volume", "yellow_trips", status, f"{count} rows (band {low}-{high})")
    )
    return results


def check_schema_drift(expected_columns: dict[str, set[str]]) -> list[MonitorResult]:
    """Detect added or removed RAW columns against a known-good schema snapshot."""
    results: list[MonitorResult] = []
    conn = _cursor()
    with conn, conn.cursor() as cur:
        for table, expected in expected_columns.items():
            cur.execute(
                "select column_name from information_schema.columns "
                "where table_schema = 'RAW' and table_name = %s",
                (table.upper(),),
            )
            actual = {row[0].lower() for row in cur.fetchall()}
            added = actual - expected
            removed = expected - actual
            if added or removed:
                results.append(
                    MonitorResult(
                        "schema_drift",
                        table,
                        "fail",
                        f"added={sorted(added)} removed={sorted(removed)}",
                    )
                )
            else:
                results.append(MonitorResult("schema_drift", table, "ok", "no drift"))
    return results
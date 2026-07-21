from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quality.monitors import checks


class FakeCursor:
    def __init__(self, fetchone_values: list[tuple], fetchall_values: list[list[tuple]] | None = None):
        self._fetchone_values = fetchone_values
        self._fetchall_values = fetchall_values or []
        self.statements: list[tuple[str, tuple | None]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, statement: str, params: tuple | None = None) -> None:
        self.statements.append((statement, params))

    def fetchone(self) -> tuple:
        return self._fetchone_values.pop(0)

    def fetchall(self) -> list[tuple]:
        return self._fetchall_values.pop(0)


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor


def test_check_freshness_marks_stale_source_failed(monkeypatch) -> None:
    contracts = {"yellow_trips": {"freshness_sla_hours": 1}}
    latest = datetime.now(timezone.utc) - timedelta(hours=2)
    cursor = FakeCursor(fetchone_values=[(latest,)])

    monkeypatch.setattr(checks, "load_contracts", lambda: contracts)
    monkeypatch.setattr(checks, "_cursor", lambda: FakeConnection(cursor))

    results = checks.check_freshness()

    assert len(results) == 1
    assert results[0].monitor == "freshness"
    assert results[0].target == "yellow_trips"
    assert results[0].status == "fail"


def test_check_volume_warns_outside_expected_band(monkeypatch) -> None:
    contracts = {
        "yellow_trips": {
            "expected_daily_row_min": 50,
            "expected_daily_row_max": 100,
        }
    }
    cursor = FakeCursor(fetchone_values=[(10,)])

    monkeypatch.setattr(checks, "load_contracts", lambda: contracts)
    monkeypatch.setattr(checks, "_cursor", lambda: FakeConnection(cursor))

    results = checks.check_volume()

    assert results == [
        checks.MonitorResult("volume", "yellow_trips", "warn", "10 rows (band 50-100)")
    ]


def test_check_schema_drift_reports_added_and_removed_columns(monkeypatch) -> None:
    cursor = FakeCursor(
        fetchone_values=[],
        fetchall_values=[[("ID",), ("EXTRA",)]],
    )

    monkeypatch.setattr(checks, "_cursor", lambda: FakeConnection(cursor))

    results = checks.check_schema_drift({"rides": {"id", "amount"}})

    assert len(results) == 1
    assert results[0].monitor == "schema_drift"
    assert results[0].target == "rides"
    assert results[0].status == "fail"
    assert "added=['extra']" in results[0].detail
    assert "removed=['amount']" in results[0].detail

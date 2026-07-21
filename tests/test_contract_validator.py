from __future__ import annotations

import pandas as pd
import pytest

from ingest.contracts import validator


def _contract() -> dict:
    return {
        "primary_keys": ["id"],
        "columns": {
            "id": {"dtype": "int", "nullable": False},
            "amount": {"dtype": "float", "nullable": False, "min": 0, "max": 100},
            "status": {"dtype": "str", "nullable": False, "allowed": ["ok", "warn"]},
            "created_at": {"dtype": "datetime", "nullable": False},
        },
    }


@pytest.fixture(autouse=True)
def stub_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "get_contract", lambda source: _contract())


def test_validate_passes_contract_shaped_dataframe() -> None:
    df = pd.DataFrame(
        {
            "id": pd.Series([1, 2], dtype="Int64"),
            "amount": pd.Series([10.5, 99.9], dtype="float64"),
            "status": ["ok", "warn"],
            "created_at": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        }
    )

    report = validator.validate(df, "example")

    assert report.passed
    assert report.row_count == 2
    assert report.raise_if_failed() is report


def test_validate_reports_contract_violations() -> None:
    df = pd.DataFrame(
        {
            "id": pd.Series([1, 1], dtype="Int64"),
            "amount": pd.Series([-1.0, 150.0], dtype="float64"),
            "status": ["ok", "bad"],
            "created_at": pd.to_datetime(["2024-01-01", None]),
        }
    )

    report = validator.validate(df, "example")

    assert not report.passed
    assert any("amount: 1 value(s) below min 0" in v for v in report.violations)
    assert any("amount: 1 value(s) above max 100" in v for v in report.violations)
    assert any("status: unexpected value(s) ['bad']" in v for v in report.violations)
    assert any("created_at: 1 null(s)" in v for v in report.violations)
    assert any("primary key ['id']: 1 duplicate row(s)" in v for v in report.violations)

    with pytest.raises(validator.ContractViolation):
        report.raise_if_failed()

"""Contract enforcement.

Every ingest source is validated against its declared contract BEFORE it is
allowed to land in RAW. A violation raises ContractViolation and aborts the load,
so bad data never reaches downstream models.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config.settings import get_contract


class ContractViolation(Exception):
    """Raised when a batch fails its data contract."""


@dataclass
class ValidationReport:
    source: str
    row_count: int
    violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations

    def raise_if_failed(self) -> "ValidationReport":
        if not self.passed:
            joined = "\n  - ".join(self.violations)
            raise ContractViolation(
                f"Contract '{self.source}' failed with "
                f"{len(self.violations)} violation(s):\n  - {joined}"
            )
        return self


_DTYPE_CHECKS = {
    "int": pd.api.types.is_integer_dtype,
    "float": pd.api.types.is_float_dtype,
    "str": pd.api.types.is_object_dtype,
    "datetime": pd.api.types.is_datetime64_any_dtype,
}


def validate(df: pd.DataFrame, source: str) -> ValidationReport:
    """Validate a dataframe against the named contract."""
    contract = get_contract(source)
    report = ValidationReport(source=source, row_count=len(df))
    cols = contract.get("columns", {})

    # 1. Required columns present
    missing = [c for c in cols if c not in df.columns]
    for c in missing:
        report.violations.append(f"missing required column: {c}")

    # 2. Per-column checks
    for col, rules in cols.items():
        if col not in df.columns:
            continue
        series = df[col]

        # dtype
        expected = rules.get("dtype")
        check = _DTYPE_CHECKS.get(expected)
        if check and not check(series):
            report.violations.append(
                f"{col}: expected dtype {expected}, got {series.dtype}"
            )

        # nullability
        if not rules.get("nullable", True):
            n_null = int(series.isna().sum())
            if n_null:
                report.violations.append(f"{col}: {n_null} null(s) in non-nullable column")

        non_null = series.dropna()

        # range
        if "min" in rules and pd.api.types.is_numeric_dtype(non_null):
            below = int((non_null < rules["min"]).sum())
            if below:
                report.violations.append(f"{col}: {below} value(s) below min {rules['min']}")
        if "max" in rules and pd.api.types.is_numeric_dtype(non_null):
            above = int((non_null > rules["max"]).sum())
            if above:
                report.violations.append(f"{col}: {above} value(s) above max {rules['max']}")

        # allowed set
        if "allowed" in rules:
            bad = set(non_null.unique()) - set(rules["allowed"])
            if bad:
                report.violations.append(f"{col}: unexpected value(s) {sorted(bad)[:5]}")

    # 3. Primary-key uniqueness
    pk = contract.get("primary_keys", [])
    if pk and all(k in df.columns for k in pk):
        dupes = int(df.duplicated(subset=pk).sum())
        if dupes:
            report.violations.append(f"primary key {pk}: {dupes} duplicate row(s)")

    return report
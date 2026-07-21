"""Great Expectations suite for the marts layer.

Runs a validation suite against fact_trips after dbt builds it. Complements dbt
tests: dbt guards schema/referential rules, GE captures distributional and
statistical expectations that are awkward to express in SQL.

Usage:
    python -m quality.expectations.run_suite
"""
from __future__ import annotations

import logging
import sys

import great_expectations as gx
import pandas as pd
import snowflake.connector

from config.settings import SnowflakeConfig

log = logging.getLogger(__name__)


def _read_fact() -> pd.DataFrame:
    cfg = SnowflakeConfig.from_env()
    conn = snowflake.connector.connect(
        account=cfg.account, user=cfg.user, password=cfg.password,
        role=cfg.role, warehouse=cfg.warehouse, database=cfg.database,
        schema="ANALYTICS_MARTS",
    )
    with conn:
        return pd.read_sql("select * from fact_trips sample (5)", conn)


def build_suite(df: pd.DataFrame):
    ctx = gx.get_context()
    validator = ctx.sources.pandas_default.read_dataframe(df)

    validator.expect_column_values_to_not_be_null("TRIP_KEY")
    validator.expect_column_values_to_be_unique("TRIP_KEY")
    validator.expect_column_values_to_be_between("FARE_AMOUNT", -100, 5000)
    validator.expect_column_values_to_be_between(
        "TRIP_DISTANCE", 0, 1000, mostly=0.999
    )
    validator.expect_column_values_to_be_in_set("INGEST_SOURCE", ["batch", "stream"])
    # distributional: median fare should sit in a sane band
    validator.expect_column_median_to_be_between("FARE_AMOUNT", 5, 40)
    return validator.validate()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    df = _read_fact()
    result = build_suite(df)
    log.info("GE suite success=%s", result.success)
    if not result.success:
        log.error("Great Expectations suite failed — see results above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
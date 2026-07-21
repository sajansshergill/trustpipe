"""Thin Snowflake write helper shared by all ingest paths.

Uses write_pandas for efficient bulk loads. Keeps connection handling in one
place so loaders stay focused on source-specific logic.
"""
from __future__ import annotations

import logging

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from config.settings import SnowflakeConfig

log = logging.getLogger(__name__)


def _connect(cfg: SnowflakeConfig):
    return snowflake.connector.connect(
        account=cfg.account,
        user=cfg.user,
        password=cfg.password,
        role=cfg.role,
        warehouse=cfg.warehouse,
        database=cfg.database,
        schema=cfg.schema,
    )


def load_dataframe(df: pd.DataFrame, table: str, cfg: SnowflakeConfig | None = None) -> int:
    """Bulk-load a validated dataframe into RAW.<table>. Returns rows written."""
    cfg = cfg or SnowflakeConfig.from_env()
    df.columns = [c.upper() for c in df.columns]  # Snowflake defaults to upper-case
    with _connect(cfg) as conn:
        success, _, nrows, _ = write_pandas(
            conn, df, table.upper(), auto_create_table=True, overwrite=False
        )
    if not success:
        raise RuntimeError(f"write_pandas reported failure loading {table}")
    log.info("Loaded %s rows into RAW.%s", nrows, table)
    return nrows
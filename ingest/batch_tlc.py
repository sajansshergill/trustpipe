"""Batch ingest: NYC TLC yellow taxi parquet -> RAW.YELLOW_TRIPS.

TLC publishes monthly parquet files. This loader downloads one month, normalizes
column names, validates against the `yellow_trips` contract, and bulk-loads.

Usage:
    python -m ingest.batch_tlc --year 2024 --month 1
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd

from ingest.contracts.validator import validate
from ingest.warehouse import load_dataframe

log = logging.getLogger(__name__)

TLC_URL = (
    "https://d37ci6vzurychx.cloudfront.net/trip-data/"
    "yellow_tripdata_{year}-{month:02d}.parquet"
)

# TLC column names -> our contract's canonical names
COLUMN_MAP = {
    "VendorID": "vendor_id",
    "tpep_pickup_datetime": "tpep_pickup_datetime",
    "tpep_dropoff_datetime": "tpep_dropoff_datetime",
    "passenger_count": "passenger_count",
    "trip_distance": "trip_distance",
    "PULocationID": "pu_location_id",
    "DOLocationID": "do_location_id",
    "fare_amount": "fare_amount",
    "tip_amount": "tip_amount",
    "total_amount": "total_amount",
    "payment_type": "payment_type",
}


def extract(year: int, month: int) -> pd.DataFrame:
    url = TLC_URL.format(year=year, month=month)
    log.info("Downloading %s", url)
    df = pd.read_parquet(url)
    return df


def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP)
    keep = [c for c in COLUMN_MAP.values() if c in df.columns]
    df = df[keep].copy()

    # Coerce integer-ish columns; contract validation catches anything unfixable.
    for col in ("vendor_id", "pu_location_id", "do_location_id", "payment_type"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in ("tpep_pickup_datetime", "tpep_dropoff_datetime"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def run(year: int, month: int) -> int:
    df = transform(extract(year, month))
    validate(df, "yellow_trips").raise_if_failed()  # gate: aborts on violation
    return load_dataframe(df, "YELLOW_TRIPS")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    args = ap.parse_args()
    n = run(args.year, args.month)
    log.info("Batch load complete: %s rows", n)


if __name__ == "__main__":
    main()
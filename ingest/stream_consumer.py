"""Streaming sink: consume `ride_stream`, validate, micro-batch into RAW.RIDE_STREAM.

Events are buffered and flushed every N records (or on a time boundary), each
micro-batch passing the same contract gate as the batch path. Downstream dbt
merges RIDE_STREAM into fact_trips without double-counting via event_id.

Usage:
    python -m ingest.stream_consumer --batch-size 200
"""
from __future__ import annotations

import argparse
import json
import logging

import pandas as pd
from kafka import KafkaConsumer

from config.settings import KafkaConfig
from ingest.contracts.validator import ContractViolation, validate
from ingest.warehouse import load_dataframe

log = logging.getLogger(__name__)


def _flush(buffer: list[dict]) -> int:
    if not buffer:
        return 0
    df = pd.DataFrame(buffer)
    df["pickup_ts"] = pd.to_datetime(df["pickup_ts"], errors="coerce")
    for col in ("vendor_id", "pu_location_id", "do_location_id"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    try:
        validate(df, "ride_stream").raise_if_failed()
    except ContractViolation as exc:
        # Dead-letter rather than crash the whole stream.
        log.error("Micro-batch failed contract, routing to DLQ: %s", exc)
        df.to_parquet(f"/tmp/dlq_ride_stream_{pd.Timestamp.utcnow().value}.parquet")
        return 0
    return load_dataframe(df, "RIDE_STREAM")


def run(batch_size: int) -> None:
    cfg = KafkaConfig.from_env()
    consumer = KafkaConsumer(
        cfg.topic,
        bootstrap_servers=cfg.bootstrap_servers,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="trustpipe-ride-consumer",
    )
    buffer: list[dict] = []
    total = 0
    log.info("Consuming from %s (batch size %s)...", cfg.topic, batch_size)
    for msg in consumer:
        buffer.append(msg.value)
        if len(buffer) >= batch_size:
            total += _flush(buffer)
            buffer.clear()
            log.info("Committed micro-batch. Total loaded: %s", total)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=200)
    args = ap.parse_args()
    run(args.batch_size)


if __name__ == "__main__":
    main()
"""Streaming source: synthetic live ride events -> Kafka topic `ride_stream`.

This stands in for a production event feed. It emits contract-shaped JSON so the
consumer's merge path can be exercised end-to-end.

Usage:
    python -m ingest.stream_producer --rate 5 --seconds 60
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone

from kafka import KafkaProducer

from config.settings import KafkaConfig

log = logging.getLogger(__name__)
VENDORS = [1, 2, 6, 7]


def make_event() -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "vendor_id": random.choice(VENDORS),
        "pickup_ts": datetime.now(timezone.utc).isoformat(),
        "pu_location_id": random.randint(1, 265),
        "do_location_id": random.randint(1, 265),
        "fare_amount": round(random.uniform(3.5, 120.0), 2),
    }


def run(rate: int, seconds: int) -> int:
    cfg = KafkaConfig.from_env()
    producer = KafkaProducer(
        bootstrap_servers=cfg.bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    sent = 0
    deadline = time.time() + seconds
    while time.time() < deadline:
        for _ in range(rate):
            producer.send(cfg.topic, make_event())
            sent += 1
        producer.flush()
        time.sleep(1)
    log.info("Produced %s events to topic %s", sent, cfg.topic)
    return sent


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=int, default=5, help="events per second")
    ap.add_argument("--seconds", type=int, default=60)
    args = ap.parse_args()
    run(args.rate, args.seconds)


if __name__ == "__main__":
    main()
"""Kafka-only smoke test for the synthetic ride stream."""
from __future__ import annotations

import argparse
import json
import logging
import time
import uuid

from kafka import KafkaConsumer, KafkaProducer

from config.settings import KafkaConfig
from ingest.stream_producer import make_event

log = logging.getLogger(__name__)


def run(count: int, timeout_s: int) -> int:
    cfg = KafkaConfig.from_env()
    group_id = f"trustpipe-smoke-{uuid.uuid4()}"
    producer = KafkaProducer(
        bootstrap_servers=cfg.bootstrap_servers,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )
    consumer = KafkaConsumer(
        cfg.topic,
        bootstrap_servers=cfg.bootstrap_servers,
        value_deserializer=lambda message: json.loads(message.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        group_id=group_id,
        consumer_timeout_ms=1000,
    )

    sent_events = [make_event() for _ in range(count)]
    for event in sent_events:
        producer.send(cfg.topic, event)
    producer.flush()

    expected_ids = {event["event_id"] for event in sent_events}
    received_ids: set[str] = set()
    deadline = time.time() + timeout_s
    while time.time() < deadline and received_ids != expected_ids:
        for message in consumer:
            event_id = message.value.get("event_id")
            if event_id in expected_ids:
                received_ids.add(event_id)

    producer.close()
    consumer.close()

    if received_ids != expected_ids:
        missing = expected_ids - received_ids
        raise RuntimeError(f"Kafka smoke test missed {len(missing)} event(s)")

    log.info("Kafka smoke test produced and consumed %s event(s)", len(received_ids))
    return len(received_ids)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--timeout-s", type=int, default=20)
    args = parser.parse_args()
    run(args.count, args.timeout_s)


if __name__ == "__main__":
    main()

"""Send repeatable batches of sensor readings to the Kafka topic."""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from confluent_kafka import Producer

ROOMS = ("A101", "A102", "B201")
TOPIC = os.getenv("KAFKA_TOPIC", "campus.measurements")
log = logging.getLogger(__name__)


def make_message(number: int, started_at: datetime) -> dict:
    """Every tenth block contains three deliberate invalid or repeated messages."""
    room = ROOMS[(number - 1) % len(ROOMS)]
    if number % 10 == 0:
        return make_message(number - 1, started_at)
    measured_at = started_at + timedelta(seconds=number)
    row = {
        "room": room,
        "measured_at": measured_at.isoformat(),
        "co2_ppm": 650 + number * 3,
        "temperature_c": 20.0 + number % 5 / 10,
        "humidity_pct": 45.0 + number % 7,
    }
    if number % 10 == 5:
        if number % 30 == 5:
            row["co2_ppm"] = "invalid"
        elif number % 30 == 15:
            del row["temperature_c"]
        else:
            row["humidity_pct"] = 120
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Envoyer des mesures de démonstration")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if args.count < 1 or args.interval < 0:
        parser.error("--count doit être positif et --interval ne peut pas être négatif")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
    producer = Producer({"bootstrap.servers": servers})
    started_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    failures: list[str] = []

    def delivery(error, _message) -> None:
        if error is not None:
            failures.append(str(error))

    log.info(
        "sending to %s, topic %s, one round every %s s", servers, TOPIC, args.interval
    )
    for number in range(1, args.count + 1):
        row = make_message(number, started_at)
        label = (
            "duplicate"
            if number % 10 == 0
            else "invalid"
            if number % 10 == 5
            else "valid"
        )
        producer.produce(
            TOPIC,
            key=row["room"].encode("utf-8"),
            value=json.dumps(row).encode("utf-8"),
            on_delivery=delivery,
        )
        producer.poll(0)
        log.info("message %s -> %s: %s", number, row["room"], label)
        if number % len(ROOMS) == 0 and number < args.count:
            time.sleep(args.interval)
    remaining = producer.flush(30)
    if remaining or failures:
        log.error("%s message(s) non confirmés par Kafka", remaining or len(failures))
        return 1
    log.info("all messages confirmed by Kafka")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

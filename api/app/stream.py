"""Consume sensor measurements from Kafka and store them in the existing dataset API."""

import json
import logging
import os
import signal
import time
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaException, TopicPartition
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import SessionLocal
from .ingestion import EXPECTED_HEADER, ParsedMeasurement, check_line
from .models import Dataset, Ingestion, Measurement

TOPIC = os.getenv("KAFKA_TOPIC", "campus.measurements")
DATASET_NAME = os.getenv("STREAM_DATASET_NAME", "Flux capteurs (Kafka)")
STREAM_FILENAME = f"kafka:{TOPIC}"
MAX_DETAILED_ERRORS = 100
RETRY_SECONDS = 5

log = logging.getLogger(__name__)


def parse_message(raw: bytes | None, now: datetime) -> ParsedMeasurement:
    """Return a validated measurement, or a readable rejection reason."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("Invalid message") from None
    if not isinstance(data, dict) or set(data) != set(EXPECTED_HEADER):
        raise ValueError("Invalid message")
    return check_line([str(data[key]) for key in EXPECTED_HEADER], now)


def stream_ingestion(session: Session) -> Ingestion:
    """Lock the shared stream dataset so counters stay correct across consumers."""
    session.execute(
        insert(Dataset)
        .values(
            name=DATASET_NAME,
            owner="Capteurs",
            description=f"Mesures reçues du topic {TOPIC}",
        )
        .on_conflict_do_nothing(index_elements=["name"])
    )
    dataset = session.scalars(
        select(Dataset).where(Dataset.name == DATASET_NAME).with_for_update()
    ).one()
    ingestion = session.scalars(
        select(Ingestion).where(
            Ingestion.dataset_id == dataset.id,
            Ingestion.filename == STREAM_FILENAME,
        )
    ).first()
    if ingestion is None:c
        ingestion = Ingestion(
            dataset_id=dataset.id,
            filename=STREAM_FILENAME,
            content=b"",
            status="succeeded",
            rows_accepted=0,
            rows_rejected=0,
            rows_duplicate=0,
            errors=[],
            started_at=datetime.now(timezone.utc),
        )
        session.add(ingestion)
        session.flush()
    return ingestion


def handle(raw: bytes | None, now: datetime | None = None) -> str:
    """Commit the measurement and the permanent report in one SQL transaction."""
    now = now or datetime.now(timezone.utc)
    with SessionLocal() as session:
        ingestion = stream_ingestion(session)
        line = (
            ingestion.rows_accepted
            + ingestion.rows_rejected
            + ingestion.rows_duplicate
            + 1
        )
        try:
            row = parse_message(raw, now)
        except ValueError as exc:
            outcome = str(exc)
            ingestion.rows_rejected += 1
            if len(ingestion.errors) < MAX_DETAILED_ERRORS:
                ingestion.errors = [
                    *ingestion.errors,
                    {"line": line, "reason": outcome},
                ]
        else:
            inserted = session.execute(
                insert(Measurement)
                .values(
                    dataset_id=ingestion.dataset_id,
                    ingestion_id=ingestion.id,
                    room=row.room,
                    measured_at=row.measured_at,
                    co2_ppm=row.co2_ppm,
                    temperature_c=row.temperature_c,
                    humidity_pct=row.humidity_pct,
                )
                .on_conflict_do_nothing(constraint="uq_measurement_dataset_room_time")
                .returning(Measurement.id)
            ).first()
            if inserted is None:
                outcome = "duplicate"
                ingestion.rows_duplicate += 1
            else:
                outcome = "accepted"
                ingestion.rows_accepted += 1
        ingestion.finished_at = datetime.now(timezone.utc)
        session.commit()
    return outcome


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
    consumer = Consumer(
        {
            "bootstrap.servers": servers,
            "group.id": os.getenv("KAFKA_GROUP_ID", "campus-stream"),
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "allow.auto.create.topics": True,
        }
    )
    consumer.subscribe([TOPIC])
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("lecture du topic %s sur %s", TOPIC, servers)
    try:
        while not stopping:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                log.warning("kafka : %s", message.error())
                continue
            try:
                outcome = handle(message.value())
            except SQLAlchemyError:
                log.exception(
                    "base indisponible, message relu dans %s s", RETRY_SECONDS
                )
                consumer.seek(
                    TopicPartition(
                        message.topic(), message.partition(), message.offset()
                    )
                )
                time.sleep(RETRY_SECONDS)
                continue
            try:
                consumer.commit(message=message, asynchronous=False)
            except KafkaException as exc:
                log.warning("offset non validé : %s", exc)
            log.info(
                "message partition %s offset %s : %s",
                message.partition(),
                message.offset(),
                outcome,
            )
    finally:
        consumer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

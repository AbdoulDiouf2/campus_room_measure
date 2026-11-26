"""Kafka message validation and persistence through the shared SQL models."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app import stream
from app.database import SessionLocal, engine
from app.main import app
from app.models import Dataset, Ingestion, Measurement
from app.simulator import make_message

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("raw", [None, b"not json", b"[]", b"{}", b"\xff"])
def test_invalid_message_shape(raw):
    with pytest.raises(ValueError, match="^Invalid message$"):
        stream.parse_message(raw, NOW)


def test_simulator_batch_and_sql_report(monkeypatch):
    if not engine.url.database.endswith("_test"):
        pytest.fail("Ce test doit utiliser une base *_test")
    name = f"Flux test {uuid4().hex}"
    monkeypatch.setattr(stream, "DATASET_NAME", name)
    started = NOW - timedelta(minutes=1)
    messages = [
        json.dumps(make_message(number, started)).encode() for number in range(1, 31)
    ]
    try:
        outcomes = [stream.handle(raw, NOW) for raw in messages]
        assert outcomes.count("accepted") == 24
        assert outcomes.count("duplicate") == 3
        assert [outcome for outcome in outcomes if outcome.startswith("Invalid")] == [
            "Invalid co2_ppm",
            "Invalid message",
            "Invalid humidity_pct",
        ]
        with SessionLocal() as session:
            dataset = session.scalar(select(Dataset).where(Dataset.name == name))
            report = session.scalar(
                select(Ingestion).where(Ingestion.dataset_id == dataset.id)
            )
            assert (
                report.rows_accepted,
                report.rows_rejected,
                report.rows_duplicate,
            ) == (24, 3, 3)
            assert [item["reason"] for item in report.errors] == [
                "Invalid co2_ppm",
                "Invalid message",
                "Invalid humidity_pct",
            ]
            assert (
                len(
                    session.scalars(
                        select(Measurement).where(Measurement.dataset_id == dataset.id)
                    ).all()
                )
                == 24
            )
            dataset_id = dataset.id
        response = TestClient(app).get(f"/api/datasets/{dataset_id}/stats")
        assert response.status_code == 200
        assert {row["room"] for row in response.json()} == {"A101", "A102", "B201"}
        assert sum(row["measurement_count"] for row in response.json()) == 24
        assert TestClient(app).delete(f"/api/ingestions/{report.id}").status_code == 409
    finally:
        with SessionLocal() as session:
            session.execute(delete(Dataset).where(Dataset.name == name))
            session.commit()

"""End-to-end HTTP and worker checks against the dedicated PostgreSQL database."""

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.database import SessionLocal, engine
from app.main import app
from app.models import Dataset, Ingestion, Measurement
from app.services import process_next_ingestion

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
client = TestClient(app)


@pytest.fixture
def dataset():
    if engine.url.database != "campus_test":
        pytest.fail("Ce test doit utiliser campus_test")
    response = client.post("/api/datasets", json={"name": f"Test API {uuid4().hex}"})
    assert response.status_code == 201, response.text
    dataset_id = response.json()["id"]
    try:
        yield dataset_id
    finally:
        with SessionLocal() as session:
            session.execute(delete(Dataset).where(Dataset.id == dataset_id))
            session.commit()


def upload(dataset_id: str, filename: str):
    return client.post(
        f"/api/datasets/{dataset_id}/ingestions",
        params={"filename": filename},
        content=(DATA_DIR / filename).read_bytes(),
        headers={"Content-Type": "text/csv"},
    )


def process_one():
    with SessionLocal() as session:
        assert process_next_ingestion(session)


def test_dataset_routes_and_refusals(dataset):
    detail = client.get(f"/api/datasets/{dataset}")
    assert detail.status_code == 200
    assert detail.json()["measurement_count"] == 0
    assert dataset in [item["id"] for item in client.get("/api/datasets").json()]
    duplicate = client.post("/api/datasets", json={"name": detail.json()["name"]})
    assert duplicate.status_code == 409
    assert client.get(f"/api/datasets/{uuid4()}").status_code == 404
    assert client.post("/api/datasets", json={"name": "   "}).status_code == 422


def test_valid_upload_twice_and_stats(dataset):
    filename = "mesures-salles-2026-10-05.csv"
    first = upload(dataset, filename)
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "pending"
    process_one()
    first_report = client.get(f"/api/ingestions/{first.json()['id']}").json()
    assert (first_report["status"], first_report["rows_accepted"]) == ("succeeded", 63)
    assert first_report["rows_rejected"] == first_report["rows_duplicate"] == 0
    assert client.post(f"/api/ingestions/{first.json()['id']}/retry").status_code == 409

    second = upload(dataset, filename)
    assert second.status_code == 202
    process_one()
    second_report = client.get(f"/api/ingestions/{second.json()['id']}").json()
    assert (second_report["status"], second_report["rows_accepted"]) == ("succeeded", 0)
    assert second_report["rows_duplicate"] == 63
    assert client.get(f"/api/datasets/{dataset}").json()["measurement_count"] == 63

    stats = client.get(f"/api/datasets/{dataset}/stats")
    assert stats.status_code == 200, stats.text
    assert sum(item["measurement_count"] for item in stats.json()) == 63
    filtered = client.get(
        f"/api/datasets/{dataset}/stats",
        params={
            "room": "A101",
            "from": "2026-10-05T08:00:00+02:00",
            "to": "2026-10-05T08:30:00+02:00",
        },
    )
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["measurement_count"] == 2
    assert filtered.json()[0]["co2_min"] == 430
    assert filtered.json()[0]["co2_max"] == 637
    assert (
        client.get(f"/api/datasets/{dataset}/stats", params={"room": "unknown"}).json()
        == []
    )
    assert (
        client.get(
            f"/api/datasets/{dataset}/stats",
            params={
                "from": "2026-10-06T00:00:00+00:00",
                "to": "2026-10-05T00:00:00+00:00",
            },
        ).status_code
        == 422
    )


def test_mixed_and_invalid_header(dataset):
    mixed = upload(dataset, "mesures-avec-erreurs.csv")
    assert mixed.status_code == 202
    process_one()
    report = client.get(f"/api/ingestions/{mixed.json()['id']}").json()
    assert (
        report["status"],
        report["rows_accepted"],
        report["rows_rejected"],
        report["rows_duplicate"],
    ) == ("succeeded", 4, 7, 1)
    assert [item["line"] for item in report["errors"]] == [5, 6, 7, 8, 9, 10, 12]

    invalid = upload(dataset, "en-tete-invalide.csv")
    assert invalid.status_code == 202
    process_one()
    failed = client.get(f"/api/ingestions/{invalid.json()['id']}").json()
    assert failed["status"] == "failed"
    assert failed["rows_accepted"] == 0
    assert "Invalid header" in failed["errors"][0]["reason"]
    retry = client.post(f"/api/ingestions/{invalid.json()['id']}/retry")
    assert retry.status_code == 202
    assert retry.json()["status"] == "pending"
    assert retry.json()["errors"] == []
    process_one()
    assert (
        client.get(f"/api/ingestions/{invalid.json()['id']}").json()["status"]
        == "failed"
    )
    assert client.get(f"/api/datasets/{dataset}").json()["measurement_count"] == 4


def test_upload_refusals_and_delete(dataset):
    path = f"/api/datasets/{dataset}/ingestions?filename=test.csv"
    assert (
        client.post(
            path, content=b"x", headers={"Content-Type": "application/json"}
        ).status_code
        == 415
    )
    assert (
        client.post(
            path, content=b"x" * (1024 * 1024 + 1), headers={"Content-Type": "text/csv"}
        ).status_code
        == 413
    )
    assert (
        client.post(
            f"/api/datasets/{uuid4()}/ingestions?filename=x.csv",
            content=b"x",
            headers={"Content-Type": "text/csv"},
        ).status_code
        == 404
    )
    assert client.get(f"/api/datasets/{dataset}/ingestions").json() == []
    result = client.delete(f"/api/datasets/{dataset}")
    assert result.status_code == 204
    assert result.content == b""
    assert client.get(f"/api/datasets/{dataset}").status_code == 404


def test_worker_once_drains_queue_and_delete_cascades(dataset):
    first = upload(dataset, "mesures-salles-2026-10-05.csv")
    second = upload(dataset, "mesures-avec-erreurs.csv")
    assert first.status_code == second.status_code == 202

    completed = subprocess.run(
        [sys.executable, "-m", "app.worker", "--once"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (
        client.get(f"/api/ingestions/{first.json()['id']}").json()["status"]
        == "succeeded"
    )
    assert (
        client.get(f"/api/ingestions/{second.json()['id']}").json()["status"]
        == "succeeded"
    )
    assert client.get(f"/api/datasets/{dataset}").json()["measurement_count"] == 67

    response = client.delete(f"/api/datasets/{dataset}")
    assert response.status_code == 204
    with SessionLocal() as session:
        assert (
            session.scalar(
                select(func.count(Ingestion.id)).where(Ingestion.dataset_id == dataset)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count(Measurement.id)).where(
                    Measurement.dataset_id == dataset
                )
            )
            == 0
        )

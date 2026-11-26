"""Business operations shared by HTTP routes and the ingestion worker."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .ingestion import CsvFormatError, parse_csv
from .models import Dataset, Ingestion, Measurement
from .schemas import DatasetCreate, StatsRow


class DatasetNameConflict(Exception):
    """A dataset already uses this name."""


class DatasetNotFound(Exception):
    """The requested dataset does not exist."""


class IngestionNotFound(Exception):
    """The requested ingestion does not exist."""


class IngestionConflict(Exception):
    """The requested ingestion transition is not allowed."""


def create_dataset(session: Session, data: DatasetCreate) -> Dataset:
    dataset = Dataset(name=data.name, description=data.description, owner=data.owner)
    session.add(dataset)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DatasetNameConflict(data.name) from exc
    session.refresh(dataset)
    return dataset


def list_datasets(session: Session) -> list[tuple[Dataset, int]]:
    statement = (
        select(Dataset, func.count(Measurement.id))
        .outerjoin(Measurement, Measurement.dataset_id == Dataset.id)
        .group_by(Dataset.id)
        .order_by(Dataset.created_at.desc(), Dataset.id)
    )
    return [(dataset, count) for dataset, count in session.execute(statement)]


def get_dataset(session: Session, dataset_id: UUID) -> tuple[Dataset, int]:
    statement = (
        select(Dataset, func.count(Measurement.id))
        .outerjoin(Measurement, Measurement.dataset_id == Dataset.id)
        .where(Dataset.id == dataset_id)
        .group_by(Dataset.id)
    )
    result = session.execute(statement).one_or_none()
    if result is None:
        raise DatasetNotFound()
    dataset, count = result
    return dataset, count


def delete_dataset(session: Session, dataset_id: UUID) -> None:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise DatasetNotFound()
    session.delete(dataset)
    session.commit()


def create_ingestion(
    session: Session, dataset_id: UUID, filename: str, content: bytes
) -> Ingestion:
    if session.get(Dataset, dataset_id) is None:
        raise DatasetNotFound()
    ingestion = Ingestion(dataset_id=dataset_id, filename=filename, content=content)
    session.add(ingestion)
    session.commit()
    session.refresh(ingestion)
    return ingestion


def get_ingestion(session: Session, ingestion_id: UUID) -> Ingestion:
    ingestion = session.get(Ingestion, ingestion_id)
    if ingestion is None:
        raise IngestionNotFound()
    return ingestion


def list_ingestions(session: Session, dataset_id: UUID) -> list[Ingestion]:
    if session.get(Dataset, dataset_id) is None:
        raise DatasetNotFound()
    return list(
        session.scalars(
            select(Ingestion)
            .where(Ingestion.dataset_id == dataset_id)
            .order_by(Ingestion.created_at.desc(), Ingestion.id)
        )
    )


def delete_ingestion(session: Session, ingestion_id: UUID) -> None:
    """Delete a finished upload and its measurements, retaining the dataset."""
    ingestion = session.scalar(
        select(Ingestion).where(Ingestion.id == ingestion_id).with_for_update()
    )
    if ingestion is None:
        raise IngestionNotFound()
    if ingestion.filename.startswith("kafka:"):
        raise IngestionConflict()
    if ingestion.status not in {"succeeded", "failed"}:
        raise IngestionConflict()
    session.delete(ingestion)
    session.commit()


def retry_ingestion(session: Session, ingestion_id: UUID) -> Ingestion:
    ingestion = session.scalar(
        select(Ingestion).where(Ingestion.id == ingestion_id).with_for_update()
    )
    if ingestion is None:
        raise IngestionNotFound()
    if ingestion.status != "failed":
        raise IngestionConflict()
    ingestion.status = "pending"
    ingestion.rows_accepted = 0
    ingestion.rows_rejected = 0
    ingestion.rows_duplicate = 0
    ingestion.errors = []
    ingestion.started_at = None
    ingestion.finished_at = None
    session.commit()
    session.refresh(ingestion)
    return ingestion


def process_next_ingestion(session: Session) -> bool:
    """Claim and process one pending upload; return False if the queue is empty."""
    ingestion = session.scalar(
        select(Ingestion)
        .where(Ingestion.status == "pending")
        .order_by(Ingestion.created_at, Ingestion.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if ingestion is None:
        session.rollback()
        return False
    ingestion.status = "running"
    ingestion.started_at = datetime.now(timezone.utc)
    session.commit()

    try:
        parsed = parse_csv(ingestion.content)
    except CsvFormatError as exc:
        ingestion.status = "failed"
        ingestion.errors = [{"line": 1, "reason": str(exc)}]
        ingestion.finished_at = datetime.now(timezone.utc)
        session.commit()
        return True

    rows = [
        {
            "dataset_id": ingestion.dataset_id,
            "ingestion_id": ingestion.id,
            "room": item.room,
            "measured_at": item.measured_at,
            "co2_ppm": item.co2_ppm,
            "temperature_c": item.temperature_c,
            "humidity_pct": item.humidity_pct,
        }
        for item in parsed.measurements
    ]
    accepted = 0
    if rows:
        statement = (
            insert(Measurement)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_measurement_dataset_room_time")
            .returning(Measurement.id)
        )
        accepted = len(session.scalars(statement).all())
    ingestion.rows_accepted = accepted
    ingestion.rows_rejected = len(parsed.rejected)
    ingestion.rows_duplicate = parsed.duplicates + len(rows) - accepted
    ingestion.errors = [
        {"line": item.line, "reason": item.reason} for item in parsed.rejected
    ]
    ingestion.status = "succeeded"
    ingestion.finished_at = datetime.now(timezone.utc)
    session.commit()
    return True


def get_stats(
    session: Session,
    dataset_id: UUID,
    room: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> list[StatsRow]:
    if session.get(Dataset, dataset_id) is None:
        raise DatasetNotFound()
    statement = select(
        Measurement.room,
        func.count(Measurement.id),
        func.avg(Measurement.co2_ppm),
        func.min(Measurement.co2_ppm),
        func.max(Measurement.co2_ppm),
        func.avg(Measurement.temperature_c),
        func.avg(Measurement.humidity_pct),
        func.max(Measurement.measured_at),
    ).where(Measurement.dataset_id == dataset_id)
    if room:
        statement = statement.where(Measurement.room == room)
    if from_time:
        statement = statement.where(Measurement.measured_at >= from_time)
    if to_time:
        statement = statement.where(Measurement.measured_at <= to_time)
    statement = statement.group_by(Measurement.room).order_by(Measurement.room)
    return [
        StatsRow(
            room=name,
            measurement_count=count,
            co2_avg=float(co2_avg),
            co2_min=co2_min,
            co2_max=co2_max,
            temperature_avg=float(temperature_avg),
            humidity_avg=float(humidity_avg),
            last_measured_at=last_measured_at,
        )
        for (
            name,
            count,
            co2_avg,
            co2_min,
            co2_max,
            temperature_avg,
            humidity_avg,
            last_measured_at,
        ) in session.execute(statement)
    ]

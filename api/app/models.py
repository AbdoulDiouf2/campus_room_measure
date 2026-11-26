from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Ingestion(Base):
    __tablename__ = "ingestions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_ingestions_status",
        ),
        CheckConstraint(
            "rows_accepted >= 0 AND rows_rejected >= 0 AND rows_duplicate >= 0",
            name="ck_ingestions_counts",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    rows_accepted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "room",
            "measured_at",
            name="uq_measurement_dataset_room_time",
        ),
        CheckConstraint("co2_ppm >= 0", name="ck_measurements_co2"),
        CheckConstraint(
            "humidity_pct >= 0 AND humidity_pct <= 100",
            name="ck_measurements_humidity",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingestion_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestions.id", ondelete="CASCADE"),
        nullable=False,
    )
    room: Mapped[str] = mapped_column(Text, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    co2_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature_c: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    humidity_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

"""HTTP contract for datasets, uploads, and room statistics."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from .database import get_session
from .models import Dataset
from .schemas import DatasetCreate, DatasetOut, IngestionOut, StatsRow
from .services import (
    create_dataset,
    create_ingestion,
    delete_dataset,
    get_dataset,
    get_ingestion,
    get_stats,
    list_datasets,
    list_ingestions,
    retry_ingestion,
)

router = APIRouter(prefix="/api")
MAX_CSV_BYTES = 1024 * 1024


def dataset_out(dataset: Dataset, count: int) -> DatasetOut:
    return DatasetOut(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        owner=dataset.owner,
        created_at=dataset.created_at,
        measurement_count=count,
    )


@router.post("/datasets", response_model=DatasetOut, status_code=201)
def create_dataset_route(
    data: DatasetCreate, session: Session = Depends(get_session)
) -> DatasetOut:
    dataset = create_dataset(session, data)
    return dataset_out(dataset, 0)


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets_route(session: Session = Depends(get_session)) -> list[DatasetOut]:
    return [dataset_out(item, count) for item, count in list_datasets(session)]


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset_route(
    dataset_id: UUID, session: Session = Depends(get_session)
) -> DatasetOut:
    dataset, count = get_dataset(session, dataset_id)
    return dataset_out(dataset, count)


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset_route(
    dataset_id: UUID, session: Session = Depends(get_session)
) -> None:
    delete_dataset(session, dataset_id)


@router.post(
    "/datasets/{dataset_id}/ingestions",
    response_model=IngestionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_ingestion_route(
    dataset_id: UUID,
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
    session: Session = Depends(get_session),
) -> IngestionOut:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if content_type.lower() != "text/csv":
        raise HTTPException(status_code=415, detail="Expected text/csv")
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_CSV_BYTES:
            raise HTTPException(status_code=413, detail="CSV exceeds 1 MiB")
    return IngestionOut.model_validate(
        create_ingestion(session, dataset_id, filename, bytes(content))
    )


@router.get("/datasets/{dataset_id}/ingestions", response_model=list[IngestionOut])
def list_ingestions_route(
    dataset_id: UUID, session: Session = Depends(get_session)
) -> list[IngestionOut]:
    return [
        IngestionOut.model_validate(item)
        for item in list_ingestions(session, dataset_id)
    ]


@router.get("/ingestions/{ingestion_id}", response_model=IngestionOut)
def get_ingestion_route(
    ingestion_id: UUID, session: Session = Depends(get_session)
) -> IngestionOut:
    return IngestionOut.model_validate(get_ingestion(session, ingestion_id))


@router.post(
    "/ingestions/{ingestion_id}/retry",
    response_model=IngestionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_ingestion_route(
    ingestion_id: UUID, session: Session = Depends(get_session)
) -> IngestionOut:
    return IngestionOut.model_validate(retry_ingestion(session, ingestion_id))


@router.get("/datasets/{dataset_id}/stats", response_model=list[StatsRow])
def stats_route(
    dataset_id: UUID,
    room: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
) -> list[StatsRow]:
    for value in (from_time, to_time):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise HTTPException(status_code=422, detail="Timezone required")
    if from_time is not None and to_time is not None and from_time > to_time:
        raise HTTPException(status_code=422, detail="Invalid period")
    return get_stats(session, dataset_id, room, from_time, to_time)

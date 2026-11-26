from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.database import SessionLocal, engine
from app.models import Dataset
from app.schemas import DatasetCreate
from app.services import (
    DatasetNameConflict,
    DatasetNotFound,
    create_dataset,
    get_dataset,
    list_datasets,
)


def test_create_dataset_and_reject_duplicate():
    if engine.url.database != "campus_test":
        pytest.fail("Ce test doit utiliser campus_test")

    name = f"Test jeu {uuid4().hex}"

    with SessionLocal() as session:
        created = create_dataset(session, DatasetCreate(name=f"  {name}  "))
        created_id = created.id

        try:
            assert created.name == name
            assert created.id is not None

            with pytest.raises(DatasetNameConflict):
                create_dataset(session, DatasetCreate(name=name))

            count = session.scalar(
                select(func.count(Dataset.id)).where(Dataset.name == name)
            )
            assert count == 1
        finally:
            session.execute(delete(Dataset).where(Dataset.id == created_id))
            session.commit()


def test_list_and_get_empty_dataset():
    if engine.url.database != "campus_test":
        pytest.fail("Ce test doit utiliser campus_test")

    name = f"Test lecture {uuid4().hex}"

    with SessionLocal() as session:
        created = create_dataset(session, DatasetCreate(name=name))
        created_id = created.id

        try:
            listed = {dataset.id: count for dataset, count in list_datasets(session)}
            assert listed[created_id] == 0

            dataset, count = get_dataset(session, created_id)
            assert dataset.name == name
            assert count == 0

            with pytest.raises(DatasetNotFound):
                get_dataset(session, uuid4())
        finally:
            session.execute(delete(Dataset).where(Dataset.id == created_id))
            session.commit()

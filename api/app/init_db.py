from . import models  # noqa: F401 — enregistre les trois modèles dans Base.metadata
from .database import Base, engine


def main() -> None:
    database_name = engine.url.database
    if database_name not in {"campus", "campus_test"}:
        raise SystemExit(f"Base inattendue : {database_name}")

    Base.metadata.create_all(engine)


if __name__ == "__main__":
    main()
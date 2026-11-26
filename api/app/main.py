# CONTEXTE ÉTUDIANT : S1-S2 | point d’entrée Uvicorn app.main:app
# À PRÉPARER / ADAPTER : Charger DATABASE_URL avant le lancement. Compléter les TODO selon le contrat.
# CONTRÔLE ATTENDU : Contrôler live/ready/version, puis les routes métier après votre réalisation.
#
"""Point d'entrée de l'API CampusData."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine
from .routes import router
from .services import (
    DatasetNameConflict,
    DatasetNotFound,
    IngestionConflict,
    IngestionNotFound,
)

logger = logging.getLogger(__name__)
app = FastAPI(title="CampusData", version="0.1.0")
app.include_router(router)


@app.exception_handler(DatasetNotFound)
@app.exception_handler(IngestionNotFound)
def not_found(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(DatasetNameConflict)
@app.exception_handler(IngestionConflict)
def conflict(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "Conflict"})


@app.exception_handler(SQLAlchemyError)
def database_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database request failed: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.exception_handler(Exception)
def unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unexpected request error: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health/live")
def live():
    """Vérifier le processus sans dépendre de la disponibilité de PostgreSQL."""
    # Une panne DB doit modifier la readiness, pas provoquer une boucle
    # de redémarrages d'un processus API qui fonctionne encore.
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    """Vérifier la connexion DB et la présence des trois tables métier."""
    try:
        # Le contexte libère la connexion même lorsqu'une exception remonte.
        with engine.connect() as connection:
            for table in ("datasets", "ingestions", "measurements"):
                connection.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    except SQLAlchemyError:
        # Réponse publique générique : ne jamais renvoyer le DSN ou le secret.
        # Cette interception est limitée à la probe. Dans les routes métier, distinguer
        # indisponibilité DB, conflit métier et erreur de programmation.
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ready"}


@app.get("/api/version")
def version():
    """Lire la référence écrite au build, ou dev lors d'une exécution locale."""
    # Le chemin est relatif au module, pas au dossier courant du terminal.
    version_file = Path(__file__).with_name("VERSION")
    value = version_file.read_text().strip() if version_file.exists() else "dev"
    # La version permet une vérification croisée avec le commit et le digest.
    # Ce champ seul ne prouve pas que toute la recette a été exécutée.
    return {"version": value}

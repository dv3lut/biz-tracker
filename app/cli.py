"""Command line entry points."""
from __future__ import annotations

from typing import Optional

import typer
import uvicorn

from app.api import create_app
from app.config import get_settings
from app.db import Base, get_engine, session_scope
from app.logging_config import configure_logging
from app.services.sync_service import SyncService

cli = typer.Typer(help="Outils de synchronisation avec l'API Sirene.")


@cli.command("init-db")
def init_db() -> None:
    """Créer les tables nécessaires dans la base de données."""
    
    settings = get_settings()
    configure_logging()
    typer.echo(f"Initialisation de la base de données sur {settings.database.sqlalchemy_url}")
    engine = get_engine()
    Base.metadata.create_all(engine)
    typer.echo("Tables créées (si nécessaire).")


@cli.command("sync-full")
def sync_full(
    resume: bool = typer.Option(True, help="Reprendre le curseur précédent si disponible."),
    max_records: Optional[int] = typer.Option(
        None,
        "--max-records",
        "-m",
        help="Nombre maximal d'établissements à traiter (ignorer pour la synchro complète).",
    ),
) -> None:
    """Lancer une synchronisation complète des restaurants."""

    configure_logging()
    service = SyncService()
    with session_scope() as session:
        run = service.run_full_sync(session, resume=resume, max_records=max_records)
        typer.echo(f"Synchronisation complète terminée: run={run.id} status={run.status}")


@cli.command("sync-incremental")
def sync_incremental() -> None:
    """Lancer une synchronisation incrémentale basée sur la dernière mise à jour Sirene."""

    configure_logging()
    service = SyncService()
    with session_scope() as session:
        run = service.run_incremental_sync(session)
        if run:
            typer.echo(f"Synchronisation incrémentale terminée: run={run.id} status={run.status}")
        else:
            typer.echo("Aucune mise à jour disponible.")


@cli.command("serve")
def serve(
    host: Optional[str] = typer.Option(None, help="Adresse d'écoute (défaut: configuration API)."),
    port: Optional[int] = typer.Option(None, help="Port d'écoute (défaut: configuration API)."),
) -> None:
    """Démarrer l'API FastAPI en s'appuyant sur la configuration."""

    configure_logging()
    settings = get_settings()
    api_settings = settings.api
    app = create_app()

    uvicorn.run(
        app,
        host=host or api_settings.host,
        port=port or api_settings.port,
        log_config=None,
    )


def main() -> None:
    cli()

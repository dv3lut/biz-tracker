"""Command line entry points."""
from __future__ import annotations

from typing import Optional

import typer
import uvicorn

from app.api import create_app
from app.config import get_settings
from app.db import Base, get_engine, session_scope
from app.db.migrations import run_schema_upgrades
from app.logging_config import configure_logging
from app.services.sync_service import SyncService
from app.db import models

cli = typer.Typer(help="Outils de synchronisation avec l'API Sirene.")


@cli.command("init-db")
def init_db() -> None:
    """Créer les tables nécessaires dans la base de données."""
    
    settings = get_settings()
    configure_logging()
    typer.echo(f"Initialisation de la base de données sur {settings.database.sqlalchemy_url}")
    engine = get_engine()
    Base.metadata.create_all(engine)
    run_schema_upgrades(engine)
    typer.echo("Tables créées (si nécessaire).")


def _execute_sync(check_for_updates: bool) -> None:
    configure_logging()
    service = SyncService()
    with session_scope() as session:
        run = service.prepare_sync_run(
            session,
            check_informations=check_for_updates,
        )
        if run is None:
            typer.echo("Aucune mise à jour à synchroniser.")
            return
        run_id = run.id

    typer.echo(f"Synchronisation programmée: run={run_id}")
    service.execute_sync_run(run_id, triggered_by="cli")

    with session_scope() as session:
        final_run = session.get(models.SyncRun, run_id)
        status = final_run.status if final_run else "inconnu"
    typer.echo(f"Synchronisation terminée: run={run_id} status={status}")


@cli.command("sync")
def sync(
    check_for_updates: bool = typer.Option(
        False,
        "--check-for-updates/--no-check-for-updates",
        help="Annule automatiquement si aucune nouvelle donnée n'est disponible côté Sirene.",
    ),
) -> None:
    """Lancer la synchronisation unifiée des restaurants."""

    _execute_sync(check_for_updates=check_for_updates)


@cli.command("sync-full", hidden=True)
def sync_full_legacy(
) -> None:
    """Alias rétrocompatibilité vers la synchronisation unifiée."""

    typer.echo("Commande 'sync-full' obsolète. Utilisation de 'sync'.")
    _execute_sync(check_for_updates=False)


@cli.command("sync-incremental", hidden=True)
def sync_incremental_legacy() -> None:
    """Alias rétrocompatibilité vers la synchronisation unifiée."""

    typer.echo("Commande 'sync-incremental' obsolète. Utilisation de 'sync'.")
    _execute_sync(check_for_updates=False)


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

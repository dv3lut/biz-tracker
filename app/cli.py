"""Command line entry points."""
from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional
from uuid import UUID

import typer
import uvicorn

from app.api.schemas import SyncRequest
from app.api import create_app
from app.config import get_settings
from app.db import Base, get_engine, session_scope
from app.db.migrations import run_schema_upgrades
from app.logging_config import configure_logging
from app.services.sync.mode import SyncMode
from app.services.sync.replay_reference import DayReplayReference
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


def _parse_replay_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # noqa: BLE001
        raise typer.BadParameter("Format attendu: YYYY-MM-DD") from exc


def _execute_sync(
    check_for_updates: bool,
    mode: SyncMode,
    replay_for_date: date | None = None,
    replay_reference: DayReplayReference = DayReplayReference.CREATION_DATE,
    target_naf_codes: list[str] | None = None,
    target_client_ids: list[str] | None = None,
    google_statuses: list[str] | None = None,
    notify_admins: bool = True,
    force_google_replay: bool = False,
) -> None:
    if replay_for_date and not mode.requires_replay_date:
        raise typer.BadParameter("--replay-for-date est uniquement compatible avec le mode 'day_replay'.")
    configure_logging()
    service = SyncService()
    with session_scope() as session:
        run = service.prepare_sync_run(
            session,
            check_informations=check_for_updates,
            mode=mode,
            replay_for_date=replay_for_date,
            replay_reference=replay_reference,
            target_naf_codes=target_naf_codes,
            target_client_ids=[UUID(value) for value in target_client_ids] if target_client_ids else None,
            google_statuses=google_statuses,
            notify_admins=notify_admins,
            force_google_replay=force_google_replay,
        )
        if run is None:
            typer.echo("Aucune mise à jour à synchroniser.")
            return
        run_id = run.id

    typer.echo(f"Synchronisation programmée: run={run_id} mode={mode.value}")
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
    mode: SyncMode = typer.Option(
        SyncMode.FULL,
        "--mode",
        case_sensitive=False,
        help=(
            "Mode d'exécution: 'full' déclenche Sirene + Google, 'sirene_only' saute Google, "
            "'google_refresh' relance Google selon les statuts ciblés, "
            "'day_replay' rejoue une journée complète sans notifier les clients."
        ),
    ),
    replay_for_date: Optional[str] = typer.Option(
        None,
        "--replay-for-date",
        help="Date (YYYY-MM-DD) à rejouer lorsque le mode 'day_replay' est sélectionné.",
    ),
    replay_reference: DayReplayReference = typer.Option(
        DayReplayReference.CREATION_DATE,
        "--replay-reference",
        case_sensitive=False,
        help=(
            "Référence utilisée pour le rejeu: 'creation_date' filtre par date Sirene, "
            "'insertion_date' par date d'insertion en base (mode 'day_replay')."
        ),
    ),
    naf_codes: Optional[List[str]] = typer.Option(
        None,
        "--naf-code",
        help="Code NAF ciblé (ex: 5610A). Peut être répété pour filtrer plusieurs codes.",
    ),
    target_client_ids: Optional[List[str]] = typer.Option(
        None,
        "--target-client",
        help="Client (UUID) à notifier lors d'un rejeu. Peut être répété.",
    ),
    google_statuses: Optional[List[str]] = typer.Option(
        None,
        "--google-status",
        help="Statut Google à relancer (ex: pending). Peut être répété pour filtrer plusieurs statuts.",
    ),
    notify_admins: bool = typer.Option(
        True,
        "--notify-admins/--skip-admins",
        help="Contrôle l'envoi de l'alerte administrateur (mode 'day_replay').",
    ),
    force_google_replay: bool = typer.Option(
        False,
        "--force-google-replay/--no-force-google-replay",
        help="Force un nouvel enrichissement Google lors d'un rejeu même si des fiches existent déjà.",
    ),
) -> None:
    """Lancer la synchronisation unifiée des restaurants."""

    replay_date = _parse_replay_date(replay_for_date)
    request = SyncRequest(
        check_for_updates=check_for_updates,
        mode=mode,
        replay_for_date=replay_date,
        replay_reference=replay_reference,
        naf_codes=naf_codes,
        target_client_ids=target_client_ids,
        google_statuses=google_statuses,
        notify_admins=notify_admins,
        force_google_replay=force_google_replay,
    )
    _execute_sync(
        check_for_updates=request.check_for_updates,
        mode=request.mode,
        replay_for_date=request.replay_for_date,
        replay_reference=request.replay_reference,
        target_naf_codes=request.naf_codes,
        target_client_ids=[str(client_id) for client_id in request.target_client_ids] if request.target_client_ids else None,
        google_statuses=request.google_statuses,
        notify_admins=request.notify_admins,
        force_google_replay=request.force_google_replay,
    )


@cli.command("sync-full", hidden=True)
def sync_full_legacy(
) -> None:
    """Alias rétrocompatibilité vers la synchronisation unifiée."""

    typer.echo("Commande 'sync-full' obsolète. Utilisation de 'sync'.")
    _execute_sync(check_for_updates=False, mode=SyncMode.FULL)


@cli.command("sync-incremental", hidden=True)
def sync_incremental_legacy() -> None:
    """Alias rétrocompatibilité vers la synchronisation unifiée."""

    typer.echo("Commande 'sync-incremental' obsolète. Utilisation de 'sync'.")
    _execute_sync(check_for_updates=False, mode=SyncMode.FULL)


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

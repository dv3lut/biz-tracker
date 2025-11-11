"""Administrative and monitoring endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_db_session, require_admin
from app.api.schemas import (
    AlertOut,
    AdminEmailConfig,
    AdminEmailConfigUpdate,
    DashboardMetrics,
    DashboardRunBreakdown,
    DeleteRunResult,
    EmailTestRequest,
    EmailTestResponse,
    EstablishmentOut,
    EstablishmentDetailOut,
    ClientCreate,
    ClientOut,
    ClientUpdate,
    GoogleStatusBreakdown,
    ManualGoogleCheckResponse,
    StatsSummary,
    SyncRequest,
    SyncRunOut,
    SyncStateOut,
)
from app.config import get_settings
from app.db import models
from app.observability import log_event
from app.services.email_service import EmailService
from app.services.google_business_service import GoogleBusinessService
from app.services.export_service import build_google_places_workbook
from app.services.sync_service import SyncService
from app.services.client_service import (
    collect_client_emails,
    dispatch_email_to_clients,
    get_active_clients,
    get_admin_emails,
    get_all_clients,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

def _serialize_run(run: models.SyncRun | None, *, state: models.SyncState | None = None) -> SyncRunOut | None:
    if run is None:
        return None
    enriched = SyncRunOut.model_validate(run)
    total_expected, progress, remaining_seconds, eta = _compute_run_metrics(run, state)
    enriched.total_expected_records = total_expected
    enriched.progress = progress
    enriched.estimated_remaining_seconds = remaining_seconds
    enriched.estimated_completion_at = eta
    return enriched


def _serialize_alert(alert: models.Alert | None) -> AlertOut | None:
    if alert is None:
        return None
    return AlertOut.model_validate(alert)


def _compute_run_metrics(
    run: models.SyncRun,
    state: models.SyncState | None,
) -> tuple[int | None, float | None, float | None, datetime | None]:
    target_raw = state.last_total if state and state.last_total is not None else run.max_records
    total_expected: int | None
    try:
        total_candidate = int(target_raw) if target_raw is not None else None
    except (TypeError, ValueError):
        total_candidate = None
    total_expected = total_candidate if total_candidate and total_candidate > 0 else None

    progress: float | None = None
    if total_expected:
        progress = min(run.fetched_records / total_expected, 1.0)

    estimated_remaining_seconds: float | None = None
    estimated_completion_at: datetime | None = None
    if run.status == "running" and total_expected and run.fetched_records > 0:
        now = datetime.utcnow()
        elapsed_seconds = max((now - run.started_at).total_seconds(), 0.0)
        if elapsed_seconds > 0:
            rate = run.fetched_records / elapsed_seconds
            if rate > 0:
                remaining = max(total_expected - run.fetched_records, 0)
                estimated_remaining_seconds = remaining / rate if remaining > 0 else 0.0
                estimated_completion_at = now + timedelta(seconds=estimated_remaining_seconds)

    return total_expected, progress, estimated_remaining_seconds, estimated_completion_at


def _format_establishment_summary(establishment: models.Establishment, *, include_google: bool = True) -> list[str]:
    lines = [
        f"- {establishment.name or '(nom indisponible)'}",
        f"  SIRET: {establishment.siret} | NAF: {establishment.naf_code or 'N/A'}",
    ]
    address_parts = [
        element
        for element in [
            establishment.numero_voie,
            establishment.type_voie,
            establishment.libelle_voie,
        ]
        if element
    ]
    commune_parts = [
        part
        for part in [
            establishment.code_postal,
            establishment.libelle_commune or establishment.libelle_commune_etranger,
        ]
        if part
    ]
    lines.append(f"  Adresse: {' '.join(address_parts) if address_parts else 'N/A'}")
    lines.append(f"           {' '.join(commune_parts) if commune_parts else ''}")
    if establishment.date_creation:
        lines.append(f"  Création: {establishment.date_creation.isoformat()}")
    if include_google:
        if establishment.google_place_url:
            lines.append(f"  Google: {establishment.google_place_url}")
        if establishment.google_place_id:
            lines.append(f"  Place ID: {establishment.google_place_id}")
    return lines


def _normalize_emails(emails: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for email in emails:
        if not email:
            continue
        candidate = email.strip().lower()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


@router.get("/stats/summary", response_model=StatsSummary, summary="Synthèse des métriques principales")
def get_stats_summary(session: Session = Depends(get_db_session)) -> StatsSummary:
    total_establishments = session.execute(select(func.count(models.Establishment.siret))).scalar_one()
    total_alerts = session.execute(select(func.count(models.Alert.id))).scalar_one()
    database_size_pretty = session.execute(
        select(func.pg_size_pretty(func.pg_database_size(func.current_database())))
    ).scalar_one()

    service = SyncService()
    target_scope = service.settings.sync.scope_key

    last_run_stmt = (
        select(models.SyncRun)
        .where(models.SyncRun.scope_key == target_scope)
        .order_by(models.SyncRun.started_at.desc())
        .limit(1)
    )
    last_run = session.execute(last_run_stmt).scalar_one_or_none()
    if not last_run:
        fallback_stmt = select(models.SyncRun).order_by(models.SyncRun.started_at.desc()).limit(1)
        last_run = session.execute(fallback_stmt).scalar_one_or_none()

    last_alert_stmt = select(models.Alert).order_by(models.Alert.created_at.desc()).limit(1)
    last_alert = session.execute(last_alert_stmt).scalar_one_or_none()

    last_run_state = session.get(models.SyncState, last_run.scope_key) if last_run else None

    return StatsSummary(
        total_establishments=total_establishments,
        total_alerts=total_alerts,
        last_run=_serialize_run(last_run, state=last_run_state),
        last_alert=_serialize_alert(last_alert),
        database_size_pretty=database_size_pretty,
    )


@router.get(
    "/stats/dashboard",
    response_model=DashboardMetrics,
    summary="Tableau de bord consolidé des indicateurs journaliers",
)
def get_dashboard_metrics(
    days: int = Query(30, ge=1, le=180, description="Nombre de jours à couvrir pour les séries temporelles."),
    session: Session = Depends(get_db_session),
) -> DashboardMetrics:
    now = datetime.utcnow()
    start_date = now.date() - timedelta(days=days - 1) if days > 1 else now.date()
    since_dt = datetime.combine(start_date, datetime.min.time())

    service = SyncService()
    scope_key = service.settings.sync.scope_key

    last_run_stmt = (
        select(models.SyncRun)
        .where(models.SyncRun.scope_key == scope_key, models.SyncRun.status == "success")
        .order_by(models.SyncRun.started_at.desc())
        .limit(1)
    )
    last_run = session.execute(last_run_stmt).scalar_one_or_none()
    if not last_run:
        fallback_stmt = (
            select(models.SyncRun)
            .where(models.SyncRun.status == "success")
            .order_by(models.SyncRun.started_at.desc())
            .limit(1)
        )
        last_run = session.execute(fallback_stmt).scalar_one_or_none()

    last_run_state = session.get(models.SyncState, last_run.scope_key) if last_run else None
    serialized_last_run = _serialize_run(last_run, state=last_run_state)

    latest_run_breakdown = None
    if last_run:
        run_google_rows = (
            session.execute(
                select(
                    models.Establishment.google_check_status,
                    func.count(models.Establishment.siret),
                )
                .where(models.Establishment.created_run_id == last_run.id)
                .group_by(models.Establishment.google_check_status)
            )
            .all()
        )
        run_google_counts = {"found": 0, "not_found": 0, "insufficient": 0, "pending": 0, "other": 0}
        for status, count in run_google_rows:
            key = status or "pending"
            bucket = key if key in run_google_counts else "other"
            run_google_counts[bucket] += int(count or 0)

        alerts_row = session.execute(
            select(
                func.count(models.Alert.id).label("created"),
                func.count(models.Alert.sent_at).label("sent"),
            ).where(models.Alert.run_id == last_run.id)
        ).one()

        latest_run_breakdown = DashboardRunBreakdown(
            run_id=last_run.id,
            started_at=last_run.started_at,
            created_records=last_run.created_records,
            updated_records=last_run.updated_records,
            api_call_count=last_run.api_call_count,
            google_found=last_run.google_immediate_matched_count,
            google_found_late=last_run.google_late_matched_count,
            google_not_found=run_google_counts["not_found"],
            google_insufficient=run_google_counts["insufficient"],
            google_pending=run_google_counts["pending"],
            google_other=run_google_counts["other"],
            alerts_created=int(alerts_row.created or 0),
            alerts_sent=int(alerts_row.sent or 0),
        )

    runs_rows = (
        session.execute(
            select(
                func.date_trunc("day", models.SyncRun.started_at).label("day"),
                func.sum(models.SyncRun.created_records).label("created"),
                func.sum(models.SyncRun.api_call_count).label("api_calls"),
                func.count(models.SyncRun.id).label("run_count"),
            )
            .where(
                models.SyncRun.run_type == "sync",
                models.SyncRun.status == "success",
                models.SyncRun.started_at >= since_dt,
            )
            .group_by("day")
            .order_by("day")
        )
        .all()
    )
    runs_map = {row.day.date(): row for row in runs_rows}

    daily_new_businesses: list[dict[str, object]] = []
    daily_api_calls: list[dict[str, object]] = []
    for index in range(days):
        day = start_date + timedelta(days=index)
        row = runs_map.get(day)
        created = int(row.created or 0) if row else 0
        api_calls = int(row.api_calls or 0) if row else 0
        run_count = int(row.run_count or 0) if row else 0
        daily_new_businesses.append({"date": day, "value": created})
        daily_api_calls.append({"date": day, "value": api_calls, "run_count": run_count})

    alerts_rows = (
        session.execute(
            select(
                func.date_trunc("day", models.Alert.created_at).label("day"),
                func.count(models.Alert.id).label("created"),
                func.count(models.Alert.sent_at).label("sent"),
            )
            .where(models.Alert.created_at >= since_dt)
            .group_by("day")
            .order_by("day")
        )
        .all()
    )
    alerts_map = {row.day.date(): row for row in alerts_rows}
    daily_alerts: list[dict[str, object]] = []
    for index in range(days):
        day = start_date + timedelta(days=index)
        row = alerts_map.get(day)
        created = int(row.created or 0) if row else 0
        sent = int(row.sent or 0) if row else 0
        daily_alerts.append({"date": day, "created": created, "sent": sent})

    global_google_rows = (
        session.execute(
            select(
                models.Establishment.google_check_status,
                func.count(models.Establishment.siret),
            ).group_by(models.Establishment.google_check_status)
        )
        .all()
    )
    global_google_counts = {"found": 0, "not_found": 0, "insufficient": 0, "pending": 0, "other": 0}
    for status, count in global_google_rows:
        key = status or "pending"
        bucket = key if key in global_google_counts else "other"
        global_google_counts[bucket] += int(count or 0)

    establishment_rows = (
        session.execute(
            select(
                models.Establishment.etat_administratif,
                func.count(models.Establishment.siret),
            ).group_by(models.Establishment.etat_administratif)
        )
        .all()
    )
    establishment_breakdown: dict[str, int] = {}
    for status, count in establishment_rows:
        key = status or "INCONNU"
        establishment_breakdown[key] = int(count or 0)

    return DashboardMetrics(
        latest_run=serialized_last_run,
        latest_run_breakdown=latest_run_breakdown,
        daily_new_businesses=daily_new_businesses,
        daily_api_calls=daily_api_calls,
        daily_alerts=daily_alerts,
        google_status_breakdown=GoogleStatusBreakdown(**global_google_counts),
        establishment_status_breakdown=establishment_breakdown,
    )


@router.post(
    "/email/test",
    response_model=EmailTestResponse,
    summary="Envoyer un e-mail de test",
)
def send_test_email(
    payload: EmailTestRequest = Body(default_factory=EmailTestRequest),
    session: Session = Depends(get_db_session),
) -> EmailTestResponse:
    settings = get_settings().email
    email_service = EmailService()

    if not email_service.is_enabled():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le service e-mail est désactivé.")

    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration SMTP incomplète (hôte ou adresse expéditeur manquants).",
        )

    if payload.recipients:
        recipients = _normalize_emails(payload.recipients)
    else:
        recipients = _normalize_emails(get_admin_emails(session))
        if not recipients:
            recipients = collect_client_emails(get_active_clients(session))
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun destinataire configuré.")

    provider = settings.provider or "SMTP"
    subject = payload.subject or f"[{provider}] Test Biz Tracker"
    body = payload.body or (
        "Ce message confirme que la configuration SMTP de Biz Tracker fonctionne.\n"
        "Vous recevez cet e-mail car l'endpoint /admin/email/test a été appelé."
    )

    email_service.send(subject, body, recipients)
    log_event(
        "email.test_sent",
        provider=provider,
        recipients=recipients,
    )
    return EmailTestResponse(sent=True, provider=provider, subject=subject, recipients=recipients)


@router.post(
    "/establishments/{siret}/google-check",
    response_model=ManualGoogleCheckResponse,
    summary="Vérifier un établissement via Google Places et envoyer une alerte",
)
def manual_google_check(
    siret: str,
    session: Session = Depends(get_db_session),
) -> ManualGoogleCheckResponse:
    settings = get_settings()
    google_settings = settings.google
    if not google_settings.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'enrichissement Google est désactivé ou la clé API est absente.",
        )

    email_service = EmailService()
    if not email_service.is_enabled():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le service e-mail est désactivé.")
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration SMTP incomplète (hôte ou adresse expéditeur manquants).",
        )

    active_clients = get_active_clients(session)
    eligible_clients = [client for client in active_clients if any(recipient.email for recipient in client.recipients)]
    configured_recipients = collect_client_emails(eligible_clients)
    if not configured_recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun destinataire configuré.")

    establishment = session.get(models.Establishment, siret)
    if establishment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")

    google_service = GoogleBusinessService(session)
    try:
        match = google_service.manual_check(establishment)
    finally:
        google_service.close()

    session.refresh(establishment)

    found = match is not None
    check_status = establishment.google_check_status
    place_url = establishment.google_place_url
    place_id = establishment.google_place_id

    email_sent = False
    partial_failure = False
    if found:
        subject = (
            f"[{settings.sync.scope_key}] Page Google détectée pour "
            f"{establishment.name or establishment.siret}"
        )
        message_lines = [
            "Une vérification manuelle Google Places vient d'être effectuée.",
            "",
            *_format_establishment_summary(establishment),
            "",
            "Cette recherche a été déclenchée depuis la console d'administration Biz Tracker.",
        ]
        if not establishment.google_place_url:
            message_lines.insert(
                3,
                "  Attention : Google Places n'a pas fourni d'URL publique pour cette fiche (Place ID uniquement).",
            )
        body = "\n".join(message_lines)
        dispatch_result = dispatch_email_to_clients(email_service, eligible_clients, subject, body)
        partial_failure = bool(dispatch_result.failed)

        for client, exc in dispatch_result.failed:
            log_event(
                "manual_google.email.error",
                client_id=str(client.id),
                siret=siret,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        if dispatch_result.delivered:
            email_sent = True
        else:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Échec de l'envoi de l'e-mail d'alerte.",
            )

    if check_status == "insufficient":
        message = "Informations insuffisantes pour lancer une recherche Google."
    elif found:
        if email_sent:
            if partial_failure:
                message = (
                    "Une page Google a été trouvée. Certains clients n'ont pas pu être notifiés, "
                    "consultez les logs pour les détails."
                )
            else:
                message = "Une page Google a été trouvée et les destinataires ont été notifiés."
        else:
            message = "Une page Google a été trouvée mais aucun e-mail n'a été envoyé."
    else:
        message = "Aucune page Google n'a été trouvée pour cet établissement."

    log_event(
        "sync.google.manual_check",
        siret=siret,
        found=found,
        email_sent=email_sent,
        partial_failure=partial_failure,
        configured_recipients=len(configured_recipients),
        place_id=place_id,
        place_url=place_url,
        check_status=check_status,
    )

    establishment_payload = EstablishmentOut.model_validate(establishment)
    return ManualGoogleCheckResponse(
        found=found,
        email_sent=email_sent,
        message=message,
        place_id=place_id,
        place_url=place_url,
        check_status=check_status,
        establishment=establishment_payload,
    )


@router.get(
    "/google/places-export",
    summary="Exporter les établissements enrichis via Google Places",
)
def export_google_places(session: Session = Depends(get_db_session)) -> StreamingResponse:
    stmt = (
        select(models.Establishment)
        .where(
            or_(
                models.Establishment.google_place_url.is_not(None),
                models.Establishment.google_place_id.is_not(None),
            )
        )
        .order_by(
            models.Establishment.google_last_found_at.desc().nullslast(),
            models.Establishment.last_seen_at.desc(),
        )
    )
    establishments = session.execute(stmt).scalars().all()
    workbook_stream = build_google_places_workbook(establishments)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"biz-tracker-google-places-{timestamp}.xlsx"

    log_event(
        "export.google.places",
        count=len(establishments),
        filename=filename,
    )

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        workbook_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get(
    "/establishments/{siret}",
    response_model=EstablishmentDetailOut,
    summary="Consulter le détail complet d'un établissement",
)
def get_establishment_detail(
    siret: str,
    session: Session = Depends(get_db_session),
) -> EstablishmentDetailOut:
    entity = session.get(models.Establishment, siret)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")
    return EstablishmentDetailOut.model_validate(entity)


@router.get("/sync-runs", response_model=list[SyncRunOut], summary="Historique des synchronisations")
def list_sync_runs(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[SyncRunOut]:
    stmt = select(models.SyncRun).order_by(models.SyncRun.started_at.desc()).limit(limit)
    runs = session.execute(stmt).scalars().all()
    states = session.execute(select(models.SyncState)).scalars().all()
    states_by_scope = {state.scope_key: state for state in states}
    return [
        _serialize_run(run, state=states_by_scope.get(run.scope_key))
        for run in runs
    ]


@router.get("/sync-state", response_model=list[SyncStateOut], summary="État des curseurs et checkpoints")
def list_sync_state(session: Session = Depends(get_db_session)) -> list[SyncStateOut]:
    states = session.execute(select(models.SyncState).order_by(models.SyncState.scope_key)).scalars().all()
    return [SyncStateOut.model_validate(state) for state in states]


@router.get("/alerts/recent", response_model=list[AlertOut], summary="Dernières alertes générées")
def list_recent_alerts(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[AlertOut]:
    stmt = select(models.Alert).order_by(models.Alert.created_at.desc()).limit(limit)
    alerts = session.execute(stmt).scalars().all()
    return [AlertOut.model_validate(alert) for alert in alerts]


@router.get(
    "/establishments",
    response_model=list[EstablishmentOut],
    summary="Lister les établissements actifs",
)
def list_establishments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, alias="q", description="Filtre sur SIRET, nom ou code postal"),
    session: Session = Depends(get_db_session),
) -> list[EstablishmentOut]:
    query = session.query(models.Establishment).filter(models.Establishment.etat_administratif == "A")
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                models.Establishment.siret.ilike(pattern),
                models.Establishment.name.ilike(pattern),
                models.Establishment.code_postal.ilike(pattern),
            )
        )
    establishments = (
        query.order_by(
            models.Establishment.date_creation.desc(),
            models.Establishment.last_seen_at.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [EstablishmentOut.model_validate(item) for item in establishments]


@router.delete(
    "/sync-runs/{run_id}",
    response_model=DeleteRunResult,
    summary="Supprimer un run et les données associées",
)
def delete_sync_run(
    run_id: UUID,
    session: Session = Depends(get_db_session),
) -> DeleteRunResult:
    run = session.get(models.SyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run introuvable.")

    alerts_deleted = (
        session.query(models.Alert)
        .filter(models.Alert.run_id == run_id)
        .delete(synchronize_session=False)
    )

    establishments_deleted = (
        session.query(models.Establishment)
        .filter(models.Establishment.created_run_id == run_id)
        .delete(synchronize_session=False)
    )

    session.query(models.Establishment).filter(models.Establishment.last_run_id == run_id).update(
        {models.Establishment.last_run_id: None}, synchronize_session=False
    )

    states_reset = (
        session.query(models.SyncState)
        .filter(models.SyncState.last_successful_run_id == run_id)
        .update(
            {
                models.SyncState.last_successful_run_id: None,
                models.SyncState.last_cursor: None,
                models.SyncState.cursor_completed: False,
                models.SyncState.last_synced_at: None,
                models.SyncState.last_total: None,
                models.SyncState.last_treated_max: None,
                models.SyncState.query_checksum: None,
            },
            synchronize_session=False,
        )
    )

    runs_updated = (
        session.query(models.SyncRun)
        .filter(models.SyncRun.resumed_from_run_id == run_id)
        .update({models.SyncRun.resumed_from_run_id: None}, synchronize_session=False)
    )

    session.delete(run)
    session.flush()

    return DeleteRunResult(
        establishments_deleted=establishments_deleted,
        alerts_deleted=alerts_deleted,
        states_reset=states_reset,
        runs_updated=runs_updated,
        sync_run_deleted=True,
    )


@router.delete(
    "/establishments/{siret}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un établissement",
)
def delete_establishment(
    siret: str,
    session: Session = Depends(get_db_session),
) -> None:
    entity = session.get(models.Establishment, siret)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")
    session.delete(entity)
    session.flush()


@router.post(
    "/sync",
    response_model=SyncRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Déclencher une synchronisation",
)
def trigger_sync_run(
    payload: SyncRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
) -> SyncRunOut:
    service = SyncService()
    scope_key = service.settings.sync.scope_key
    if service.has_active_run(session, scope_key):
        log_event(
            "sync.run.request_rejected",
            scope_key=scope_key,
            reason="active_run",
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Une synchronisation est déjà en cours.")

    run = service.prepare_sync_run(
        session,
        resume=payload.resume,
        check_informations=payload.check_for_updates,
    )
    if run is None:
        log_event(
            "sync.run.request_no_updates",
            scope_key=scope_key,
            resume=payload.resume,
            check_informations=payload.check_for_updates,
        )
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Aucune mise à jour disponible.")

    session.commit()
    session.refresh(run)
    state = session.get(models.SyncState, run.scope_key)

    log_event(
        "sync.run.request_accepted",
        run_id=str(run.id),
        scope_key=scope_key,
        resume=payload.resume,
        check_informations=payload.check_for_updates,
    )

    background_tasks.add_task(
        service.execute_sync_run,
        run.id,
        resume=payload.resume,
        triggered_by="api",
    )
    return _serialize_run(run, state=state)

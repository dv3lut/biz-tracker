"""Database models."""
from __future__ import annotations

import uuid
from datetime import datetime, date

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.business_types import is_individual_company
from app.utils.google_listing import default_listing_statuses
from app.utils.dates import utcnow


def _default_client_listing_statuses() -> list[str]:
    """Provide a fresh copy of the default listing statuses for alerts."""

    return default_listing_statuses()


class Establishment(Base):
    """Restaurant establishment tracked by the system."""

    __tablename__ = "establishments"

    siret: Mapped[str] = mapped_column(String(14), primary_key=True)
    siren: Mapped[str] = mapped_column(String(9), nullable=False, index=True)
    nic: Mapped[str | None] = mapped_column(String(5), nullable=True)
    naf_code: Mapped[str | None] = mapped_column(String(10), index=True)
    naf_libelle: Mapped[str | None] = mapped_column(String(255))
    etat_administratif: Mapped[str | None] = mapped_column(String(1), index=True)
    date_creation: Mapped[date | None] = mapped_column(Date)
    date_debut_activite: Mapped[date | None] = mapped_column(Date)
    date_dernier_traitement_etablissement: Mapped[datetime | None] = mapped_column(DateTime)
    date_dernier_traitement_unite_legale: Mapped[datetime | None] = mapped_column(DateTime)

    name: Mapped[str | None] = mapped_column(String(255), index=True)
    denomination_unite_legale: Mapped[str | None] = mapped_column(String(255))
    denomination_usuelle_unite_legale: Mapped[str | None] = mapped_column(String(255))
    denomination_usuelle_etablissement: Mapped[str | None] = mapped_column(String(255))
    enseigne1: Mapped[str | None] = mapped_column(String(255))
    enseigne2: Mapped[str | None] = mapped_column(String(255))
    enseigne3: Mapped[str | None] = mapped_column(String(255))
    categorie_juridique: Mapped[str | None] = mapped_column(String(10))
    categorie_entreprise: Mapped[str | None] = mapped_column(String(10))
    tranche_effectifs: Mapped[str | None] = mapped_column(String(10))
    annee_effectifs: Mapped[int | None] = mapped_column(Integer)
    nom_usage: Mapped[str | None] = mapped_column(String(255))
    nom: Mapped[str | None] = mapped_column(String(255))
    prenom1: Mapped[str | None] = mapped_column(String(255))
    prenom2: Mapped[str | None] = mapped_column(String(255))
    prenom3: Mapped[str | None] = mapped_column(String(255))
    prenom4: Mapped[str | None] = mapped_column(String(255))
    prenom_usuel: Mapped[str | None] = mapped_column(String(255))
    pseudonyme: Mapped[str | None] = mapped_column(String(255))
    sexe: Mapped[str | None] = mapped_column(String(10))
    created_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sync_runs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sync_runs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    complement_adresse: Mapped[str | None] = mapped_column(String(255))
    numero_voie: Mapped[str | None] = mapped_column(String(10))
    indice_repetition: Mapped[str | None] = mapped_column(String(5))
    type_voie: Mapped[str | None] = mapped_column(String(50))
    libelle_voie: Mapped[str | None] = mapped_column(String(255))
    distribution_speciale: Mapped[str | None] = mapped_column(String(255))
    code_postal: Mapped[str | None] = mapped_column(String(10), index=True)
    libelle_commune: Mapped[str | None] = mapped_column(String(255))
    libelle_commune_etranger: Mapped[str | None] = mapped_column(String(255))
    code_commune: Mapped[str | None] = mapped_column(String(10), index=True)
    code_cedex: Mapped[str | None] = mapped_column(String(10))
    libelle_cedex: Mapped[str | None] = mapped_column(String(255))
    code_pays: Mapped[str | None] = mapped_column(String(10))
    libelle_pays: Mapped[str | None] = mapped_column(String(255))

    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    google_place_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    google_place_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    google_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    google_last_found_at: Mapped[datetime | None] = mapped_column(DateTime)
    google_check_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    google_match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    google_category_match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    google_listing_origin_at: Mapped[datetime | None] = mapped_column(DateTime)
    google_listing_origin_source: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    google_listing_age_status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    google_contact_phone: Mapped[str | None] = mapped_column(String(64))
    google_contact_email: Mapped[str | None] = mapped_column(String(255))
    google_contact_website: Mapped[str | None] = mapped_column(String(512))

    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="establishment")

    @property
    def is_sole_proprietorship(self) -> bool:
        """Return True when the establishment is classified as an entreprise individuelle."""

        return is_individual_company(self.categorie_juridique)


class SyncRun(Base):
    """Track each execution of the synchronization pipeline."""

    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope_key: Mapped[str] = mapped_column(String(255), index=True)
    run_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="full", nullable=False)
    replay_for_date: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_cursor: Mapped[str | None] = mapped_column(Text)
    query_checksum: Mapped[str | None] = mapped_column(String(64))
    api_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    google_api_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fetched_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    google_queue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    google_eligible_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    google_matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    google_pending_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    google_immediate_matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    google_late_matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[dict[str, object] | None] = mapped_column(JSONB, default=None)
    resumed_from_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sync_runs.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    max_records: Mapped[int | None] = mapped_column(Integer)
    reset_state: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    truncate_before_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    target_naf_codes: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    initial_backfill: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    target_client_ids: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    notify_admins: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    google_reset_state: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    day_replay_force_google: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    day_replay_reference: Mapped[str] = mapped_column(String(32), default="creation_date", nullable=False)

    previous_run: Mapped[SyncRun | None] = relationship(remote_side=[id], backref="resumed_runs")
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="run")


class SyncState(Base):
    """Persist last known state for each synchronization scope."""

    __tablename__ = "sync_state"

    scope_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_successful_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sync_runs.id"))
    last_cursor: Mapped[str | None] = mapped_column(Text)
    cursor_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_total: Mapped[int | None] = mapped_column(Integer)
    last_treated_max: Mapped[datetime | None] = mapped_column(DateTime)
    last_creation_date: Mapped[date | None] = mapped_column(Date)
    query_checksum: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    run: Mapped[SyncRun | None] = relationship("SyncRun")


class Alert(Base):
    """Alert emitted when a new establishment is detected."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sync_runs.id"), nullable=False)
    siret: Mapped[str] = mapped_column(String(14), ForeignKey("establishments.siret"), nullable=False)
    recipients: Mapped[list[str]] = mapped_column(JSONB, default=list)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    run: Mapped[SyncRun] = relationship("SyncRun", back_populates="alerts")
    establishment: Mapped[Establishment] = relationship("Establishment", back_populates="alerts")


class Client(Base):
    """Client configuration owning email recipients for alerting."""

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    listing_statuses: Mapped[list[str]] = mapped_column(
        JSONB,
        default=_default_client_listing_statuses,
        nullable=False,
    )
    emails_sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    recipients: Mapped[list["ClientRecipient"]] = relationship(
        "ClientRecipient",
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="ClientRecipient.email",
    )
    subscriptions: Mapped[list["ClientSubscription"]] = relationship(
        "ClientSubscription",
        back_populates="client",
        cascade="all, delete-orphan",
        single_parent=True,
    )


class ClientRecipient(Base):
    """Email address associated with a client."""

    __tablename__ = "client_recipients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    client: Mapped[Client] = relationship("Client", back_populates="recipients")


class NafCategory(Base):
    """High-level grouping for NAF subcategories and pricing."""

    __tablename__ = "naf_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    subcategories: Mapped[list["NafSubCategory"]] = relationship(
        "NafSubCategory",
        back_populates="category",
        order_by="NafSubCategory.naf_code",
    )


class NafSubCategory(Base):
    """Leaf NAF code entry attached to a category with pricing."""

    __tablename__ = "naf_subcategories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("naf_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    naf_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    category: Mapped[NafCategory] = relationship("NafCategory", back_populates="subcategories")
    subscriptions: Mapped[list["ClientSubscription"]] = relationship(
        "ClientSubscription",
        back_populates="subcategory",
    )


class ClientSubscription(Base):
    """Association table linking clients to the NAF subcategories they subscribe to."""

    __tablename__ = "client_subscriptions"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subcategory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("naf_subcategories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    client: Mapped[Client] = relationship("Client", back_populates="subscriptions")
    subcategory: Mapped[NafSubCategory] = relationship("NafSubCategory", back_populates="subscriptions")


class AdminRecipient(Base):
    """Administrative email recipient for run summaries."""

    __tablename__ = "admin_recipients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class GoogleRetryConfig(Base):
    """Persisted configuration for Google Places retry strategy."""

    __tablename__ = "google_retry_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    retry_weekdays: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    default_rules: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list, nullable=False)
    micro_rules: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list, nullable=False)
    micro_company_categories: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    micro_legal_categories: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

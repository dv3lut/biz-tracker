import type { FormEvent, ChangeEvent } from "react";

import type { GoogleCheckResult } from "../types";
import { formatDateTime, formatPercent } from "../utils/format";

const STATUS_LABELS: Record<string, string> = {
  found: "Fiche trouvée",
  not_found: "Aucune fiche",
  insufficient: "Identité insuffisante",
  pending: "En attente",
  type_mismatch: "Catégorie incompatible",
};

const STATUS_TONES: Record<string, "success" | "danger" | "warning" | "info"> = {
  found: "success",
  not_found: "danger",
  insufficient: "warning",
  pending: "info",
  type_mismatch: "warning",
};

const LISTING_AGE_LABELS: Record<string, string> = {
  recent_creation: "Création récente",
  not_recent_creation: "Création ancienne",
  buyback_suspected: "Création ancienne",
  unknown: "Âge inconnu",
};

const LISTING_ORIGIN_LABELS: Record<string, string> = {
  opening_period: "Horaires Google",
  review: "Avis clients",
  assumed_recent: "Activité récente supposée",
  unknown: "Source inconnue",
};

const formatStatusLabel = (status: string | null | undefined): string | null => {
  if (!status) {
    return null;
  }
  return STATUS_LABELS[status] ?? status.replace(/_/g, " ").trim();
};

const formatStatusTone = (status: string | null | undefined): "success" | "danger" | "warning" | "info" => {
  if (!status) {
    return "info";
  }
  return STATUS_TONES[status] ?? "info";
};

const formatListingAgeStatus = (value: string | null | undefined): string => {
  if (!value) {
    return "—";
  }
  return LISTING_AGE_LABELS[value] ?? value.replace(/_/g, " ").trim();
};

const formatListingOriginSource = (value: string | null | undefined): string => {
  if (!value) {
    return "—";
  }
  return LISTING_ORIGIN_LABELS[value] ?? value.replace(/_/g, " ").trim();
};

type ManualGoogleCheckCardProps = {
  siret: string;
  onSiretChange: (value: string) => void;
  onSubmit: (siret: string) => void;
  notify: boolean;
  onNotifyChange: (value: boolean) => void;
  isSubmitting: boolean;
  isGlobalSubmitting: boolean;
  checkingGoogleSiret: string | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  result: GoogleCheckResult | null;
};

export const ManualGoogleCheckCard = ({
  siret,
  onSiretChange,
  onSubmit,
  notify,
  onNotifyChange,
  isSubmitting,
  isGlobalSubmitting,
  checkingGoogleSiret,
  feedbackMessage,
  errorMessage,
  result,
}: ManualGoogleCheckCardProps) => {
  const normalizedSiret = siret.replace(/\s+/g, "");
  const isCurrentSiretProcessing =
    Boolean(checkingGoogleSiret) && normalizedSiret.length === 14 && checkingGoogleSiret === normalizedSiret;
  const currentEstablishment = result?.establishment ?? null;
  const status = currentEstablishment?.googleCheckStatus ?? result?.checkStatus ?? null;
  const statusLabel = formatStatusLabel(status);
  const statusTone = formatStatusTone(status);

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value.replace(/[^0-9\s]/g, "");
    onSiretChange(value);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isGlobalSubmitting || normalizedSiret.length !== 14) {
      return;
    }
    onSubmit(siret);
  };

  const isButtonDisabled = isGlobalSubmitting || normalizedSiret.length !== 14;

  return (
    <section className="card manual-google-check-card">
      <header className="card-header">
        <div>
          <h2>Relancer un check Google</h2>
          <p className="muted">
            Relancez une vérification Google pour un SIRET précis et décidez si l&apos;équipe admin reçoit un e-mail lorsque
            la fiche est retrouvée.
          </p>
        </div>
      </header>

      {feedbackMessage ? <p className="feedback success">{feedbackMessage}</p> : null}
      {errorMessage ? <p className="feedback error">{errorMessage}</p> : null}
      {isSubmitting && isCurrentSiretProcessing ? (
        <p className="refresh-indicator">Relance en cours pour le SIRET {normalizedSiret}…</p>
      ) : null}

      <form className="manual-google-form" onSubmit={handleSubmit}>
        <div className="manual-google-form-row">
          <label htmlFor="manual-google-siret" className="manual-google-label">
            Numéro de SIRET
          </label>
          <input
            id="manual-google-siret"
            type="text"
            inputMode="numeric"
            autoComplete="off"
            placeholder="123 456 789 01234"
            maxLength={17}
            value={siret}
            onChange={handleInputChange}
            disabled={isGlobalSubmitting}
            className="manual-google-input"
            aria-label="Numéro de SIRET à vérifier"
          />
        </div>
        <div className="manual-google-form-row manual-google-form-row--actions">
          <label className="form-checkbox">
            <input
              type="checkbox"
              checked={notify}
              onChange={(event) => onNotifyChange(event.target.checked)}
              disabled={isGlobalSubmitting}
            />
            <span>Notifier les administrateurs si une fiche est trouvée</span>
          </label>
          <button type="submit" className="primary" disabled={isButtonDisabled}>
            {isSubmitting && isCurrentSiretProcessing ? "Relance en cours…" : "Relancer"}
          </button>
        </div>
        <p className="manual-google-form-note">
          <span className="muted small">14 chiffres requis. Les notifications s&apos;adressent uniquement aux e-mails admin, jamais aux clients.</span>
        </p>
      </form>

      <div className="manual-google-result">
        <div className="manual-google-result-header">
          <div>
            <h3>Dernier résultat</h3>
            <p className="muted small">
              {result && currentEstablishment
                ? `Mise à jour ${formatDateTime(currentEstablishment.googleLastCheckedAt)}`
                : "Lancez une vérification pour afficher le détail ici."}
            </p>
          </div>
          {statusLabel ? <span className={`status-chip status-chip--${statusTone}`}>{statusLabel}</span> : null}
        </div>

        {result && currentEstablishment ? (
          <>
            <div className="manual-google-meta">
              <div>
                <p className="muted small">Établissement</p>
                <p className="manual-google-meta-value">{currentEstablishment.name ?? "—"}</p>
              </div>
              <div>
                <p className="muted small">SIRET</p>
                <p className="manual-google-meta-value">{currentEstablishment.siret}</p>
              </div>
              <div>
                <p className="muted small">Code NAF</p>
                <p className="manual-google-meta-value">{currentEstablishment.nafCode ?? "—"}</p>
              </div>
            </div>

            <dl className="data-grid manual-google-data-grid">
              <div>
                <dt>Score de confiance</dt>
                <dd>{formatPercent(currentEstablishment.googleMatchConfidence)}</dd>
              </div>
              <div>
                <dt>Dernier check</dt>
                <dd>{formatDateTime(currentEstablishment.googleLastCheckedAt)}</dd>
              </div>
              <div>
                <dt>Dernière détection</dt>
                <dd>{formatDateTime(currentEstablishment.googleLastFoundAt)}</dd>
              </div>
              <div>
                <dt>Âge de la fiche</dt>
                <dd>{formatListingAgeStatus(currentEstablishment.googleListingAgeStatus)}</dd>
              </div>
              <div>
                <dt>Source d'origine</dt>
                <dd>{formatListingOriginSource(currentEstablishment.googleListingOriginSource)}</dd>
              </div>
              <div>
                <dt>Code postal</dt>
                <dd>{currentEstablishment.codePostal ?? "—"}</dd>
              </div>
              <div>
                <dt>Commune</dt>
                <dd>{currentEstablishment.libelleCommune ?? "—"}</dd>
              </div>
              <div>
                <dt>Place ID</dt>
                <dd>{result.placeId ?? "—"}</dd>
              </div>
            </dl>

            <div className="manual-google-links">
              {result.placeUrl ? (
                <a className="manual-google-link" href={result.placeUrl} target="_blank" rel="noreferrer">
                  Ouvrir la fiche Google
                </a>
              ) : (
                <p className="muted small">Aucune URL publique fournie par Google.</p>
              )}
            </div>
          </>
        ) : (
          <p className="muted small">Aucun résultat récent à afficher.</p>
        )}
      </div>
    </section>
  );
};

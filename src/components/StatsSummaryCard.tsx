import { type ReactNode } from "react";

import { StatsSummary, SyncRun } from "../types";
import { formatDateTime, formatNumber, formatPercent, formatDuration } from "../utils/format";
import { computeGoogleProgress, computeSireneProgress } from "../utils/progress";
import {
  describeDayReplayReference,
  describeSyncMode,
  formatNafCodesPreview,
  syncModeIsGoogleOnly,
  syncModeSupportsSirene,
} from "../utils/sync";
import { ProgressBar } from "./ProgressBar";
import { RunModeBadges } from "./RunModeBadges";

type Props = {
  summary?: StatsSummary;
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
  onTriggerSync: () => void;
  isTriggering: boolean;
  onOpenGoogleExportModal: () => void;
  isExportingGooglePlaces: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
  isRefreshing: boolean;
};

const renderRunDetails = (run: SyncRun | null): ReactNode => {
  if (!run) {
    return <p className="muted">Aucune exécution enregistrée.</p>;
  }

  const sireneProgress = computeSireneProgress(run);
  const googleProgress = computeGoogleProgress(run);
  const googleDisabled = !run.googleEnabled;
  const sireneEnabled = syncModeSupportsSirene(run.mode);
  const isGoogleOnly = syncModeIsGoogleOnly(run.mode);
  const sireneDetails = sireneProgress.total
    ? `${formatNumber(sireneProgress.processed)} / ${formatNumber(sireneProgress.total)} établissements traités`
    : `${formatNumber(sireneProgress.processed)} établissements traités (total inconnu)`;
  const hasGoogleWork =
    !googleDisabled && (googleProgress.total !== null || run.googleQueueCount > 0 || run.googleEligibleCount > 0);
  const googleDetailParts: string[] = [];
  if (googleProgress.total !== null) {
    googleDetailParts.push(
      `${formatNumber(googleProgress.processed)} / ${formatNumber(googleProgress.total)} fiches traitées`,
    );
  } else {
    googleDetailParts.push(
      run.status === "running" ? "Traitement en cours (volume inconnu)" : "Aucune fiche Google à traiter",
    );
  }
  if (googleProgress.pending > 0) {
    googleDetailParts.push(`Restant: ${formatNumber(googleProgress.pending)}`);
  }

  return (
    <>
      <RunModeBadges
        run={{
          mode: run.mode,
          targetNafCodes: run.targetNafCodes,
          targetClientIds: run.targetClientIds,
          notifyAdmins: run.notifyAdmins,
          dayReplayForceGoogle: run.dayReplayForceGoogle,
          dayReplayReference: run.dayReplayReference,
        }}
        className="mb-1"
      />
      <div className="progress-bars">
        {sireneEnabled ? (
          <ProgressBar
            label="Avancement Sirene"
            value={sireneProgress.value}
            details={<span>{sireneDetails}</span>}
          />
        ) : (
          <p className="muted small">Run Google uniquement : aucune collecte Sirene n'a été effectuée.</p>
        )}
        {hasGoogleWork ? (
          <ProgressBar
            label="Appels Google"
            tone="success"
            value={googleProgress.value}
            details={<span>{googleDetailParts.join(" · ")}</span>}
          />
        ) : googleDisabled ? (
          <p className="muted small">Google Places désactivé pour ce run.</p>
        ) : null}
      </div>
      <dl className="data-grid">
        <div>
          <dt>Mode</dt>
          <dd>{describeSyncMode(run.mode)}</dd>
        </div>
        <div>
          <dt>Ciblage NAF</dt>
          <dd>{formatNafCodesPreview(run.targetNafCodes, 6)}</dd>
        </div>
        <div>
          <dt>Google Places</dt>
          <dd>{run.googleEnabled ? "Activé" : "Désactivé"}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{run.runType}</dd>
        </div>
        {run.mode === "day_replay" ? (
          <div>
            <dt>Référence rejeu</dt>
            <dd>{describeDayReplayReference(run.dayReplayReference)}</dd>
          </div>
        ) : null}
        <div>
          <dt>Status</dt>
          <dd>{run.status}</dd>
        </div>
      <div>
        <dt>Démarrée</dt>
        <dd>{formatDateTime(run.startedAt)}</dd>
      </div>
      <div>
        <dt>Terminée</dt>
        <dd>{formatDateTime(run.finishedAt)}</dd>
      </div>
      <div>
        <dt>Progression</dt>
        <dd>{formatPercent(run.progress)}</dd>
      </div>
      <div>
        <dt>Enregistrements traités</dt>
        <dd>{formatNumber(run.fetchedRecords)}</dd>
      </div>
      <div>
        <dt>Nouveaux établissements</dt>
        <dd>{formatNumber(run.createdRecords)}</dd>
      </div>
      <div>
        <dt>File Google totale</dt>
        <dd>{formatNumber(run.googleQueueCount)}</dd>
      </div>
      <div>
        <dt>Eligibles Google</dt>
        <dd>{formatNumber(run.googleEligibleCount)}</dd>
      </div>
      <div>
        <dt>Fiches Google trouvées</dt>
        <dd>{formatNumber(run.googleMatchedCount)}</dd>
      </div>
      <div>
        <dt>Reste à trouver</dt>
        <dd>{formatNumber(run.googlePendingCount)}</dd>
      </div>
      <div>
        <dt>Appels API</dt>
        <dd>{formatNumber(run.apiCallCount)}</dd>
      </div>
      <div>
        <dt>Appels Google</dt>
        <dd>{formatNumber(run.googleApiCallCount)}</dd>
      </div>
      <div>
        <dt>Restant estimé</dt>
        <dd>{formatDuration(run.estimatedRemainingSeconds)}</dd>
      </div>
      <div>
        <dt>ETA</dt>
        <dd>{formatDateTime(run.estimatedCompletionAt)}</dd>
      </div>
      <div>
        <dt>Total attendu</dt>
        <dd>{formatNumber(run.totalExpectedRecords)}</dd>
      </div>
      <div>
        <dt>Run repris</dt>
        <dd>{run.resumedFromRunId ?? "—"}</dd>
      </div>
      <div>
        <dt>Notes</dt>
        <dd>{run.notes ?? "—"}</dd>
      </div>
        {isGoogleOnly ? (
          <div>
            <dt>Observation</dt>
            <dd>Ce run n'a pas interrogé l'API Sirene.</dd>
          </div>
        ) : null}
      </dl>
    </>
  );
};

export const StatsSummaryCard = ({
  summary,
  isLoading,
  error,
  onRefresh,
  onTriggerSync,
  isTriggering,
  onOpenGoogleExportModal,
  isExportingGooglePlaces,
  feedbackMessage,
  errorMessage,
  isRefreshing,
}: Props) => (
  <section className="card">
    <header className="card-header">
      <div>
        <h2>Statistiques globales</h2>
        <p className="muted">Synthèse des traitements récents et déclenchement direct d'une nouvelle synchro.</p>
      </div>
      <div className="card-actions">
        <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
          Rafraîchir
        </button>
        <button
          type="button"
          className="ghost"
          onClick={onOpenGoogleExportModal}
          disabled={isExportingGooglePlaces}
          title="Télécharger un export Excel des fiches Google détectées"
        >
          {isExportingGooglePlaces ? "Export..." : "Exporter Google Places"}
        </button>
        <button
          type="button"
          className="primary"
          onClick={onTriggerSync}
          disabled={isTriggering}
          title="Choisir entre une synchro complète ou Sirene uniquement"
        >
          {isTriggering ? "Déclenchement..." : "Lancer une synchro"}
        </button>
      </div>
    </header>

    {feedbackMessage && <p className="feedback success">{feedbackMessage}</p>}
    {errorMessage && <p className="feedback error">{errorMessage}</p>}
  {isRefreshing && !isLoading && <p className="refresh-indicator">Actualisation en cours…</p>}

    {isLoading && <p>Chargement...</p>}
    {error && <p className="error">{error.message}</p>}

    {summary && !isLoading && !error && (
      <div className="summary-grid">
        <article>
          <h3>Etablissements indexés</h3>
          <p className="big">{formatNumber(summary.totalEstablishments)}</p>
        </article>
        <article>
          <h3>Alertes générées</h3>
          <p className="big">{formatNumber(summary.totalAlerts)}</p>
        </article>
        {summary.databaseSizePretty ? (
          <article>
            <h3>Taille base</h3>
            <p className="big">{summary.databaseSizePretty}</p>
          </article>
        ) : null}
        <article>
          <h3>Dernière alerte</h3>
          <p>{formatDateTime(summary.lastAlert?.createdAt ?? null)}</p>
          {summary.lastAlert && (
            <p className="muted small">Destinataires: {summary.lastAlert.recipients.join(", ") || "—"}</p>
          )}
        </article>
      </div>
    )}

    {summary && !isLoading && !error && (
      <div className="split">
        <article>
          <h3>Dernière synchronisation</h3>
          {renderRunDetails(summary.lastRun)}
        </article>
      </div>
    )}
  </section>
);

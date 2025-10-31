import { type ReactNode } from "react";

import { StatsSummary, SyncRun } from "../types";
import { formatDateTime, formatNumber, formatPercent, formatDuration } from "../utils/format";

type Props = {
  summary?: StatsSummary;
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
};

const renderRunDetails = (run: SyncRun | null): ReactNode => {
  if (!run) {
    return <p className="muted">Aucune exécution enregistrée.</p>;
  }

  return (
    <dl className="data-grid">
      <div>
        <dt>Type</dt>
        <dd>{run.runType}</dd>
      </div>
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
        <dt>Enregistrements créés</dt>
        <dd>{formatNumber(run.createdRecords)}</dd>
      </div>
      <div>
        <dt>Appels API</dt>
        <dd>{formatNumber(run.apiCallCount)}</dd>
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
        <dt>Max autorisé</dt>
        <dd>{formatNumber(run.maxRecords)}</dd>
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
        <dt>Dernier curseur</dt>
        <dd>{run.lastCursor ?? "—"}</dd>
      </div>
      <div>
        <dt>Notes</dt>
        <dd>{run.notes ?? "—"}</dd>
      </div>
    </dl>
  );
};

export const StatsSummaryCard = ({ summary, isLoading, error, onRefresh }: Props) => (
  <section className="card">
    <header className="card-header">
      <div>
        <h2>Statistiques globales</h2>
        <p className="muted">Synthèse des traitements récents côté API.</p>
      </div>
      <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
        Rafraîchir
      </button>
    </header>

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
          <h3>Dernière synchro complète</h3>
          {renderRunDetails(summary.lastFullRun)}
        </article>
        <article>
          <h3>Dernière synchro incrémentale</h3>
          {renderRunDetails(summary.lastIncrementalRun)}
        </article>
      </div>
    )}
  </section>
);

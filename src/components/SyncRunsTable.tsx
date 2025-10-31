import { ChangeEvent } from "react";

import { SyncRun } from "../types";
import { formatDateTime, formatNumber, formatPercent, formatDuration } from "../utils/format";

type Props = {
  runs?: SyncRun[];
  isLoading: boolean;
  error: Error | null;
  limit: number;
  onLimitChange: (limit: number) => void;
  onRefresh: () => void;
};

const truncate = (value: string | null, length = 16): string => {
  if (!value) {
    return "—";
  }
  if (value.length <= length) {
    return value;
  }
  return `${value.slice(0, length)}...`;
};

export const SyncRunsTable = ({ runs, isLoading, error, limit, onLimitChange, onRefresh }: Props) => {
  const handleLimitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onLimitChange(Number(event.target.value));
  };

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Historique des synchronisations</h2>
          <p className="muted">Dernières exécutions des traitements batch.</p>
        </div>
        <div className="actions">
          <label className="muted small">
            Lignes
            <select value={limit} onChange={handleLimitChange}>
              {[10, 20, 50, 100, 200].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Rafraîchir
          </button>
        </div>
      </header>

      {isLoading && <p>Chargement...</p>}
      {error && <p className="error">{error.message}</p>}

      {!isLoading && !error && runs && runs.length === 0 && <p className="muted">Aucune exécution à afficher.</p>}

      {!isLoading && !error && runs && runs.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Début</th>
                <th>Type</th>
                <th>Status</th>
                <th>Progression</th>
                <th>Volumes</th>
                <th>Paramètres</th>
                <th>Temps</th>
                <th>Détails</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>
                    <span className="small muted">{run.scopeKey}</span>
                    <br />
                    {formatDateTime(run.startedAt)}
                  </td>
                  <td>{run.runType}</td>
                  <td>
                    <span className={`badge status-${run.status}`}>{run.status}</span>
                  </td>
                  <td>{formatPercent(run.progress)}</td>
                  <td>
                    <strong>{formatNumber(run.fetchedRecords)}</strong>
                    <br />
                    <span className="small muted">Créés: {formatNumber(run.createdRecords)}</span>
                    <br />
                    <span className="small muted">Appels API: {formatNumber(run.apiCallCount)}</span>
                  </td>
                  <td>
                    <span className="small muted">Attendu: {formatNumber(run.totalExpectedRecords)}</span>
                    <br />
                    <span className="small muted">Max autorisé: {formatNumber(run.maxRecords)}</span>
                    <br />
                    <span className="small muted">
                      Reprise depuis: {run.resumedFromRunId ? truncate(run.resumedFromRunId) : "—"}
                    </span>
                  </td>
                  <td>
                    {formatDuration(run.estimatedRemainingSeconds)}
                    <br />
                    <span className="small muted">Fin estimée: {formatDateTime(run.estimatedCompletionAt)}</span>
                    <br />
                    <span className="small muted">Terminée: {formatDateTime(run.finishedAt)}</span>
                  </td>
                  <td>
                    {run.notes ? <span>{run.notes}</span> : <span className="muted">—</span>}
                    <br />
                    <span className="small muted">Curseur: {truncate(run.lastCursor)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

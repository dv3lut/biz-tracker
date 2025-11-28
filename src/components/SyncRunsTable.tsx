import { ChangeEvent } from "react";

import { SyncRun } from "../types";
import { formatDateTime, formatNumber, formatDuration } from "../utils/format";
import { computeGoogleProgress, computeSireneProgress } from "../utils/progress";
import { ProgressBar } from "./ProgressBar";
import { RunModeBadges } from "./RunModeBadges";
import { describeSyncMode, formatNafCodesPreview, syncModeSupportsSirene } from "../utils/sync";

type Props = {
  runs?: SyncRun[];
  isLoading: boolean;
  error: Error | null;
  limit: number;
  onLimitChange: (limit: number) => void;
  onRefresh: () => void;
  onDeleteRun: (runId: string) => void;
  deletingRunId: string | null;
  isDeletingRun: boolean;
  isRefreshing: boolean;
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

export const SyncRunsTable = ({
  runs,
  isLoading,
  error,
  limit,
  onLimitChange,
  onRefresh,
  onDeleteRun,
  deletingRunId,
  isDeletingRun,
  isRefreshing,
}: Props) => {
  const handleLimitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onLimitChange(Number(event.target.value));
  };

  const handleDeleteRun = (runId: string) => {
    const confirmed = window.confirm(
      "Supprimer ce run et toutes les données associées (établissements, alertes) ?"
    );
    if (confirmed) {
      onDeleteRun(runId);
    }
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
  {isRefreshing && !isLoading && <p className="refresh-indicator">Actualisation en cours…</p>}

      {!isLoading && !error && runs && runs.length === 0 && <p className="muted">Aucune exécution à afficher.</p>}

      {!isLoading && !error && runs && runs.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Progression</th>
                <th>Durées</th>
                <th>Détails</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const sirene = computeSireneProgress(run);
                const google = computeGoogleProgress(run);
                const showGoogle =
                  run.googleEnabled && (google.total !== null || run.googleQueueCount > 0 || run.googleEligibleCount > 0);
                const sireneEnabled = syncModeSupportsSirene(run.mode);

                return (
                  <tr key={run.id}>
                    <td>
                      <strong>{formatDateTime(run.startedAt)}</strong>
                      <br />
                      <span className="small muted">Scope: {run.scopeKey}</span>
                      <br />
                      <span className="small muted">Type: {run.runType}</span>
                      <br />
                      <span className="small muted">Mode: {describeSyncMode(run.mode)}</span>
                      <RunModeBadges run={{ mode: run.mode, targetNafCodes: run.targetNafCodes }} />
                      <br />
                      <span className="small muted">
                        Google: {run.googleEnabled ? "Activé" : "Désactivé"}
                      </span>
                      {run.resumedFromRunId ? (
                        <>
                          <br />
                          <span className="small muted">Reprise: {truncate(run.resumedFromRunId, 20)}</span>
                        </>
                      ) : null}
                    </td>
                    <td>
                      <span className={`badge status-${run.status}`}>{run.status}</span>
                      <div className="table-progress">
                        {sireneEnabled ? (
                          <ProgressBar label="Sirene" value={sirene.value} />
                        ) : (
                          <span className="small muted">Google uniquement</span>
                        )}
                        {showGoogle ? (
                          <ProgressBar label="Google" tone="success" value={google.value} />
                        ) : !run.googleEnabled ? (
                          <span className="small muted">Google désactivé</span>
                        ) : null}
                      </div>
                      <span className="small muted">Traités: {formatNumber(run.fetchedRecords)}</span>
                      <br />
                      <span className="small muted">Nouveaux: {formatNumber(run.createdRecords)}</span>
                      <br />
                      <span className="small muted">Total attendu: {formatNumber(run.totalExpectedRecords)}</span>
                    </td>
                    <td>
                      <span className="small muted">Restant: {formatDuration(run.estimatedRemainingSeconds)}</span>
                      <br />
                      <span className="small muted">Fin estimée: {formatDateTime(run.estimatedCompletionAt)}</span>
                      <br />
                      <span className="small muted">Terminée: {formatDateTime(run.finishedAt)}</span>
                      <br />
                      <span className="small muted">Appels API: {formatNumber(run.apiCallCount)}</span>
                      <br />
                      <span className="small muted">Appels Google: {formatNumber(run.googleApiCallCount)}</span>
                    </td>
                    <td>
                      <span className="small muted">Google - File: {formatNumber(run.googleQueueCount)}</span>
                      <br />
                      <span className="small muted">Eligibles: {formatNumber(run.googleEligibleCount)}</span>
                      <br />
                      <span className="small muted">Trouvées: {formatNumber(run.googleMatchedCount)}</span>
                      <br />
                      <span className="small muted">Restant: {formatNumber(run.googlePendingCount)}</span>
                      <br />
                      <span className="small muted">Notes: {run.notes ? truncate(run.notes, 64) : "—"}</span>
                      <br />
                      <span className="small muted">NAF ciblées: {formatNafCodesPreview(run.targetNafCodes, 5)}</span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => handleDeleteRun(run.id)}
                        disabled={isDeletingRun && deletingRunId === run.id}
                      >
                        {isDeletingRun && deletingRunId === run.id ? "Suppression..." : "Supprimer les données"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

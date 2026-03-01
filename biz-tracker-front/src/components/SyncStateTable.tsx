import { SyncState } from "../types";
import { formatDateTime, formatNumber } from "../utils/format";

type Props = {
  states?: SyncState[];
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
  isRefreshing: boolean;
};

export const SyncStateTable = ({ states, isLoading, error, onRefresh, isRefreshing }: Props) => (
  <section className="card">
    <header className="card-header">
      <div>
        <h2>Etat des synchronisations</h2>
        <p className="muted">Vue consolidée par scope.</p>
      </div>
      <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
        Rafraîchir
      </button>
    </header>

    {isLoading && <p>Chargement...</p>}
    {error && <p className="error">{error.message}</p>}
    {isRefreshing && !isLoading && <p className="refresh-indicator">Actualisation en cours…</p>}

    {!isLoading && !error && states && states.length === 0 && <p className="muted">Aucun état de synchro disponible.</p>}

    {!isLoading && !error && states && states.length > 0 && (
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Scope</th>
              <th>Synchronisation</th>
              <th>Statut</th>
              <th>Volume</th>
            </tr>
          </thead>
          <tbody>
            {states.map((state) => (
              <tr key={state.scopeKey}>
                <td>
                  <strong>{state.scopeKey}</strong>
                  <br />
                  <span className="small muted">Run: {state.lastSuccessfulRunId ?? "—"}</span>
                </td>
                <td>
                  <span className="small muted">Dernière sync: {formatDateTime(state.lastSyncedAt)}</span>
                  <br />
                  <span className="small muted">MAJ: {formatDateTime(state.updatedAt)}</span>
                </td>
                <td>
                  <span className={`badge status-${state.cursorCompleted ? "done" : "pending"}`}>
                    {state.cursorCompleted ? "Terminé" : "En cours"}
                  </span>
                  <br />
                  <span className="small muted">Traité max: {formatDateTime(state.lastTreatedMax)}</span>
                </td>
                <td>
                  <span className="small muted">Total connu: {formatNumber(state.lastTotal)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </section>
);

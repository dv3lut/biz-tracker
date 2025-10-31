import { SyncState } from "../types";
import { formatDateTime, formatNumber } from "../utils/format";

type Props = {
  states?: SyncState[];
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
};

export const SyncStateTable = ({ states, isLoading, error, onRefresh }: Props) => (
  <section className="card">
    <header className="card-header">
      <div>
        <h2>Etat des curseurs</h2>
        <p className="muted">Progression détaillée par scope.</p>
      </div>
      <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
        Rafraîchir
      </button>
    </header>

    {isLoading && <p>Chargement...</p>}
    {error && <p className="error">{error.message}</p>}

    {!isLoading && !error && states && states.length === 0 && <p className="muted">Aucun état de synchro disponible.</p>}

    {!isLoading && !error && states && states.length > 0 && (
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Scope</th>
              <th>Dernier run</th>
              <th>Cursor</th>
              <th>Complété</th>
              <th>Dernière sync</th>
              <th>Total</th>
              <th>Checksum</th>
              <th>MAJ</th>
            </tr>
          </thead>
          <tbody>
            {states.map((state) => (
              <tr key={state.scopeKey}>
                <td>{state.scopeKey}</td>
                <td>{state.lastSuccessfulRunId ?? "—"}</td>
                <td>
                  {state.lastCursor ?? "—"}
                  <br />
                  <span className="small muted">Traité max: {formatDateTime(state.lastTreatedMax)}</span>
                </td>
                <td>
                  <span className={`badge status-${state.cursorCompleted ? "done" : "pending"}`}>
                    {state.cursorCompleted ? "Oui" : "Non"}
                  </span>
                </td>
                <td>{formatDateTime(state.lastSyncedAt)}</td>
                <td>{formatNumber(state.lastTotal)}</td>
                <td className="small">{state.queryChecksum ?? "—"}</td>
                <td>{formatDateTime(state.updatedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </section>
);

import { ChangeEvent } from "react";

import { Alert } from "../types";
import { formatDateTime } from "../utils/format";

type Props = {
  alerts?: Alert[];
  isLoading: boolean;
  error: Error | null;
  limit: number;
  onLimitChange: (limit: number) => void;
  onRefresh: () => void;
  onTriggerGoogleCheck: (siret: string) => void;
  isCheckingGoogle: boolean;
  checkingGoogleSiret: string | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onSelect: (siret: string) => void;
};

export const AlertsList = ({
  alerts,
  isLoading,
  error,
  limit,
  onLimitChange,
  onRefresh,
  onTriggerGoogleCheck,
  isCheckingGoogle,
  checkingGoogleSiret,
  feedbackMessage,
  errorMessage,
  onSelect,
}: Props) => {
  const handleLimitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onLimitChange(Number(event.target.value));
  };

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Alertes récentes</h2>
          <p className="muted">Dernières anomalies détectées par l'API.</p>
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

      {!isLoading && !error && alerts && alerts.length === 0 && <p className="muted">Aucune alerte récente.</p>}

      {!isLoading && !error && alerts && alerts.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Créée</th>
                <th>SIRET</th>
                <th>Destinataires</th>
                <th>Payload</th>
                <th>Envoyée</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr
                  key={alert.id}
                  className="clickable"
                  onClick={() => onSelect(alert.siret)}
                >
                  <td>{formatDateTime(alert.createdAt)}</td>
                  <td>{alert.siret}</td>
                  <td>{alert.recipients.join(", ") || "—"}</td>
                  <td>
                    <pre className="payload">{JSON.stringify(alert.payload, null, 2)}</pre>
                  </td>
                  <td>{formatDateTime(alert.sentAt)}</td>
                  <td>
                    <button
                      type="button"
                      className="ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        onTriggerGoogleCheck(alert.siret);
                      }}
                      disabled={isCheckingGoogle && checkingGoogleSiret === alert.siret}
                    >
                      {isCheckingGoogle && checkingGoogleSiret === alert.siret
                        ? "Vérification..."
                        : "Rechecker Google"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {feedbackMessage && <p className="feedback success">{feedbackMessage}</p>}
      {errorMessage && <p className="feedback error">{errorMessage}</p>}
    </section>
  );
};

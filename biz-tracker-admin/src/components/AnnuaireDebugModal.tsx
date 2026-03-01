import type { AnnuaireDebugResult } from "../types";

const buildPrettyPayload = (payload: AnnuaireDebugResult["payload"]): string => {
  if (!payload) {
    return "—";
  }
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
};

type Props = {
  siret: string;
  result: AnnuaireDebugResult;
  onClose: () => void;
};

export const AnnuaireDebugModal = ({ siret, result, onClose }: Props) => {
  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>Debug API Annuaire</h2>
            <p className="muted small">Établissement: {siret}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose} aria-label="Fermer">
            Fermer
          </button>
        </header>

        <div className="modal-content">
          <div className="card" style={{ marginBottom: 16 }}>
            <p className="muted small" style={{ marginBottom: 6 }}>
              Requête annuaire (SIREN {result.siren})
            </p>
            <p style={{ marginTop: 0 }}>
              <strong>{result.success ? "Succès" : "Échec"}</strong>
            </p>
            <p className="muted small">
              Statut HTTP: {result.statusCode ?? "—"} · Durée: {result.durationMs ?? "—"} ms
            </p>
            {result.error ? <p className="muted small">Erreur: {result.error}</p> : null}
          </div>

          <div className="card">
            <p className="muted small" style={{ marginBottom: 6 }}>
              Payload brut renvoyé par l'API annuaire
            </p>
            <pre className="muted small" style={{ whiteSpace: "pre-wrap" }}>
              {buildPrettyPayload(result.payload)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

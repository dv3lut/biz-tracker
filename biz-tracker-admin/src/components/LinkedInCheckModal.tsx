import type { LinkedInCheckResponse } from "../types";
import { formatDateTime } from "../utils/format";

type Props = {
  directorName: string;
  companyName: string | null;
  result: LinkedInCheckResponse;
  onClose: () => void;
};

export const LinkedInCheckModal = ({ directorName, companyName, result, onClose }: Props) => {
  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>Recherche LinkedIn</h2>
            <p className="muted small">Dirigeant : {directorName || "—"}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose} aria-label="Fermer">
            Fermer
          </button>
        </header>

        <div className="modal-content">
          <div className="card" style={{ marginBottom: 16 }}>
            <p className="muted small" style={{ marginBottom: 6 }}>
              Paramètres de recherche
            </p>
            <p style={{ marginTop: 0 }}>
              <strong>
                {[result.firstNames, result.lastName].filter(Boolean).join(" ") || "—"}
              </strong>
            </p>
            <p className="muted small">Entreprise : {companyName || result.companyName || "—"}</p>
            <p className="muted small">Dernier check : {formatDateTime(result.linkedinLastCheckedAt)}</p>
            <p className="muted small">Statut : {result.linkedinCheckStatus}</p>
            <p className="muted small">Message : {result.message || "—"}</p>
          </div>

          {result.linkedinProfileUrl ? (
            <p>
              <a href={result.linkedinProfileUrl} target="_blank" rel="noreferrer">
                Ouvrir le profil LinkedIn
              </a>
            </p>
          ) : null}

          <section>
            <h3>Données renvoyées</h3>
            <pre className="payload">{JSON.stringify(result.linkedinProfileData, null, 2)}</pre>
          </section>
        </div>
      </div>
    </div>
  );
};

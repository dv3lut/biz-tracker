import type { LinkedInDebugResponse } from "../types";

type Props = {
  directorName: string;
  result: LinkedInDebugResponse;
  onClose: () => void;
};

export const LinkedInDebugModal = ({ directorName, result, onClose }: Props) => {
  const searchSummary = [
    result.searchInput.firstName,
    result.searchInput.lastName,
    result.searchInput.company,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>Debug LinkedIn</h2>
            <p className="muted small">Dirigeant : {directorName || result.directorName || "—"}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose} aria-label="Fermer">
            Fermer
          </button>
        </header>

        <div className="modal-content">
          <div className="card" style={{ marginBottom: 16 }}>
            <p className="muted small" style={{ marginBottom: 6 }}>
              Paramètres Apify
            </p>
            <p style={{ marginTop: 0 }}>
              <strong>{searchSummary || "—"}</strong>
            </p>
            <p className="muted small">Entreprise : {result.companyName || "—"}</p>
            <p className="muted small">Statut : {result.status}</p>
            <p className="muted small">Relance avec unité légale : {result.retriedWithLegalUnit ? "Oui" : "Non"}</p>
            {result.error ? <p className="muted small">Erreur : {result.error}</p> : null}
          </div>

          {result.profileUrl ? (
            <p>
              <a href={result.profileUrl} target="_blank" rel="noreferrer">
                Ouvrir le profil LinkedIn
              </a>
            </p>
          ) : null}

          <section>
            <h3>Réponse Apify</h3>
            <pre className="payload">{JSON.stringify(result.apifyResponse, null, 2)}</pre>
          </section>

          <section>
            <h3>Données profil</h3>
            <pre className="payload">{JSON.stringify(result.profileData, null, 2)}</pre>
          </section>
        </div>
      </div>
    </div>
  );
};

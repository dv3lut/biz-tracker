import type { GoogleFindPlaceDebugResult } from "../types";

type Props = {
  siret: string;
  result: GoogleFindPlaceDebugResult;
  onClose: () => void;
};

export const GoogleFindPlaceDebugModal = ({ siret, result, onClose }: Props) => {
  const searchUrl = result.query ? `https://www.google.com/search?q=${encodeURIComponent(result.query)}` : null;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>Debug Google Find Place</h2>
            <p className="muted small">Établissement: {siret}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose} aria-label="Fermer">
            Fermer
          </button>
        </header>

        <div className="modal-content">
          <div className="card" style={{ marginBottom: 16 }}>
            <p className="muted small" style={{ marginBottom: 6 }}>
              Requête envoyée à Google Places (Find Place)
            </p>
            <p style={{ marginTop: 0 }}>
              <strong>{result.query || "—"}</strong>
            </p>
            <p className="muted small">Candidats renvoyés: {result.candidateCount}</p>
            {searchUrl ? (
              <a className="small" href={searchUrl} target="_blank" rel="noreferrer">
                Ouvrir la recherche Google dans un nouvel onglet
              </a>
            ) : null}
          </div>

          {result.candidates.length === 0 ? (
            <p className="muted">Aucun candidat renvoyé par Google Places.</p>
          ) : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Nom</th>
                    <th>Adresse</th>
                    <th>Score</th>
                    <th>Décision</th>
                    <th>Place ID</th>
                  </tr>
                </thead>
                <tbody>
                  {result.candidates.map((candidate, index) => (
                    <tr key={`${candidate.placeId ?? "unknown"}-${index}`}>
                      <td>{candidate.name || "—"}</td>
                      <td className="muted small">{candidate.formattedAddress || "—"}</td>
                      <td>{candidate.matchScore != null ? candidate.matchScore.toFixed(3) : "—"}</td>
                      <td>{candidate.decision || "—"}</td>
                      <td className="muted small">{candidate.placeId || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="muted small" style={{ marginTop: 12 }}>
            Note: ce debug montre uniquement Find Place + scoring interne (avant Place Details).
          </p>
        </div>
      </div>
    </div>
  );
};

import { ChangeEvent } from "react";

import { Establishment } from "../types";
import { formatDateTime } from "../utils/format";

interface EstablishmentsSectionProps {
  establishments?: Establishment[];
  isLoading: boolean;
  error: Error | null;
  limit: number;
  page: number;
  query: string;
  hasNextPage: boolean;
  onLimitChange: (limit: number) => void;
  onPageChange: (page: number) => void;
  onQueryChange: (query: string) => void;
  onRefresh: () => void;
  onDeleteEstablishment: (siret: string) => void;
  deletingSiret: string | null;
  isDeletingOne: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onTriggerGoogleCheck: (siret: string) => void;
  isCheckingGoogle: boolean;
  checkingGoogleSiret: string | null;
  onSelectEstablishment: (siret: string) => void;
}

export const EstablishmentsSection = ({
  establishments,
  isLoading,
  error,
  limit,
  page,
  query,
  hasNextPage,
  onLimitChange,
  onPageChange,
  onQueryChange,
  onRefresh,
  onDeleteEstablishment,
  deletingSiret,
  isDeletingOne,
  feedbackMessage,
  errorMessage,
  onTriggerGoogleCheck,
  isCheckingGoogle,
  checkingGoogleSiret,
  onSelectEstablishment,
}: EstablishmentsSectionProps) => {
  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    onQueryChange(event.target.value);
  };

  const handleLimitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onLimitChange(Number(event.target.value));
  };

  const handleDeleteOne = (siret: string) => {
    const confirmed = window.confirm(`Supprimer l'établissement ${siret} ? Cette action est irréversible.`);
    if (confirmed) {
      onDeleteEstablishment(siret);
    }
  };

  const formatRunId = (value: string | null) => {
    if (!value) {
      return "—";
    }
    return `${value.slice(0, 8)}…`;
  };

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Gestion des établissements</h2>
          <p className="muted">Rechercher, inspecter et purger les établissements synchronisés.</p>
        </div>
        <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
          Rafraîchir
        </button>
      </header>

      <div className="establishments-controls">
        <input
          type="search"
          value={query}
          onChange={handleSearchChange}
          placeholder="Filtrer par SIRET, nom ou code postal"
        />
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
        <div className="establishments-pagination">
          <button type="button" className="ghost" onClick={() => onPageChange(Math.max(0, page - 1))} disabled={page === 0 || isLoading}>
            Page précédente
          </button>
          <span className="small muted">Page {page + 1}</span>
          <button
            type="button"
            className="ghost"
            onClick={() => onPageChange(page + 1)}
            disabled={!hasNextPage || isLoading}
          >
            Page suivante
          </button>
        </div>
      </div>

      {isLoading && <p>Chargement...</p>}
      {error && <p className="error">{error.message}</p>}

      {!isLoading && !error && establishments && establishments.length === 0 && (
        <p className="muted">Aucun établissement trouvé pour ces critères.</p>
      )}

      {!isLoading && !error && establishments && establishments.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>SIRET</th>
                <th>Nom</th>
                <th>Localisation</th>
                <th>Dates</th>
                <th>Synchronisations</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {establishments.map((establishment) => (
                <tr
                  key={establishment.siret}
                  className="clickable"
                  onClick={() => onSelectEstablishment(establishment.siret)}
                >
                  <td>
                    <strong>{establishment.siret}</strong>
                    <br />
                    <span className="small muted">SIREN: {establishment.siren}</span>
                  </td>
                  <td>
                    {establishment.name || "—"}
                    <br />
                    <span className="small muted">
                      NAF: {establishment.nafCode ?? "—"} {establishment.nafLibelle ? `(${establishment.nafLibelle})` : ""}
                    </span>
                  </td>
                  <td>
                    {establishment.codePostal ?? "—"} {establishment.libelleCommune ?? ""}
                    <br />
                    <span className="small muted">Etat: {establishment.etatAdministratif ?? "—"}</span>
                  </td>
                  <td>
                    <span className="small muted">Création: {establishment.dateCreation ?? "—"}</span>
                    <br />
                    <span className="small muted">Début activité: {establishment.dateDebutActivite ?? "—"}</span>
                    <br />
                    <span className="small muted">Première vue: {formatDateTime(establishment.firstSeenAt)}</span>
                    <br />
                    <span className="small muted">Dernière vue: {formatDateTime(establishment.lastSeenAt)}</span>
                  </td>
                  <td>
                    <span className="small muted">Créé par: {formatRunId(establishment.createdRunId)}</span>
                    <br />
                    <span className="small muted">Dernier run: {formatRunId(establishment.lastRunId)}</span>
                    <br />
                    <span className="small muted">
                      Google: {establishment.googleCheckStatus}
                      {establishment.googleLastCheckedAt ? ` (checké le ${formatDateTime(establishment.googleLastCheckedAt)})` : ""}
                    </span>
                    <br />
                    <span className="small muted">
                      Dernière détection: {establishment.googleLastFoundAt ? formatDateTime(establishment.googleLastFoundAt) : "—"}
                    </span>
                    {establishment.googlePlaceId && (
                      <>
                        <br />
                        <span className="small muted">Place ID: {establishment.googlePlaceId}</span>
                      </>
                    )}
                    {establishment.googlePlaceUrl && (
                      <>
                        <br />
                        <a className="small" href={establishment.googlePlaceUrl} target="_blank" rel="noreferrer">
                          Ouvrir la page Google
                        </a>
                      </>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        onTriggerGoogleCheck(establishment.siret);
                      }}
                      disabled={isCheckingGoogle && checkingGoogleSiret === establishment.siret}
                    >
                      {isCheckingGoogle && checkingGoogleSiret === establishment.siret
                        ? "Vérification..."
                        : "Rechecker Google"}
                    </button>
                    <br />
                    <button
                      type="button"
                      className="ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleDeleteOne(establishment.siret);
                      }}
                      disabled={isDeletingOne && deletingSiret === establishment.siret}
                    >
                      {isDeletingOne && deletingSiret === establishment.siret ? "Suppression..." : "Supprimer"}
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

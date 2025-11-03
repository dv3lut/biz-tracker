import { ChangeEvent, FormEvent, useEffect, useState } from "react";

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
  onDeleteAll: (confirmPhrase: string) => void;
  deletingSiret: string | null;
  isDeletingOne: boolean;
  isDeletingAll: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
}

const DELETE_ALL_PHRASE = "DELETE ALL ESTABLISHMENTS";

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
  onDeleteAll,
  deletingSiret,
  isDeletingOne,
  isDeletingAll,
  feedbackMessage,
  errorMessage,
}: EstablishmentsSectionProps) => {
  const [confirmPhrase, setConfirmPhrase] = useState("");

  useEffect(() => {
    if (feedbackMessage) {
      setConfirmPhrase("");
    }
  }, [feedbackMessage]);

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

  const handleDeleteAll = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onDeleteAll(confirmPhrase);
  };

  const disableDeleteAll = confirmPhrase !== DELETE_ALL_PHRASE || isDeletingAll;

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
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {establishments.map((establishment) => (
                <tr key={establishment.siret}>
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
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => handleDeleteOne(establishment.siret)}
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

      <form className="establishments-danger" onSubmit={handleDeleteAll}>
        <h3>Suppression complète des établissements</h3>
        <p className="muted small">
          Tapez exactement <code>{DELETE_ALL_PHRASE}</code> pour confirmer la suppression de toutes les entrées.
        </p>
        <input
          type="text"
          value={confirmPhrase}
          onChange={(event) => setConfirmPhrase(event.target.value)}
          placeholder={DELETE_ALL_PHRASE}
        />
        <button type="submit" className="danger" disabled={disableDeleteAll}>
          {isDeletingAll ? "Suppression..." : "Supprimer tous les établissements"}
        </button>
      </form>

      {feedbackMessage && <p className="feedback success">{feedbackMessage}</p>}
      {errorMessage && <p className="feedback error">{errorMessage}</p>}
    </section>
  );
};

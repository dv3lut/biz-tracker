import { ChangeEvent, useEffect, useRef, useState } from "react";

import { Establishment, EstablishmentIndividualFilter, NafCategory } from "../types";
import { formatDateTime } from "../utils/format";
import { canonicalizeNafCode, normalizeNafCode } from "../utils/sync";
import { SiretLink } from "./SiretLink";

interface EstablishmentsSectionProps {
  establishments?: Establishment[];
  isLoading: boolean;
  error: Error | null;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  limit: number;
  page: number;
  query: string;
  nafCodes: string[];
  addedFrom: string;
  addedTo: string;
  individualFilter: EstablishmentIndividualFilter;
  hasNextPage: boolean;
  onLimitChange: (limit: number) => void;
  onPageChange: (page: number) => void;
  onQueryChange: (query: string) => void;
  onNafCodesChange: (value: string[]) => void;
  onAddedFromChange: (value: string) => void;
  onAddedToChange: (value: string) => void;
  onApplyFilters: () => void;
  hasPendingFilters: boolean;
  onResetFilters: () => void;
  onIndividualFilterChange: (value: EstablishmentIndividualFilter) => void;
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
  nafCategories,
  isLoadingNafCategories,
  limit,
  page,
  query,
  nafCodes,
  addedFrom,
  addedTo,
  individualFilter,
  hasNextPage,
  onLimitChange,
  onPageChange,
  onQueryChange,
  onNafCodesChange,
  onAddedFromChange,
  onAddedToChange,
  onApplyFilters,
  hasPendingFilters,
  onResetFilters,
  onIndividualFilterChange,
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
  const nafDetailsRef = useRef<HTMLDetailsElement | null>(null);
  const [isNafOpen, setIsNafOpen] = useState(false);

  useEffect(() => {
    if (!isNafOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const details = nafDetailsRef.current;
      if (!details) {
        return;
      }

      if (details.contains(event.target as Node)) {
        return;
      }

      setIsNafOpen(false);
    };

    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [isNafOpen]);

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    onQueryChange(event.target.value);
  };

  const handleAddedFromChange = (event: ChangeEvent<HTMLInputElement>) => {
    onAddedFromChange(event.target.value);
  };

  const handleAddedToChange = (event: ChangeEvent<HTMLInputElement>) => {
    onAddedToChange(event.target.value);
  };

  const handleLimitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onLimitChange(Number(event.target.value));
  };

  const handleIndividualFilterChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onIndividualFilterChange(event.target.value as EstablishmentIndividualFilter);
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

  const handleToggleNafCode = (nafCode: string) => {
    const normalized = normalizeNafCode(nafCode);
    if (!normalized) {
      return;
    }
    if (nafCodes.includes(normalized)) {
      onNafCodesChange(nafCodes.filter((item) => item !== normalized));
      return;
    }
    onNafCodesChange([...nafCodes, normalized]);
  };

  const nafSelectionLabel = () => {
    if (isLoadingNafCategories) {
      return "Chargement des NAF…";
    }
    if (!nafCodes.length) {
      return "Tous";
    }
    if (nafCodes.length === 1) {
      return canonicalizeNafCode(nafCodes[0]) ?? nafCodes[0];
    }
    return `${nafCodes.length} sélectionnés`;
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
        <div className="establishments-controls-row establishments-controls-row--main">
          <div className="establishments-control establishments-control--search">
            <input
              type="search"
              value={query}
              onChange={handleSearchChange}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  onApplyFilters();
                }
              }}
              placeholder="Filtrer par SIRET, nom ou code postal"
            />
          </div>

          <div className="establishments-control establishments-control--naf">
            <details
              ref={nafDetailsRef}
              className="naf-multiselect"
              open={isNafOpen}
              onToggle={(event) => {
                setIsNafOpen((event.target as HTMLDetailsElement).open);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setIsNafOpen(false);
                }
              }}
            >
              <summary className="muted small">NAF : {nafSelectionLabel()}</summary>
              <div className="naf-multiselect-panel">
                {!isLoadingNafCategories && (!nafCategories || nafCategories.length === 0) ? (
                  <p className="muted small">Aucun NAF configuré.</p>
                ) : null}
                {nafCategories?.map((category) => (
                  <div key={category.id} className="naf-multiselect-group">
                    <div className="naf-multiselect-group-title muted small">{category.name}</div>
                    <div className="naf-multiselect-options">
                      {category.subcategories
                        .filter((subcategory) => subcategory.isActive)
                        .map((subcategory) => {
                          const normalizedCode = normalizeNafCode(subcategory.nafCode);
                          if (!normalizedCode) {
                            return null;
                          }
                          const checked = nafCodes.includes(normalizedCode);
                          const label = `${canonicalizeNafCode(normalizedCode) ?? normalizedCode} — ${subcategory.name}`;
                          return (
                            <label key={subcategory.id} className="naf-multiselect-option muted small">
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => handleToggleNafCode(normalizedCode)}
                                disabled={isLoading}
                              />
                              <span>{label}</span>
                            </label>
                          );
                        })}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          </div>

          <div className="establishments-control establishments-control--added-from">
            <label className="muted small">
              Ajouté du
              <input
                type="date"
                value={addedFrom}
                onChange={handleAddedFromChange}
                title="Pour une date exacte, mettre la même date dans 'du' et 'au'."
              />
            </label>
          </div>

          <div className="establishments-control establishments-control--added-to">
            <label className="muted small">
              au
              <input
                type="date"
                value={addedTo}
                onChange={handleAddedToChange}
                title="Pour une date exacte, mettre la même date dans 'du' et 'au'."
              />
            </label>
          </div>

          <div className="establishments-control establishments-control--individual">
            <label className="muted small">
              Entreprise individuelle
              <select value={individualFilter} onChange={handleIndividualFilterChange}>
                <option value="all">Toutes</option>
                <option value="individual">Oui uniquement</option>
                <option value="non_individual">Sans EI</option>
              </select>
            </label>
          </div>
        </div>

        <div className="establishments-controls-row establishments-controls-row--secondary">
          <div className="establishments-control establishments-control--limit">
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
          </div>

          <div className="establishments-control establishments-control--pagination">
            <div className="establishments-pagination">
              <button
                type="button"
                className="ghost"
                onClick={() => onPageChange(Math.max(0, page - 1))}
                disabled={page === 0 || isLoading}
              >
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

          <div className="establishments-controls-actions">
            <div className="establishments-control establishments-control--apply">
              <button
                type="button"
                className="primary"
                onClick={onApplyFilters}
                disabled={isLoading || isLoadingNafCategories || !hasPendingFilters}
                title={hasPendingFilters ? "Appliquer les filtres" : "Aucun changement de filtre"}
              >
                Rechercher
              </button>
            </div>

            <div className="establishments-control establishments-control--reset">
              <button type="button" className="ghost" onClick={onResetFilters} disabled={isLoading}>
                Réinitialiser
              </button>
            </div>
          </div>
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
                    <strong>
                      <SiretLink value={establishment.siret} />
                    </strong>
                    <br />
                    <span className="small muted">SIREN: {establishment.siren}</span>
                  </td>
                  <td>
                    {establishment.name || "—"}
                    <br />
                    <span className="small muted">
                      NAF: {establishment.nafCode ?? "—"} {establishment.nafLibelle ? `(${establishment.nafLibelle})` : ""}
                    </span>
                    <br />
                    <span className="small muted">
                      Entreprise individuelle: {establishment.isSoleProprietorship ? "Oui" : "Non"}
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

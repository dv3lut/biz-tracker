import { ChangeEvent, useEffect, useRef, useState } from "react";

import {
  Establishment,
  EstablishmentIndividualFilter,
  LinkedInStatus,
  NafCategory,
  Region,
  WebsiteScrapeStatus,
} from "../types";
import { formatDateTime, formatNumber } from "../utils/format";
import { canonicalizeNafCode, normalizeNafCode } from "../utils/sync";
import { openGoogleSearchForEstablishment } from "../utils/googleSearch";
import toast from "react-hot-toast";
import { SiretLink } from "./SiretLink";
import { GoogleFindPlaceDebugModal } from "./GoogleFindPlaceDebugModal";
import { RegionDepartmentPanel } from "./RegionDepartmentPanel";

interface EstablishmentsSectionProps {
  establishments?: Establishment[];
  resultCount?: number;
  isResultCountLoading: boolean;
  isLoading: boolean;
  error: Error | null;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  regions: Region[] | undefined;
  isLoadingRegions: boolean;
  limit: number;
  page: number;
  query: string;
  nafCodes: string[];
  departmentCodes: string[];
  addedFrom: string;
  addedTo: string;
  lastTreatmentFrom: string;
  lastTreatmentTo: string;
  individualFilter: EstablishmentIndividualFilter;
  googleCheckStatus: string;
  linkedinStatuses: LinkedInStatus[];
  websiteScrapeStatuses: WebsiteScrapeStatus[];
  hasNextPage: boolean;
  onLimitChange: (limit: number) => void;
  onPageChange: (page: number) => void;
  onQueryChange: (query: string) => void;
  onNafCodesChange: (value: string[]) => void;
  onDepartmentCodesChange: (value: string[]) => void;
  onAddedFromChange: (value: string) => void;
  onAddedToChange: (value: string) => void;
  onLastTreatmentFromChange: (value: string) => void;
  onLastTreatmentToChange: (value: string) => void;
  onApplyFilters: () => void;
  hasPendingFilters: boolean;
  onResetFilters: () => void;
  onIndividualFilterChange: (value: EstablishmentIndividualFilter) => void;
  onGoogleCheckStatusChange: (value: string) => void;
  onLinkedinStatusesChange: (value: LinkedInStatus[]) => void;
  onWebsiteScrapeStatusesChange: (value: WebsiteScrapeStatus[]) => void;
  onRefresh: () => void;
  onDeleteEstablishment: (siret: string) => void;
  deletingSiret: string | null;
  isDeletingOne: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onTriggerGoogleCheck: (siret: string) => void;
  isCheckingGoogle: boolean;
  checkingGoogleSiret: string | null;
  onTriggerGoogleFindPlaceDebug: (siret: string) => void;
  isDebuggingGoogleFindPlace: boolean;
  debuggingGoogleFindPlaceSiret: string | null;
  googleFindPlaceDebugModal: { siret: string; result: import("../types").GoogleFindPlaceDebugResult } | null;
  onCloseGoogleFindPlaceDebugModal: () => void;
  onSelectEstablishment: (siret: string) => void;
}

export const EstablishmentsSection = ({
  establishments,
  resultCount,
  isResultCountLoading,
  isLoading,
  error,
  nafCategories,
  isLoadingNafCategories,
  regions,
  isLoadingRegions,
  limit,
  page,
  query,
  nafCodes,
  departmentCodes,
  addedFrom,
  addedTo,
  lastTreatmentFrom,
  lastTreatmentTo,
  individualFilter,
  googleCheckStatus,
  linkedinStatuses,
  websiteScrapeStatuses,
  hasNextPage,
  onLimitChange,
  onPageChange,
  onQueryChange,
  onNafCodesChange,
  onDepartmentCodesChange,
  onAddedFromChange,
  onAddedToChange,
  onLastTreatmentFromChange,
  onLastTreatmentToChange,
  onApplyFilters,
  hasPendingFilters,
  onResetFilters,
  onIndividualFilterChange,
  onGoogleCheckStatusChange,
  onLinkedinStatusesChange,
  onWebsiteScrapeStatusesChange,
  onRefresh,
  onDeleteEstablishment,
  deletingSiret,
  isDeletingOne,
  feedbackMessage,
  errorMessage,
  onTriggerGoogleCheck,
  isCheckingGoogle,
  checkingGoogleSiret,
  onTriggerGoogleFindPlaceDebug,
  isDebuggingGoogleFindPlace,
  debuggingGoogleFindPlaceSiret,
  googleFindPlaceDebugModal,
  onCloseGoogleFindPlaceDebugModal,
  onSelectEstablishment,
}: EstablishmentsSectionProps) => {
  const nafDetailsRef = useRef<HTMLDetailsElement | null>(null);
  const [isNafOpen, setIsNafOpen] = useState(false);
  const [isRegionModalOpen, setIsRegionModalOpen] = useState(false);

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

  const handleOpenRegionModal = () => {
    setIsRegionModalOpen(true);
  };

  const handleCloseRegionModal = () => {
    setIsRegionModalOpen(false);
  };

  const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
    onQueryChange(event.target.value);
  };

  const handleAddedFromChange = (event: ChangeEvent<HTMLInputElement>) => {
    onAddedFromChange(event.target.value);
  };

  const handleAddedToChange = (event: ChangeEvent<HTMLInputElement>) => {
    onAddedToChange(event.target.value);
  };

  const handleLastTreatmentFromChange = (event: ChangeEvent<HTMLInputElement>) => {
    onLastTreatmentFromChange(event.target.value);
  };

  const handleLastTreatmentToChange = (event: ChangeEvent<HTMLInputElement>) => {
    onLastTreatmentToChange(event.target.value);
  };

  const handleLimitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onLimitChange(Number(event.target.value));
  };

  const handleIndividualFilterChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onIndividualFilterChange(event.target.value as EstablishmentIndividualFilter);
  };

  const handleGoogleCheckStatusChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onGoogleCheckStatusChange(event.target.value);
  };

  const handleLinkedinStatusToggle = (status: LinkedInStatus, checked: boolean) => {
    if (checked) {
      onLinkedinStatusesChange(
        linkedinStatuses.includes(status) ? linkedinStatuses : [...linkedinStatuses, status],
      );
      return;
    }
    onLinkedinStatusesChange(linkedinStatuses.filter((value) => value !== status));
  };

  const handleWebsiteScrapeStatusToggle = (status: WebsiteScrapeStatus, checked: boolean) => {
    if (checked) {
      onWebsiteScrapeStatusesChange(
        websiteScrapeStatuses.includes(status)
          ? websiteScrapeStatuses
          : [...websiteScrapeStatuses, status],
      );
      return;
    }
    onWebsiteScrapeStatusesChange(websiteScrapeStatuses.filter((value) => value !== status));
  };

  const linkedinStatusLabel = () => {
    if (!linkedinStatuses.length) {
      return "Tous";
    }
    if (linkedinStatuses.length === 1) {
      return linkedinStatuses[0];
    }
    return `${linkedinStatuses.length} sélectionnés`;
  };

  const websiteScrapeStatusLabel = () => {
    if (!websiteScrapeStatuses.length) {
      return "Tous";
    }
    if (websiteScrapeStatuses.length === 1) {
      return websiteScrapeStatuses[0];
    }
    return `${websiteScrapeStatuses.length} sélectionnés`;
  };

  const computeWebsiteScrapeStatus = (establishment: Establishment): WebsiteScrapeStatus => {
    const websiteUrl = establishment.googleContactWebsite?.trim();
    if (!websiteUrl) {
      return "no_website";
    }
    if (!establishment.websiteScrapedAt) {
      return "pending";
    }
    const hasInfo = [
      establishment.websiteScrapedMobilePhones,
      establishment.websiteScrapedNationalPhones,
      establishment.websiteScrapedEmails,
      establishment.websiteScrapedFacebook,
      establishment.websiteScrapedInstagram,
      establishment.websiteScrapedTwitter,
      establishment.websiteScrapedLinkedin,
    ].some((value) => Boolean(value && value.trim()));
    return hasInfo ? "found" : "no_info";
  };

  const computeLinkedInSummary = (establishment: Establishment): string => {
    const directors = establishment.directors ?? [];
    const physical = directors.filter((d) => d.typeDirigeant === "personne physique");
    if (physical.length === 0) {
      return "Aucun dirigeant physique";
    }
    const found = physical.filter((d) => d.linkedinCheckStatus === "found" || Boolean(d.linkedinProfileUrl)).length;
    const insufficient = physical.filter((d) => d.linkedinCheckStatus === "insufficient").length;
    const notFound = physical.filter((d) => d.linkedinCheckStatus === "not_found").length;
    const pending = physical.filter((d) => d.linkedinCheckStatus === "pending").length;
    return `${found} trouvé(s) · ${insufficient} insuffisant(s) · ${notFound} non trouvé(s) · ${pending} en attente`;
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

  const departmentSelectionLabel = () => {
    if (isLoadingRegions) {
      return "Chargement des départements…";
    }
    if (!regions || regions.length === 0) {
      return "Aucun département";
    }
    const allCodes = regions.flatMap((region) => region.departments.map((department) => department.code));
    if (!departmentCodes.length || departmentCodes.length === allCodes.length) {
      return "Tous";
    }
    if (departmentCodes.length === 1) {
      const target = departmentCodes[0];
      const department = regions
        .flatMap((region) => region.departments)
        .find((entry) => entry.code === target);
      return department ? `${department.code} · ${department.name}` : target;
    }
    return `${departmentCodes.length} sélectionnés`;
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

      <div className="establishments-results muted small">
        Résultats : {isResultCountLoading ? "Calcul en cours…" : formatNumber(resultCount ?? null)}
      </div>

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
              <div className="naf-multiselect-panel region-multiselect-panel">
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

          <div className="establishments-control establishments-control--naf">
            <button
              type="button"
              className="filter-modal-trigger muted small"
              onClick={handleOpenRegionModal}
              disabled={isLoadingRegions}
            >
              Départements : {departmentSelectionLabel()}
            </button>
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

          <div className="establishments-control establishments-control--last-treatment-from">
            <label className="muted small">
              Dernier traitement du
              <input
                type="date"
                value={lastTreatmentFrom}
                onChange={handleLastTreatmentFromChange}
                title="Pour une date exacte, mettre la même date dans 'du' et 'au'."
              />
            </label>
          </div>

          <div className="establishments-control establishments-control--last-treatment-to">
            <label className="muted small">
              au
              <input
                type="date"
                value={lastTreatmentTo}
                onChange={handleLastTreatmentToChange}
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

          <div className="establishments-control establishments-control--google-status">
            <label className="muted small">
              Statut business (Google)
              <select value={googleCheckStatus} onChange={handleGoogleCheckStatusChange}>
                <option value="">Tous</option>
                <option value="found">Trouvées (found)</option>
                <option value="not_found">Sans résultat (not_found)</option>
                <option value="insufficient">Identité insuffisante (insufficient)</option>
                <option value="pending">En attente (pending)</option>
                <option value="other">Autres statuts</option>
              </select>
            </label>
          </div>

          <div className="establishments-control establishments-control--linkedin-status">
            <label className="muted small">
              Statut LinkedIn
              <details className="linkedin-status-multiselect">
                <summary>{linkedinStatusLabel()}</summary>
                <div className="linkedin-status-panel">
                  {(["pending", "found", "not_found", "error", "insufficient"] as LinkedInStatus[]).map((status) => (
                    <label key={status} className="linkedin-status-option">
                      <input
                        type="checkbox"
                        checked={linkedinStatuses.includes(status)}
                        onChange={(event) => handleLinkedinStatusToggle(status, event.target.checked)}
                      />
                      <span>
                        {status === "pending"
                          ? "En attente"
                          : status === "found"
                            ? "Trouvé"
                            : status === "not_found"
                              ? "Non trouvé"
                              : status === "error"
                                ? "En erreur"
                                : "Identité insuffisante"}
                      </span>
                    </label>
                  ))}
                </div>
              </details>
            </label>
          </div>

          <div className="establishments-control establishments-control--linkedin-status">
            <label className="muted small">
              Statut scraping site
              <details className="linkedin-status-multiselect">
                <summary>{websiteScrapeStatusLabel()}</summary>
                <div className="linkedin-status-panel">
                  {(["pending", "found", "no_info", "no_website"] as WebsiteScrapeStatus[]).map((status) => (
                    <label key={status} className="linkedin-status-option">
                      <input
                        type="checkbox"
                        checked={websiteScrapeStatuses.includes(status)}
                        onChange={(event) => handleWebsiteScrapeStatusToggle(status, event.target.checked)}
                      />
                      <span>
                        {status === "pending"
                          ? "En attente"
                          : status === "found"
                            ? "Infos trouvées"
                            : status === "no_info"
                              ? "Aucune info"
                              : "Sans site web"}
                      </span>
                    </label>
                  ))}
                </div>
              </details>
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

      {isRegionModalOpen ? (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal region-filter-modal">
            <header className="modal-header">
              <div>
                <h3>Filtrer par départements</h3>
                <p className="muted small">Sélectionnez une région pour inclure tous ses départements.</p>
              </div>
              <button type="button" className="ghost" onClick={handleCloseRegionModal}>
                Fermer
              </button>
            </header>
            <div className="modal-content">
              <RegionDepartmentPanel
                regions={regions}
                isLoading={isLoadingRegions}
                selectedDepartmentCodes={departmentCodes}
                onSelectionChange={onDepartmentCodesChange}
                helperText="Sélectionnez une région pour inclure tous ses départements, ou choisissez au détail."
              />
            </div>
          </div>
        </div>
      ) : null}

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
                    <span className="small muted">LinkedIn: {computeLinkedInSummary(establishment)}</span>
                    <br />
                    <span className="small muted">
                      Dernière détection: {establishment.googleLastFoundAt ? formatDateTime(establishment.googleLastFoundAt) : "—"}
                    </span>
                    <br />
                    <span className="small muted">Scraping site: {computeWebsiteScrapeStatus(establishment)}</span>
                    <br />
                    <span className="small muted">
                      Site web: {establishment.googleContactWebsite ? "détecté" : "absent"}
                    </span>
                    {establishment.googlePlaceId && (
                      <>
                        <br />
                        <span className="small muted">Place ID: {establishment.googlePlaceId}</span>
                      </>
                    )}
                    {establishment.googleContactWebsite && (
                      <>
                        <br />
                        <a className="small" href={establishment.googleContactWebsite} target="_blank" rel="noreferrer">
                          Ouvrir le site web
                        </a>
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
                        const opened = openGoogleSearchForEstablishment({
                          name: establishment.name,
                          libelleCommune: establishment.libelleCommune,
                          codePostal: establishment.codePostal,
                        });
                        if (!opened) {
                          toast.error(
                            "Impossible de construire une recherche Google (nom / commune / code postal manquants).",
                            { id: "google-search-missing-data" },
                          );
                        }
                      }}
                    >
                      Recherche Google
                    </button>
                    <br />
                    <button
                      type="button"
                      className="ghost"
                      onClick={(event) => {
                        event.stopPropagation();
                        onTriggerGoogleFindPlaceDebug(establishment.siret);
                      }}
                      disabled={isDebuggingGoogleFindPlace && debuggingGoogleFindPlaceSiret === establishment.siret}
                    >
                      {isDebuggingGoogleFindPlace && debuggingGoogleFindPlaceSiret === establishment.siret
                        ? "Récupération..."
                        : "Debug API Google"}
                    </button>
                    <br />
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

      {googleFindPlaceDebugModal ? (
        <GoogleFindPlaceDebugModal
          siret={googleFindPlaceDebugModal.siret}
          result={googleFindPlaceDebugModal.result}
          onClose={onCloseGoogleFindPlaceDebugModal}
        />
      ) : null}
    </section>
  );
};

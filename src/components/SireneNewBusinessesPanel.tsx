import { FormEvent, useEffect, useRef, useState } from "react";

import type { NafCategory, Region, SireneNewBusiness, SireneNewBusinessesResult } from "../types";
import { formatDate, formatNumber } from "../utils/format";
import { canonicalizeNafCode, normalizeNafCode } from "../utils/sync";
import { SiretLink } from "./SiretLink";
import { RegionDepartmentPanel } from "./RegionDepartmentPanel";

type Props = {
  startDate: string;
  endDate: string;
  nafCodesInput: string;
  selectedNafCodes: string[];
  limit: number;
  isLoading: boolean;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  regions: Region[] | undefined;
  isLoadingRegions: boolean;
  selectedDepartmentCodes: string[];
  errorMessage: string | null;
  result: SireneNewBusinessesResult | null;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onNafCodesInputChange: (value: string) => void;
  onToggleNafCode: (value: string) => void;
  onDepartmentCodesChange: (value: string[]) => void;
  onLimitChange: (value: number) => void;
  enrichAnnuaire: boolean;
  onEnrichAnnuaireChange: (value: boolean) => void;
  onSubmit: () => void;
  onReset: () => void;
  onGoogleSearch: (siret: string) => void;
  onDebugGoogleFindPlace: (siret: string) => void;
  debuggingGoogleFindPlaceSiret: string | null;
};

const buildDisplayName = (item: SireneNewBusiness): string => {
  return (
    item.name ??
    item.denominationUsuelleEtablissement ??
    item.enseigne1 ??
    item.denominationUsuelleUniteLegale ??
    item.denominationUniteLegale ??
    "—"
  );
};

const hasInsufficientIdentity = (item: SireneNewBusiness): boolean => {
  return (
    !item.name &&
    !item.denominationUsuelleEtablissement &&
    !item.enseigne1 &&
    !item.enseigne2 &&
    !item.enseigne3 &&
    !item.denominationUsuelleUniteLegale &&
    !item.denominationUniteLegale &&
    !item.leaderName
  );
};

const buildAddress = (item: SireneNewBusiness): string => {
  const streetParts = [item.numeroVoie, item.indiceRepetition, item.typeVoie, item.libelleVoie]
    .filter(Boolean)
    .join(" ");
  const cityParts = [item.codePostal, item.libelleCommune ?? item.libelleCommuneEtranger]
    .filter(Boolean)
    .join(" ");
  const lineParts = [streetParts, item.complementAdresse, cityParts].filter(Boolean);
  return lineParts.length > 0 ? lineParts.join(", ") : "—";
};

export const SireneNewBusinessesPanel = ({
  startDate,
  endDate,
  nafCodesInput,
  selectedNafCodes,
  limit,
  isLoading,
  nafCategories,
  isLoadingNafCategories,
  regions,
  isLoadingRegions,
  selectedDepartmentCodes,
  errorMessage,
  result,
  onStartDateChange,
  onEndDateChange,
  onNafCodesInputChange,
  onToggleNafCode,
  onDepartmentCodesChange,
  onLimitChange,
  enrichAnnuaire,
  onEnrichAnnuaireChange,
  onSubmit,
  onReset,
  onGoogleSearch,
  onDebugGoogleFindPlace,
  debuggingGoogleFindPlaceSiret,
}: Props) => {
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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  const groupedByNaf = result
    ? result.establishments.reduce((acc, item) => {
        const key = canonicalizeNafCode(item.nafCode) ?? item.nafCode ?? "NAF inconnue";
        const current = acc.get(key) ?? [];
        current.push(item);
        acc.set(key, current);
        return acc;
      }, new Map<string, SireneNewBusiness[]>())
    : null;

  const nafGroups = groupedByNaf
    ? Array.from(groupedByNaf.entries()).sort((a, b) => a[0].localeCompare(b[0]))
    : [];

  const handleToggleNafCode = (nafCode: string) => {
    const normalized = normalizeNafCode(nafCode);
    if (!normalized) {
      return;
    }
    onToggleNafCode(normalized);
  };

  const nafSelectionLabel = () => {
    if (isLoadingNafCategories) {
      return "Chargement des NAF…";
    }
    if (!selectedNafCodes.length) {
      return "Tous";
    }
    if (selectedNafCodes.length === 1) {
      return canonicalizeNafCode(selectedNafCodes[0]) ?? selectedNafCodes[0];
    }
    return `${selectedNafCodes.length} sélectionnés`;
  };

  const departmentSelectionLabel = () => {
    if (isLoadingRegions) {
      return "Chargement des départements…";
    }
    if (!regions || regions.length === 0) {
      return "Aucun département";
    }
    const allCodes = regions.flatMap((region) => region.departments.map((department) => department.code));
    if (!selectedDepartmentCodes.length || selectedDepartmentCodes.length === allCodes.length) {
      return "Tous";
    }
    if (selectedDepartmentCodes.length === 1) {
      const target = selectedDepartmentCodes[0];
      const department = regions
        .flatMap((region) => region.departments)
        .find((entry) => entry.code === target);
      return department ? `${department.code} · ${department.name}` : target;
    }
    return `${selectedDepartmentCodes.length} sélectionnés`;
  };

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>API Sirene — nouveaux établissements</h2>
          <p className="muted">Interroger les créations Sirene sur une plage de dates et codes NAF.</p>
        </div>
      </header>

      <form className="form-grid tools-form-compact" onSubmit={handleSubmit}>
        <div className="form-field">
          <label className="input-label" htmlFor="sirene-start-date">
            Date de début
          </label>
          <input
            id="sirene-start-date"
            type="date"
            value={startDate}
            onChange={(event) => onStartDateChange(event.target.value)}
            disabled={isLoading}
            required
          />
        </div>
        <div className="form-field">
          <label className="input-label" htmlFor="sirene-end-date">
            Date de fin (optionnelle)
          </label>
          <input
            id="sirene-end-date"
            type="date"
            value={endDate}
            onChange={(event) => onEndDateChange(event.target.value)}
            disabled={isLoading}
          />
          <span className="muted small">Si vide, la date de fin = date de début.</span>
        </div>
        <div className="form-field" style={{ gridColumn: "1 / -1" }}>
          <label className="input-label">Codes NAF (base + libre)</label>
          <div className="tools-naf-row">
            <div className="tools-naf-select">
              <div className="establishments-controls">
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
                    <summary className="muted small">NAF base : {nafSelectionLabel()}</summary>
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
                                const checked = selectedNafCodes.includes(normalizedCode);
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
              </div>
            </div>
            <div className="tools-naf-input">
              <textarea
                id="sirene-naf-codes"
                value={nafCodesInput}
                onChange={(event) => onNafCodesInputChange(event.target.value)}
                placeholder="56.10A, 56.30Z"
                disabled={isLoading}
              />
              <span className="muted small">Saisie libre (virgules, points-virgules ou espaces).</span>
            </div>
            <div className="tools-region-select">
              <label className="input-label">Départements</label>
              <div className="establishments-controls">
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
              </div>
              <span className="muted small">Sans sélection, toute la France est incluse.</span>
            </div>
          </div>
        </div>
        <div className="form-field" style={{ gridColumn: "1 / -1" }}>
          <label className="input-label" htmlFor="sirene-limit">
            Limite de résultats
          </label>
          <select
            id="sirene-limit"
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
            disabled={isLoading}
          >
            {[20, 50, 100, 200].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field" style={{ gridColumn: "1 / -1" }}>
          <label className="naf-multiselect-option muted small">
            <input
              type="checkbox"
              checked={enrichAnnuaire}
              onChange={(event) => onEnrichAnnuaireChange(event.target.checked)}
              disabled={isLoading}
            />
            <span>Enrichir avec les dirigeants et l'unité légale (API Recherche Entreprises)</span>
          </label>
        </div>
        <div className="card-actions" style={{ gridColumn: "1 / -1" }}>
          <button type="submit" className="primary" disabled={isLoading}>
            {isLoading ? "Recherche…" : "Rechercher"}
          </button>
          <button type="button" className="ghost" onClick={onReset} disabled={isLoading}>
            Réinitialiser
          </button>
        </div>
      </form>

      {errorMessage ? <p className="error">{errorMessage}</p> : null}

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
                selectedDepartmentCodes={selectedDepartmentCodes}
                onSelectionChange={onDepartmentCodesChange}
                helperText="Sélectionnez une région pour inclure tous ses départements, ou choisissez au détail."
              />
            </div>
          </div>
        </div>
      ) : null}

      {!isLoading && result ? (
        <div>
          <div className="muted small" style={{ marginBottom: "0.5rem" }}>
            Total Sirene: {formatNumber(result.total)} · Retournés: {formatNumber(result.returned)}
          </div>
          {nafGroups.length > 0 ? (
            <div className="muted small" style={{ marginBottom: "1rem" }}>
              {nafGroups.map(([nafCode, items]) => (
                <span key={nafCode} style={{ marginRight: "0.75rem" }}>
                  <strong>{nafCode}</strong> · {formatNumber(items.length)}
                </span>
              ))}
            </div>
          ) : null}
          {result.establishments.length === 0 ? (
            <p className="muted">Aucun établissement trouvé pour ces critères.</p>
          ) : (
            nafGroups.map(([nafCode, items]) => {
              const sorted = [...items].sort((a, b) => {
                const aInsufficient = hasInsufficientIdentity(a);
                const bInsufficient = hasInsufficientIdentity(b);
                if (aInsufficient === bInsufficient) {
                  return 0;
                }
                return aInsufficient ? 1 : -1;
              });

              const nafLabel = items.find((item) => item.nafLabel)?.nafLabel;

              return (
                <div key={nafCode} style={{ marginBottom: "1.5rem" }}>
                  <h3 style={{ marginBottom: "0.35rem" }}>{nafCode}</h3>
                  {nafLabel ? <p className="muted small">{nafLabel}</p> : null}
                  <div className="table-wrapper">
                    <table>
                      <thead>
                        <tr>
                          <th>Nom</th>
                          <th>SIRET</th>
                          <th>NAF</th>
                          <th>Créé le</th>
                          <th>Adresse</th>
                          <th>EI</th>
                          <th>Unité légale</th>
                          <th>Dirigeants</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sorted.map((item) => (
                          <tr key={item.siret}>
                            <td>
                              <strong>{buildDisplayName(item)}</strong>
                              {item.enseigne2 || item.enseigne3 ? (
                                <div className="muted small">
                                  {[item.enseigne2, item.enseigne3].filter(Boolean).join(" · ")}
                                </div>
                              ) : null}
                            </td>
                            <td>
                              <SiretLink value={item.siret} />
                            </td>
                            <td>
                              {canonicalizeNafCode(item.nafCode) ?? item.nafCode ?? "—"}
                              {item.nafLabel ? <div className="muted small">{item.nafLabel}</div> : null}
                            </td>
                            <td>{formatDate(item.dateCreation)}</td>
                            <td>{buildAddress(item)}</td>
                            <td>{item.isIndividual ? "Oui" : "Non"}</td>
                            <td>{item.legalUnitName ?? "—"}</td>
                            <td>
                              {item.directors && item.directors.length > 0
                                ? item.directors.map((d, i) => (
                                    <div key={i} className="muted small">
                                      {d.typeDirigeant === "personne physique"
                                        ? [d.firstNames, d.lastName].filter(Boolean).join(" ") || "—"
                                        : d.denomination || "—"}
                                      {d.quality ? ` (${d.quality})` : ""}
                                    </div>
                                  ))
                                : (item.leaderName ?? "—")}
                            </td>
                            <td>
                              <div className="card-actions">
                                <button
                                  type="button"
                                  className="secondary"
                                  onClick={() => onGoogleSearch(item.siret)}
                                >
                                  Recherche Google
                                </button>
                                <button
                                  type="button"
                                  className="ghost"
                                  onClick={() => onDebugGoogleFindPlace(item.siret)}
                                  disabled={debuggingGoogleFindPlaceSiret === item.siret}
                                >
                                  {debuggingGoogleFindPlaceSiret === item.siret
                                    ? "Debug…"
                                    : "Debug API Google"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })
          )}
        </div>
      ) : null}
    </section>
  );
};

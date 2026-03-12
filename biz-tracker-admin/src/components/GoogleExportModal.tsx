import { type FormEvent, useMemo, useState, useEffect } from "react";
import type { ListingStatus, NafCategoryStat } from "../types";
import { normalizeNafCode, denormalizeNafCode, canonicalizeNafCode, MAX_TARGET_NAF_CODES } from "../utils/sync";
import { DEFAULT_LISTING_STATUSES, LISTING_STATUS_OPTIONS } from "../constants/listingStatuses";

type NormalizedSubcategory = NafCategoryStat["subcategories"][number] & {
  normalizedNafCode: string;
  displayNafCode: string;
};

type NormalizedCategory = {
  categoryId: string;
  name: string;
  nafCodes: string[];
  subcategories: NormalizedSubcategory[];
};

const buildNormalizedCategories = (categories: NafCategoryStat[]): NormalizedCategory[] => {
  return categories
    .map((category) => {
      const normalizedSubs = category.subcategories
        .map((sub) => {
          const normalized = normalizeNafCode(sub.nafCode);
          if (!normalized) {
            return null;
          }
          return {
            ...sub,
            normalizedNafCode: normalized,
            displayNafCode: denormalizeNafCode(normalized),
          };
        })
        .filter((sub): sub is NormalizedSubcategory => Boolean(sub));

      const codes = Array.from(new Set(normalizedSubs.map((sub) => sub.normalizedNafCode)));
      return {
        categoryId: category.categoryId,
        name: category.name,
        subcategories: normalizedSubs,
        nafCodes: codes,
      };
    })
    .filter((category) => category.subcategories.length > 0);
};

type Props = {
  isOpen: boolean;
  startDate: string;
  endDate: string;
  mode: "admin" | "client";
  listingStatuses: ListingStatus[];
  nafCategories: NafCategoryStat[];
  isSubmitting: boolean;
  onClose: () => void;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onModeChange: (mode: "admin" | "client") => void;
  onListingStatusesChange: (statuses: ListingStatus[]) => void;
  onSubmit: (nafCodes: string[]) => void;
};

export const GoogleExportModal = ({
  isOpen,
  startDate,
  endDate,
  mode,
  listingStatuses,
  nafCategories,
  isSubmitting,
  onClose,
  onStartDateChange,
  onEndDateChange,
  onModeChange,
  onListingStatusesChange,
  onSubmit,
}: Props) => {
  const [selectedNafCodes, setSelectedNafCodes] = useState<string[]>([]);

  useEffect(() => {
    if (isOpen) {
      setSelectedNafCodes([]);
    }
  }, [isOpen]);

  const normalizedCategories = useMemo(() => buildNormalizedCategories(nafCategories), [nafCategories]);

  const allSelectableCodes = useMemo(() => {
    const set = new Set<string>();
    normalizedCategories.forEach((category) => {
      category.nafCodes.forEach((code) => set.add(code));
    });
    return Array.from(set);
  }, [normalizedCategories]);

  const selectedSet = useMemo(() => new Set(selectedNafCodes), [selectedNafCodes]);
  const isAllSelected =
    allSelectableCodes.length > 0 && allSelectableCodes.every((code) => selectedSet.has(code));

  const addNafCodes = (codes: string[]) => {
    const normalized = Array.from(
      new Set(codes.map((code) => normalizeNafCode(code)).filter((code): code is string => Boolean(code))),
    );
    if (normalized.length === 0) return;
    setSelectedNafCodes((current) => {
      const currentSet = new Set(current);
      const unique = normalized.filter((code) => !currentSet.has(code));
      if (unique.length === 0) return current;
      const slots = MAX_TARGET_NAF_CODES - current.length;
      if (slots <= 0) return current;
      return [...current, ...unique.slice(0, slots)];
    });
  };

  const removeNafCodes = (codes: string[]) => {
    const normalized = new Set(
      codes.map((code) => normalizeNafCode(code)).filter((code): code is string => Boolean(code)),
    );
    if (normalized.size === 0) return;
    setSelectedNafCodes((current) => current.filter((code) => !normalized.has(code)));
  };

  const handleToggleSelectAll = (checked: boolean) => {
    if (checked) {
      addNafCodes(allSelectableCodes);
    } else {
      setSelectedNafCodes([]);
    }
  };

  const handleCategoryChange = (categoryCodes: string[], checked: boolean) => {
    if (checked) {
      addNafCodes(categoryCodes);
    } else {
      removeNafCodes(categoryCodes);
    }
  };

  const handleSubcategoryChange = (code: string, checked: boolean) => {
    if (checked) {
      addNafCodes([code]);
    } else {
      removeNafCodes([code]);
    }
  };

  const isCategoryFullySelected = (categoryCodes: string[]) =>
    categoryCodes.length > 0 && categoryCodes.every((code) => selectedSet.has(code));

  const isCategoryPartial = (categoryCodes: string[]) => {
    const some = categoryCodes.some((code) => selectedSet.has(code));
    const all = categoryCodes.every((code) => selectedSet.has(code));
    return some && !all;
  };

  if (!isOpen) {
    return null;
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nafCodesPayload = selectedNafCodes.map((code) => denormalizeNafCode(code));
    onSubmit(nafCodesPayload);
  };

  const handleListingStatusToggle = (status: ListingStatus) => {
    if (listingStatuses.includes(status)) {
      const next = listingStatuses.filter((value) => value !== status);
      if (next.length === 0) {
        return;
      }
      onListingStatusesChange(next);
      return;
    }
    onListingStatusesChange([...listingStatuses, status]);
  };

  const handleSelectAllStatuses = () => {
    onListingStatusesChange([...DEFAULT_LISTING_STATUSES]);
  };

  const hasStatuses = listingStatuses.length > 0;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>Exporter Google Places</h2>
            <p className="muted small">Sélectionnez la plage de création et le mode d'export.</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Fermer
          </button>
        </header>
        <form className="modal-content" onSubmit={handleSubmit}>
          <div className="form-grid">
            <label className="form-field">
              <span className="input-label">Créé à partir du</span>
              <input
                type="date"
                value={startDate}
                onChange={(event) => onStartDateChange(event.target.value)}
                required
              />
            </label>
            <label className="form-field">
              <span className="input-label">Jusqu'au</span>
              <input
                type="date"
                value={endDate}
                min={startDate || undefined}
                onChange={(event) => onEndDateChange(event.target.value)}
                required
              />
            </label>
            <label className="form-field">
              <span className="input-label">Format</span>
              <select value={mode} onChange={(event) => onModeChange(event.target.value as "admin" | "client")}>
                <option value="client">Client (infos e-mail)</option>
                <option value="admin">Administration (tous les champs)</option>
              </select>
            </label>
          </div>
          <section>
            <h3>Statuts à inclure</h3>
            <p className="muted small">Décochez les statuts que vous souhaitez exclure de cet export ponctuel.</p>
            <div className="listing-status-grid">
              {LISTING_STATUS_OPTIONS.map((option) => (
                <label key={option.value} className="listing-status-option">
                  <input
                    type="checkbox"
                    checked={listingStatuses.includes(option.value)}
                    onChange={() => handleListingStatusToggle(option.value)}
                  />
                  <div>
                    <strong>{option.label}</strong>
                    <div className="muted small">{option.description}</div>
                  </div>
                </label>
              ))}
            </div>
            <div className="card-actions" style={{ justifyContent: "flex-start", marginTop: "0.5rem" }}>
              <button type="button" className="ghost" onClick={handleSelectAllStatuses}>
                Tout sélectionner
              </button>
            </div>
          </section>

          {normalizedCategories.length > 0 ? (
            <section>
              <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3>Filtrer par catégorie NAF</h3>
                  <p className="muted small">Optionnel — sans sélection, tous les codes sont inclus.</p>
                </div>
                {selectedNafCodes.length > 0 ? (
                  <span className="muted small">{selectedNafCodes.length} code(s)</span>
                ) : null}
              </header>
              <div className="naf-filter-section">
                <div className="naf-filter-header">
                  <label className="naf-select-all">
                    <span>Tout sélectionner</span>
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={(event) => handleToggleSelectAll(event.target.checked)}
                      disabled={isSubmitting || allSelectableCodes.length === 0}
                    />
                  </label>
                  {selectedNafCodes.length > 0 ? (
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => setSelectedNafCodes([])}
                      style={{ fontSize: "0.8rem" }}
                    >
                      Réinitialiser
                    </button>
                  ) : null}
                </div>

                <div className="naf-category-grid">
                  {normalizedCategories.map((category) => {
                    const isFull = isCategoryFullySelected(category.nafCodes);
                    const isPartial = isCategoryPartial(category.nafCodes);
                    return (
                      <div key={category.categoryId} className="naf-category">
                        <label className="naf-category-header">
                          <div>
                            <strong>{category.name}</strong>
                            <p className="muted small">{category.nafCodes.length} code(s)</p>
                          </div>
                          <input
                            type="checkbox"
                            checked={isFull}
                            data-partial={isPartial ? "true" : undefined}
                            onChange={(event) => handleCategoryChange(category.nafCodes, event.target.checked)}
                            disabled={isSubmitting || category.nafCodes.length === 0}
                          />
                        </label>
                        <div className="naf-subcategory-list">
                          {category.subcategories.map((sub) => (
                            <label key={sub.subcategoryId} className="naf-subcategory">
                              <div>
                                <strong>{sub.name}</strong>
                                <span className="muted small">{sub.displayNafCode}</span>
                              </div>
                              <input
                                type="checkbox"
                                checked={selectedSet.has(sub.normalizedNafCode)}
                                onChange={(event) => handleSubcategoryChange(sub.normalizedNafCode, event.target.checked)}
                                disabled={isSubmitting}
                              />
                            </label>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {selectedNafCodes.length > 0 ? (
                  <div className="naf-selection-preview" style={{ marginTop: "0.5rem" }}>
                    <div className="naf-chip-list">
                      {selectedNafCodes.map((code) => (
                        <span key={code} className="naf-chip">
                          {canonicalizeNafCode(code) ?? code}
                          <button
                            type="button"
                            className="chip-remove"
                            onClick={() => removeNafCodes([code])}
                            disabled={isSubmitting}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          <div className="modal-actions">
            <button type="button" className="ghost" onClick={onClose} disabled={isSubmitting}>
              Annuler
            </button>
            <button type="submit" className="primary" disabled={isSubmitting || !hasStatuses}>
              {isSubmitting ? "Export en cours..." : "Télécharger l'export"}
            </button>
          </div>
          <p className="muted small">Filtre appliqué sur la date de création Sirene et les statuts sélectionnés.</p>
        </form>
      </div>
    </div>
  );
};

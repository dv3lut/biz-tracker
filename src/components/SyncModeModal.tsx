import { KeyboardEvent, useEffect, useMemo, useState } from "react";

import { NafCategoryStat, SyncMode } from "../types";
import {
  canonicalizeNafCode,
  denormalizeNafCode,
  describeSyncMode,
  formatNafCodesPreview,
  MAX_TARGET_NAF_CODES,
  normalizeNafCode,
  parseNafInput,
  syncModeIsGoogleOnly,
  syncModeRequiresReplayDate,
  syncModeSendsAlerts,
} from "../utils/sync";

const formatDateInput = (value: Date) => value.toISOString().slice(0, 10);

const MODE_OPTIONS: Array<{
  value: SyncMode;
  title: string;
  description: string;
  impact: string;
}> = [
  {
    value: "full",
    title: "Mode complet",
    description: "Télécharge les mises à jour Sirene puis déclenche les enrichissements Google Places.",
    impact: "Plus long mais garantit des fiches Google actualisées.",
  },
  {
    value: "sirene_only",
    title: "Mode Sirene uniquement",
    description: "Capture uniquement les évolutions Sirene. Les appels Google sont ignorés.",
    impact: "Recommandé pour analyser rapidement une base ou en cas d'incident Google.",
  },
  {
    value: "google_pending",
    title: "Google — nouveaux uniquement",
    description: "Ne touche pas à Sirene et rattrape uniquement les établissements jamais enrichis par Google.",
    impact: "Permet d'envoyer les alertes manquantes sans relancer un run complet.",
  },
  {
    value: "google_refresh",
    title: "Google — rafraîchir toutes les fiches",
    description: "Réinitialise les correspondances Google pour tous les établissements et relance la détection.",
    impact: "À utiliser après une mise à jour majeure de la logique de matching.",
  },
  {
    value: "day_replay",
    title: "Rejouer une journée",
    description: "Relance la collecte Sirene + Google sur une date précise pour diagnostiquer ou compléter une journée.",
    impact: "Les alertes sont limitées aux administrateurs et n'impactent pas les curseurs.",
  },
];

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

type Props = {
  isOpen: boolean;
  initialMode: SyncMode;
  initialReplayDate?: string | null;
  initialNafCodes?: string[] | null;
  nafCategories: NafCategoryStat[];
  onConfirm: (payload: { mode: SyncMode; replayForDate?: string; nafCodes?: string[] }) => void;
  onCancel: () => void;
  isSubmitting: boolean;
};

const normalizeList = (values?: string[] | null): string[] => {
  const normalized = Array.from(
    new Set((values ?? [])
      .map((code) => normalizeNafCode(code))
      .filter((code): code is string => Boolean(code)),
    ),
  );
  return normalized.slice(0, MAX_TARGET_NAF_CODES);
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

export const SyncModeModal = ({
  isOpen,
  initialMode,
  initialReplayDate,
  initialNafCodes,
  nafCategories,
  onConfirm,
  onCancel,
  isSubmitting,
}: Props) => {
  const [mode, setMode] = useState<SyncMode>(initialMode);
  const [replayDate, setReplayDate] = useState<string>(() => {
    if (initialReplayDate) {
      return initialReplayDate;
    }
    return formatDateInput(new Date());
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [nafInput, setNafInput] = useState<string>("");
  const [selectedNafCodes, setSelectedNafCodes] = useState<string[]>(() => normalizeList(initialNafCodes));

  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
      setReplayDate(initialReplayDate || formatDateInput(new Date()));
      setSelectedNafCodes(normalizeList(initialNafCodes));
      setNafInput("");
      setFormError(null);
    }
  }, [initialMode, initialReplayDate, initialNafCodes, isOpen]);

  useEffect(() => {
    if (!syncModeRequiresReplayDate(mode)) {
      setFormError(null);
    }
  }, [mode]);

  const normalizedCategories = useMemo(() => buildNormalizedCategories(nafCategories), [nafCategories]);
  const allSelectableCodes = useMemo(() => {
    const set = new Set<string>();
    normalizedCategories.forEach((category) => {
      category.nafCodes.forEach((code) => set.add(code));
    });
    return Array.from(set);
  }, [normalizedCategories]);
  const limitedSelectableCodes = allSelectableCodes.slice(0, MAX_TARGET_NAF_CODES);
  const selectedSet = useMemo(() => new Set(selectedNafCodes), [selectedNafCodes]);
  const isAllSelected =
    limitedSelectableCodes.length > 0 && limitedSelectableCodes.every((code) => selectedSet.has(code));
  const selectedCount = selectedNafCodes.length;
  const remainingSlots = Math.max(0, MAX_TARGET_NAF_CODES - selectedCount);
  const modeHighlights = useMemo(() => {
    const notes: Array<{ tone: "warning" | "info"; title: string; detail: string }> = [];
    if (mode === "sirene_only") {
      notes.push({
        tone: "warning",
        title: "Google désactivé",
        detail: "Ce run ignore complètement les correspondances Google et n'enverra aucune alerte.",
      });
    }
    if (syncModeIsGoogleOnly(mode)) {
      notes.push({
        tone: "info",
        title: "Collecte Sirene non exécutée",
        detail: "Seuls les établissements déjà connus seront traités côté Google.",
      });
    }
    if (mode === "google_refresh") {
      notes.push({
        tone: "warning",
        title: "Remise à zéro des fiches",
        detail: "Toutes les correspondances Google existantes seront supprimées avant d'être recalculées.",
      });
    }
    if (mode === "day_replay") {
      notes.push({
        tone: "info",
        title: "Alertes admin uniquement",
        detail: "Rejouer une journée ne notifie pas les clients et n'avance pas les curseurs.",
      });
    }
    if (mode === "google_pending" && syncModeSendsAlerts(mode)) {
      notes.push({
        tone: "info",
        title: "Alertes actives",
        detail: "Les clients recevront un e-mail pour chaque fiche détectée suite à ce run.",
      });
    }
    return notes;
  }, [mode]);

  const addNafCodes = (codes: string[]) => {
    const normalized = Array.from(
      new Set(codes.map((code) => normalizeNafCode(code)).filter((code): code is string => Boolean(code))),
    );
    if (normalized.length === 0) {
      setFormError("Merci de saisir des codes NAF valides (ex: 5610A).");
      return;
    }

    setSelectedNafCodes((current) => {
      const currentSet = new Set(current);
      const unique = normalized.filter((code) => !currentSet.has(code));
      if (unique.length === 0) {
        setFormError("Ces codes sont déjà sélectionnés.");
        return current;
      }
      const slots = MAX_TARGET_NAF_CODES - current.length;
      if (slots <= 0) {
        setFormError(`Maximum ${MAX_TARGET_NAF_CODES} codes NAF atteints.`);
        return current;
      }
      const allowed = unique.slice(0, slots);
      if (allowed.length < unique.length) {
        setFormError(
          `Maximum ${MAX_TARGET_NAF_CODES} codes NAF ; seules ${slots} nouvelles sélections ont été conservées.`,
        );
      } else {
        setFormError(null);
      }
      return [...current, ...allowed];
    });
  };

  const removeNafCodes = (codes: string[]) => {
    const normalized = Array.from(
      new Set(codes.map((code) => normalizeNafCode(code)).filter((code): code is string => Boolean(code))),
    );
    if (normalized.length === 0) {
      return;
    }
    setSelectedNafCodes((current) => {
      const next = current.filter((code) => !normalized.includes(code));
      if (next.length !== current.length) {
        setFormError(null);
      }
      return next;
    });
  };

  const handleToggleSelectAll = (checked: boolean) => {
    if (checked) {
      addNafCodes(limitedSelectableCodes);
    } else {
      removeNafCodes(limitedSelectableCodes);
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

  const handleManualAdd = () => {
    const parsed = parseNafInput(nafInput);
    if (parsed.length === 0) {
      setFormError("Merci de saisir des codes NAF valides (ex: 5610A).\u00A0");
      return;
    }
    addNafCodes(parsed);
    setNafInput("");
  };

  const handleNafInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === "," || event.key === ";") {
      event.preventDefault();
      handleManualAdd();
    }
  };

  const handleSubmit = () => {
    const requiresReplayDate = syncModeRequiresReplayDate(mode);
    if (requiresReplayDate && !replayDate) {
      setFormError("Merci de sélectionner une date à rejouer.");
      return;
    }
    setFormError(null);
    onConfirm({
      mode,
      replayForDate: requiresReplayDate ? replayDate : undefined,
      nafCodes:
        selectedNafCodes.length > 0 ? selectedNafCodes.map((code) => denormalizeNafCode(code)) : undefined,
    });
  };

  const isCategoryFullySelected = (codes: string[]) => codes.length > 0 && codes.every((code) => selectedSet.has(code));
  const isCategoryPartial = (codes: string[]) =>
    codes.some((code) => selectedSet.has(code)) && !isCategoryFullySelected(codes);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal sync-mode-modal">
        <header className="modal-header">
          <div>
            <h2>Choisir le mode de synchronisation</h2>
            <p className="muted small">Sélectionnez la portée avant de lancer un nouveau traitement.</p>
          </div>
          <button type="button" className="ghost" onClick={onCancel} disabled={isSubmitting}>
            Fermer
          </button>
        </header>

        <div className="modal-content sync-mode-content">
          <section className="mode-panel">
            <header className="panel-header">
              <div>
                <h3>Mode de traitement</h3>
                <p className="muted small">Choisissez le périmètre exact avant de déclencher la synchro.</p>
              </div>
              <span className="pill">{mode === "day_replay" ? "Diagnostic" : "Production"}</span>
            </header>
            <div className="mode-options">
              {MODE_OPTIONS.map((option) => {
                const isSelected = option.value === mode;
                return (
                  <label key={option.value} className={`mode-option${isSelected ? " selected" : ""}`}>
                    <div className="mode-option-body">
                      <div className="mode-option-text">
                        <strong>{option.title}</strong>
                        <p className="muted small">{option.description}</p>
                      </div>
                      <input
                        type="radio"
                        name="sync-mode"
                        value={option.value}
                        checked={isSelected}
                        onChange={() => setMode(option.value)}
                        disabled={isSubmitting}
                        className="mode-option-control"
                      />
                    </div>
                    <p className="muted small mode-option-impact">{option.impact}</p>
                    {option.value === "day_replay" && isSelected ? (
                      <div className="form-control">
                        <label htmlFor="replay-date" className="muted small">
                          Choisissez la date à rejouer:
                        </label>
                        <input
                          id="replay-date"
                          type="date"
                          value={replayDate}
                          max={formatDateInput(new Date())}
                          onChange={(event) => setReplayDate(event.target.value)}
                          disabled={isSubmitting}
                        />
                      </div>
                    ) : null}
                  </label>
                );
              })}
            </div>
            <div className="mode-summary-card">
              <p className="label">Mode sélectionné</p>
              <p className="value">{describeSyncMode(mode)}</p>
              <p className="muted small">
                {selectedCount > 0
                  ? `${selectedCount} code(s) NAF ciblés · ${remainingSlots} emplacement(s) disponible(s)`
                  : "Aucun filtrage NAF — run global"}
              </p>
            </div>
            {modeHighlights.length > 0 ? (
              <div className="mode-highlights">
                {modeHighlights.map((note, index) => (
                  <div key={`${note.title}-${index}`} className={`mode-highlight ${note.tone}`}>
                    <strong>{note.title}</strong>
                    <p className="muted small">{note.detail}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="sync-target-panel">
            <header className="panel-header">
              <div>
                <h3>Cibler certains codes NAF</h3>
                <p className="muted small">Optionnel — limite la synchro aux catégories cochées ou saisies manuellement.</p>
              </div>
              <div className="selection-counter">
                <strong>{selectedCount}</strong>
                <span>/ {MAX_TARGET_NAF_CODES}</span>
                <p className="muted small">{remainingSlots} restant(s)</p>
              </div>
            </header>
            <div className="naf-filter-section">
              <div className="naf-filter-header">
                <label className="naf-select-all">
                  <span>Tout sélectionner (max {MAX_TARGET_NAF_CODES} codes)</span>
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    onChange={(event) => handleToggleSelectAll(event.target.checked)}
                    disabled={isSubmitting || limitedSelectableCodes.length === 0}
                  />
                </label>
                <span className="muted small">
                  {selectedCount} code(s) · {remainingSlots} place(s) restantes
                </span>
              </div>

              {normalizedCategories.length > 0 ? (
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
              ) : (
                <p className="muted small">Aucun filtrage NAF disponible pour l’instant.</p>
              )}

              <div className="naf-manual-card">
                <div className="naf-manual-add">
                  <label htmlFor="naf-filter-input">Ajouter un ou plusieurs codes (facultatif)</label>
                  <div className="naf-input-row">
                    <input
                      id="naf-filter-input"
                      type="text"
                      placeholder="Ex: 5610A, 7022Z"
                      value={nafInput}
                      onChange={(event) => setNafInput(event.target.value)}
                      onKeyDown={handleNafInputKeyDown}
                      disabled={isSubmitting}
                    />
                    <button type="button" className="ghost" onClick={handleManualAdd} disabled={isSubmitting}>
                      Ajouter
                    </button>
                  </div>
                  <p className="muted small">Séparez les codes par des virgules, espaces ou points-virgules.</p>
                </div>

                {selectedNafCodes.length > 0 ? (
                  <div className="naf-selection-preview">
                    <div className="naf-chip-list">
                      {selectedNafCodes.map((code) => (
                        <span key={code} className="naf-chip">
                          {canonicalizeNafCode(code) ?? code}
                          <button
                            type="button"
                            aria-label={`Retirer ${code}`}
                            onClick={() => removeNafCodes([code])}
                            disabled={isSubmitting}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <p className="muted small">Prévisualisation : {formatNafCodesPreview(selectedNafCodes, 8)}</p>
                  </div>
                ) : (
                  <p className="muted small">Aucun code sélectionné pour le moment.</p>
                )}
              </div>
            </div>
            {formError ? <p className="muted small error">{formError}</p> : null}
          </section>
        </div>

        <footer className="modal-footer">
          <button type="button" className="ghost" onClick={onCancel} disabled={isSubmitting}>
            Annuler
          </button>
          <button type="button" className="primary" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Déclenchement…" : "Lancer la synchro"}
          </button>
        </footer>
      </div>
    </div>
  );
};

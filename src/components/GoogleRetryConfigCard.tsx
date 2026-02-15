import { FormEvent, useEffect, useMemo, useState } from "react";

import { GoogleRetryConfig, GoogleRetryRule } from "../types";

const WEEKDAYS: { label: string; value: number }[] = [
  { label: "Lun", value: 0 },
  { label: "Mar", value: 1 },
  { label: "Mer", value: 2 },
  { label: "Jeu", value: 3 },
  { label: "Ven", value: 4 },
  { label: "Sam", value: 5 },
  { label: "Dim", value: 6 },
];

const DEFAULT_CONFIG: GoogleRetryConfig = {
  retryWeekdays: [0],
  retryMissingContactEnabled: true,
  retryMissingContactFrequencyDays: 14,
  retryNoWebsiteFrequencyDays: 14,
  defaultRules: [
    { maxAgeDays: 60, frequencyDays: 7 },
    { maxAgeDays: 120, frequencyDays: 14 },
    { maxAgeDays: null, frequencyDays: 30 },
  ],
  microRules: [
    { maxAgeDays: 120, frequencyDays: 21 },
    { maxAgeDays: null, frequencyDays: 60 },
  ],
};

type RuleKind = "default" | "micro";

type Props = {
  config: GoogleRetryConfig | undefined;
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  onRefresh: () => void;
  onSubmit: (payload: GoogleRetryConfig) => void;
  isSubmitting: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
};

const cloneConfig = (config?: GoogleRetryConfig): GoogleRetryConfig =>
  JSON.parse(JSON.stringify(config ?? DEFAULT_CONFIG)) as GoogleRetryConfig;

const createEmptyRule = (): GoogleRetryRule => ({ maxAgeDays: null, frequencyDays: 30 });

export const GoogleRetryConfigCard = ({
  config,
  isLoading,
  isRefreshing,
  error,
  onRefresh,
  onSubmit,
  isSubmitting,
  feedbackMessage,
  errorMessage,
}: Props) => {
  const [formState, setFormState] = useState<GoogleRetryConfig>(() => cloneConfig());

  useEffect(() => {
    if (!config) {
      return;
    }
    setFormState(cloneConfig(config));
  }, [config]);

  const isDisabled = isSubmitting || isLoading;

  const handleWeekdayToggle = (day: number) => {
    setFormState((current) => {
      const hasDay = current.retryWeekdays.includes(day);
      const updated = hasDay
        ? current.retryWeekdays.filter((value) => value !== day)
        : [...current.retryWeekdays, day];
      return { ...current, retryWeekdays: updated.sort((a, b) => a - b) };
    });
  };

  const handleRuleChange = (kind: RuleKind, index: number, field: keyof GoogleRetryRule, value: string) => {
    setFormState((current) => {
      const key = kind === "default" ? "defaultRules" : "microRules";
      const rules = [...current[key]];
      if (field === "maxAgeDays") {
        const parsed = value === "" ? null : Number(value);
        rules[index] = { ...rules[index], maxAgeDays: Number.isFinite(parsed) ? parsed : null };
      } else {
        const parsed = Number(value);
        const safeValue = Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 1;
        rules[index] = { ...rules[index], frequencyDays: safeValue };
      }
      return { ...current, [key]: rules };
    });
  };

  const handleAddRule = (kind: RuleKind) => {
    setFormState((current) => {
      const key = kind === "default" ? "defaultRules" : "microRules";
      return { ...current, [key]: [...current[key], createEmptyRule()] };
    });
  };

  const handleRemoveRule = (kind: RuleKind, index: number) => {
    setFormState((current) => {
      const key = kind === "default" ? "defaultRules" : "microRules";
      if (current[key].length <= 1) {
        return current;
      }
      const updated = current[key].filter((_, i) => i !== index);
      return { ...current, [key]: updated };
    });
  };

  const handleReset = () => {
    if (!config) {
      return;
    }
    setFormState(cloneConfig(config));
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(formState);
  };

  const renderRules = (kind: RuleKind, title: string, description: string) => {
    const rules = kind === "default" ? formState.defaultRules : formState.microRules;
    return (
      <fieldset className="google-retry-fieldset">
        <legend>{title}</legend>
        <p className="muted small">{description}</p>
        <div className="rule-list">
          {rules.map((rule, index) => (
            <div className="rule-row" key={`${kind}-rule-${index}`}>
              <label>
                <span className="input-label">Âge max (jours)</span>
                <input
                  type="number"
                  min={0}
                  value={rule.maxAgeDays ?? ""}
                  placeholder="Illimité"
                  onChange={(event) => handleRuleChange(kind, index, "maxAgeDays", event.target.value)}
                  disabled={isDisabled}
                />
              </label>
              <label>
                <span className="input-label">Fréquence (jours)</span>
                <input
                  type="number"
                  min={1}
                  required
                  value={rule.frequencyDays}
                  onChange={(event) => handleRuleChange(kind, index, "frequencyDays", event.target.value)}
                  disabled={isDisabled}
                />
              </label>
              <div className="rule-actions">
                <button
                  type="button"
                  className="ghost"
                  onClick={() => handleRemoveRule(kind, index)}
                  disabled={isDisabled || rules.length <= 1}
                >
                  Supprimer
                </button>
              </div>
            </div>
          ))}
        </div>
        <button type="button" className="ghost" onClick={() => handleAddRule(kind)} disabled={isDisabled}>
          Ajouter une règle
        </button>
      </fieldset>
    );
  };

  const weekdayLabel = useMemo(
    () =>
      WEEKDAYS.map((weekday) => (
        <label key={weekday.value} className="weekday-toggle">
          <input
            type="checkbox"
            checked={formState.retryWeekdays.includes(weekday.value)}
            onChange={() => handleWeekdayToggle(weekday.value)}
            disabled={isDisabled}
          />
          <span>{weekday.label}</span>
        </label>
      )),
    [formState.retryWeekdays, isDisabled],
  );

  return (
    <section className="card google-retry-card">
      <header className="card-header">
        <div>
          <h2>Relances Google Places</h2>
          <p className="muted">Contrôlez la fréquence et les jours d'exécution des recherches.</p>
          {isRefreshing && !isLoading ? <p className="refresh-indicator">Actualisation…</p> : null}
        </div>
        <div className="card-actions">
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Rafraîchir
          </button>
          <button type="button" className="ghost" onClick={handleReset} disabled={isDisabled || !config}>
            Réinitialiser
          </button>
        </div>
      </header>

      {feedbackMessage && <p className="feedback success">{feedbackMessage}</p>}
      {errorMessage && <p className="feedback error">{errorMessage}</p>}
      {error && <p className="error">{error.message}</p>}
      {isLoading && <p>Chargement de la configuration…</p>}

      {!isLoading ? (
        <form className="google-retry-form" onSubmit={handleSubmit}>
          <fieldset className="google-retry-fieldset">
            <legend>Jours autorisés</legend>
            <p className="muted small">Les relances automatiques ne seront déclenchées que ces jours-là.</p>
            <div className="weekday-grid">{weekdayLabel}</div>
          </fieldset>

          <fieldset className="google-retry-fieldset">
            <legend>Fiches sans contact</legend>
            <p className="muted small">
              Relance les fiches au statut « Création récente sans contact » pour détecter l'ajout de coordonnées.
            </p>
            <div className="switch-row">
              <label className="switch-row__label">
                <input
                  className="switch-row__checkbox"
                  type="checkbox"
                  checked={formState.retryMissingContactEnabled}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      retryMissingContactEnabled: event.target.checked,
                    }))
                  }
                  disabled={isDisabled}
                />
                <span>Activer la relance des fiches sans contact</span>
              </label>
              <label className="switch-row__input">
                <span className="input-label">Fréquence min (jours)</span>
                <input
                  type="number"
                  min={1}
                  value={formState.retryMissingContactFrequencyDays}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      retryMissingContactFrequencyDays: Math.max(1, Number(event.target.value || 1)),
                    }))
                  }
                  disabled={isDisabled || !formState.retryMissingContactEnabled}
                />
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>Rattrapage sites web</legend>
            <p className="muted small">
              Re-vérifie les fiches Google sans site web pour détecter les nouvelles URL et les scraper.
            </p>
            <div className="switch-row">
              <label className="switch-row__input">
                <span className="input-label">Fréquence min (jours)</span>
                <input
                  type="number"
                  min={1}
                  value={formState.retryNoWebsiteFrequencyDays}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      retryNoWebsiteFrequencyDays: Math.max(1, Number(event.target.value || 1)),
                    }))
                  }
                  disabled={isDisabled}
                />
              </label>
            </div>
          </fieldset>

          {renderRules(
            "default",
            "Règles générales",
            "Appliquées à tous les établissements ne disposant pas encore d'une fiche Google.",
          )}

          {renderRules(
            "micro",
            "Règles micro/auto-entreprise",
            "Utilisées lorsque categorie_entreprise ou categorie_juridique correspond aux filtres ci-dessous.",
          )}

          <div className="card-actions">
            <button type="submit" className="primary" disabled={isDisabled}>
              {isSubmitting ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      ) : null}
    </section>
  );
};

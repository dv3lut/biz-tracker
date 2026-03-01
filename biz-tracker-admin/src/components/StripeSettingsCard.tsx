import { FormEvent, useEffect, useMemo, useState } from "react";

import type { AdminStripeSettings, AdminStripeSettingsUpdatePayload } from "../types";

const toInputValue = (trialPeriodDays: number | null | undefined): string => {
  if (typeof trialPeriodDays !== "number" || Number.isNaN(trialPeriodDays)) {
    return "";
  }
  return String(trialPeriodDays);
};

const parseTrialPeriod = (value: string): number | null => {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.trunc(parsed);
};

type Props = {
  settings?: AdminStripeSettings | null;
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onRefresh: () => void;
  onSubmit: (payload: AdminStripeSettingsUpdatePayload) => void;
  isSubmitting: boolean;
};

export const StripeSettingsCard = ({
  settings,
  isLoading,
  isRefreshing,
  error,
  feedbackMessage,
  errorMessage,
  onRefresh,
  onSubmit,
  isSubmitting,
}: Props) => {
  const [trialPeriodDaysInput, setTrialPeriodDaysInput] = useState<string>("");
  const [applyToExistingTrials, setApplyToExistingTrials] = useState(false);

  useEffect(() => {
    setTrialPeriodDaysInput(toInputValue(settings?.trialPeriodDays));
    setApplyToExistingTrials(false);
  }, [settings]);

  const parsedTrialPeriod = useMemo(
    () => parseTrialPeriod(trialPeriodDaysInput),
    [trialPeriodDaysInput],
  );

  const isValidTrialPeriod =
    parsedTrialPeriod !== null && parsedTrialPeriod >= 0 && parsedTrialPeriod <= 60;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (parsedTrialPeriod === null || !isValidTrialPeriod) {
      return;
    }
    onSubmit({
      trialPeriodDays: parsedTrialPeriod,
      applyToExistingTrials,
    });
  };

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Paramètres Stripe</h2>
          <p className="muted">Gérez la durée d'essai appliquée aux nouvelles souscriptions.</p>
        </div>
        <div className="card-actions">
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Rafraîchir
          </button>
        </div>
      </header>

      {feedbackMessage ? <p className="feedback success">{feedbackMessage}</p> : null}
      {errorMessage ? <p className="feedback error">{errorMessage}</p> : null}

      {isLoading ? <p>Chargement de la configuration…</p> : null}
      {isRefreshing && !isLoading ? <p className="refresh-indicator">Actualisation en cours…</p> : null}
      {error ? <p className="error">{error.message}</p> : null}

      {!isLoading && !error ? (
        <form onSubmit={handleSubmit} className="email-test-form">
          <label>
            <span className="input-label">Durée de l'essai (jours)</span>
            <input
              type="number"
              min={0}
              max={60}
              value={trialPeriodDaysInput}
              onChange={(event) => setTrialPeriodDaysInput(event.target.value)}
              required
            />
          </label>
          <p className="muted small">0 désactive l'essai gratuit. Maximum 60 jours.</p>
          <label className="form-checkbox">
            <input
              type="checkbox"
              checked={applyToExistingTrials}
              onChange={(event) => setApplyToExistingTrials(event.target.checked)}
            />
            <span>Appliquer la nouvelle durée aux essais déjà en cours</span>
          </label>
          <div className="card-actions">
            <button type="submit" className="primary" disabled={isSubmitting || !isValidTrialPeriod}>
              {isSubmitting ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      ) : null}
    </section>
  );
};

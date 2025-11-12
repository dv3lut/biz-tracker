import { FormEvent, useEffect, useState } from "react";

import { AdminEmailConfig } from "../types";
import { AdminEmailConfigPayload } from "../api/adminConfig";

type Props = {
  config?: AdminEmailConfig | null;
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onRefresh: () => void;
  onSubmit: (payload: AdminEmailConfigPayload) => void;
  isSubmitting: boolean;
};

const joinRecipients = (recipients: string[]): string => {
  return recipients.join("\n");
};

const splitRecipients = (value: string): string[] => {
  const normalized = value
    .split(/[\n,;]/)
    .map((entry) => entry.trim().toLowerCase())
    .filter((entry) => entry.length > 0);
  return Array.from(new Set(normalized));
};

export const AdminEmailConfigSection = ({
  config,
  isLoading,
  isRefreshing,
  error,
  feedbackMessage,
  errorMessage,
  onRefresh,
  onSubmit,
  isSubmitting,
}: Props) => {
  const [recipientsText, setRecipientsText] = useState<string>("");

  useEffect(() => {
    if (!config) {
      setRecipientsText("");
      return;
    }
    setRecipientsText(joinRecipients(config.recipients));
  }, [config]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit({ recipients: splitRecipients(recipientsText) });
  };

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Configuration e-mail admin</h2>
          <p className="muted">Destinataires du résumé quotidien des synchronisations.</p>
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
            <span className="input-label">Destinataires du résumé</span>
            <textarea
              rows={6}
              placeholder="ops@example.com"
              value={recipientsText}
              onChange={(event) => setRecipientsText(event.target.value)}
            />
          </label>
          <p className="muted small">Une adresse par ligne ou séparée par des virgules.</p>
          <div className="card-actions">
            <button type="submit" className="primary" disabled={isSubmitting}>
              {isSubmitting ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      ) : null}
    </section>
  );
};

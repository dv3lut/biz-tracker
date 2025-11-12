import { FormEvent, useEffect, useMemo, useState } from "react";

import { Client } from "../types";
import { formatNumber, formatDateTime } from "../utils/format";

type FormState = {
  name: string;
  startDate: string;
  endDate: string;
  recipientsText: string;
};

type SubmitPayload = {
  name: string;
  startDate: string;
  endDate: string | null;
  recipients: string[];
};

type Props = {
  isOpen: boolean;
  mode: "create" | "edit";
  client: Client | null;
  onSubmit: (payload: SubmitPayload) => void;
  onCancel: () => void;
  isProcessing: boolean;
};

const EMPTY_STATE: FormState = {
  name: "",
  startDate: "",
  endDate: "",
  recipientsText: "",
};

const splitRecipients = (value: string): string[] => {
  const normalized = value
    .split(/[\n,;]/)
    .map((entry) => entry.trim().toLowerCase())
    .filter((entry) => entry.length > 0);
  return Array.from(new Set(normalized));
};

export const ClientModal = ({ isOpen, mode, client, onSubmit, onCancel, isProcessing }: Props) => {
  const [formState, setFormState] = useState<FormState>(EMPTY_STATE);

  useEffect(() => {
    if (!isOpen) {
      setFormState(EMPTY_STATE);
      return;
    }
    if (client && mode === "edit") {
      setFormState({
        name: client.name,
        startDate: client.startDate,
        endDate: client.endDate ?? "",
        recipientsText: client.recipients.map((recipient) => recipient.email).join("\n"),
      });
    } else {
      setFormState(EMPTY_STATE);
    }
  }, [client, isOpen, mode]);

  const isValid = useMemo(() => {
    return Boolean(formState.name.trim() && formState.startDate);
  }, [formState.name, formState.startDate]);

  const handleChange = (field: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormState((current) => ({ ...current, [field]: event.target.value }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isValid) {
      return;
    }
    const payload: SubmitPayload = {
      name: formState.name.trim(),
      startDate: formState.startDate,
      endDate: formState.endDate ? formState.endDate : null,
      recipients: splitRecipients(formState.recipientsText),
    };
    onSubmit(payload);
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <header className="modal-header">
          <h2>{mode === "create" ? "Nouveau client" : `Modifier ${client?.name ?? "le client"}`}</h2>
          <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
            Fermer
          </button>
        </header>
        <form className="modal-content" onSubmit={handleSubmit}>
          <section>
            <h3>Informations principales</h3>
            <div className="email-test-form">
              <label>
                <span className="input-label">Nom du client</span>
                <input
                  type="text"
                  value={formState.name}
                  onChange={handleChange("name")}
                  placeholder="Ex : Franchise Île-de-France"
                  required
                />
              </label>
              <label>
                <span className="input-label">Date de début</span>
                <input type="date" value={formState.startDate} onChange={handleChange("startDate")} required />
              </label>
              <label>
                <span className="input-label">Date de fin (optionnelle)</span>
                <input type="date" value={formState.endDate} onChange={handleChange("endDate")} />
              </label>
            </div>
          </section>

          <section>
            <h3>Destinataires</h3>
            <p className="muted small">
              Une adresse par ligne ou séparée par des virgules. Les adresses seront dédupliquées et converties en
              minuscules.
            </p>
            <textarea
              rows={6}
              value={formState.recipientsText}
              onChange={handleChange("recipientsText")}
              placeholder="client@example.com"
            />
          </section>

          {mode === "edit" && client ? (
            <section>
              <h3>Historique</h3>
              <p className="small muted">
                E-mails envoyés : {formatNumber(client.emailsSentCount)}
                <br />
                Dernier envoi : {formatDateTime(client.lastEmailSentAt)}
              </p>
            </section>
          ) : null}

          <section className="card-actions">
            <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
              Annuler
            </button>
            <button type="submit" className="primary" disabled={!isValid || isProcessing}>
              {isProcessing ? "Enregistrement…" : "Enregistrer"}
            </button>
          </section>
        </form>
      </div>
    </div>
  );
};

export type { SubmitPayload as ClientFormSubmitPayload };

import { FormEvent, useState } from "react";

import type { EmailTestPayload } from "../types";

interface EmailTestPanelProps {
  onSend: (payload: EmailTestPayload) => void;
  isSending: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onResetMessages: () => void;
}

const presetTemplates: Record<string, { subject: string; recipients: string; body: string }> = {
  mailhog: {
    subject: "[Mailhog] Test Biz Tracker",
    recipients: "test@example.com",
    body: [
      "Bonjour équipe,",
      "",
      "Ce message confirme que l'envoi SMTP via Mailhog fonctionne.",
      "Vérifiez la délivrance sur http://localhost:8025.",
      "",
      "--",
      "Biz Tracker",
    ].join("\n"),
  },
  mailjet: {
    subject: "[Mailjet] Test Biz Tracker",
    recipients: "alertes@votredomaine.fr",
    body: [
      "Bonjour équipe,",
      "",
      "Ce message valide la configuration Mailjet (API key + secret).",
      "Vous pouvez adapter le contenu avant envoi.",
      "",
      "--",
      "Biz Tracker",
    ].join("\n"),
  },
};

export const EmailTestPanel = ({ onSend, isSending, feedbackMessage, errorMessage, onResetMessages }: EmailTestPanelProps) => {
  const [subject, setSubject] = useState("");
  const [recipientsInput, setRecipientsInput] = useState("");
  const [body, setBody] = useState("Bonjour,\n\nCeci est un test Biz Tracker.\n\n--\nBiz Tracker\n");

  const parseRecipients = (value: string): string[] => {
    return value
      .split(/[\n,]+/)
      .map((entry) => entry.trim())
      .filter(Boolean);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onResetMessages();
    const payload: EmailTestPayload = {};
    if (subject.trim()) {
      payload.subject = subject.trim();
    }
    if (body.trim()) {
      payload.body = body;
    }
    const recipients = parseRecipients(recipientsInput);
    if (recipients.length > 0) {
      payload.recipients = recipients;
    }
    onSend(payload);
  };

  const handlePreset = (presetKey: keyof typeof presetTemplates) => {
    const preset = presetTemplates[presetKey];
    setSubject(preset.subject);
    setRecipientsInput(preset.recipients);
    setBody(preset.body);
    onResetMessages();
  };

  const handleReset = () => {
    setSubject("");
    setRecipientsInput("");
    setBody("Bonjour,\n\nCeci est un test Biz Tracker.\n\n--\nBiz Tracker\n");
    onResetMessages();
  };

  return (
    <article className="card">
      <div className="card-header">
        <div>
          <h2>Test d'envoi d'e-mail</h2>
          <p className="muted small">Déclenche l'endpoint /admin/email/test avec vos paramètres SMTP.</p>
        </div>
        <div className="card-actions">
          <button type="button" className="ghost" onClick={() => handlePreset("mailhog")} disabled={isSending}>
            Préremplir Mailhog
          </button>
          <button type="button" className="ghost" onClick={() => handlePreset("mailjet")} disabled={isSending}>
            Préremplir Mailjet
          </button>
        </div>
      </div>
      <form className="email-test-form" onSubmit={handleSubmit}>
        <label className="input-label" htmlFor="email-subject">
          Sujet (optionnel)
        </label>
        <input
          id="email-subject"
          type="text"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          placeholder="Ex. [Mailjet] Test Biz Tracker"
          disabled={isSending}
        />

        <label className="input-label" htmlFor="email-recipients">
          Destinataires de test (séparés par virgule ou retour à la ligne)
        </label>
        <textarea
          id="email-recipients"
          value={recipientsInput}
          onChange={(event) => setRecipientsInput(event.target.value)}
          placeholder="alertes@votredomaine.fr"
          rows={2}
          disabled={isSending}
        />

        <label className="input-label" htmlFor="email-body">
          Message (texte brut)
        </label>
        <textarea
          id="email-body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={8}
          disabled={isSending}
        />

        {feedbackMessage && (
          <p className="feedback success" role="status">
            {feedbackMessage}
          </p>
        )}
        {errorMessage && (
          <p className="feedback error" role="alert">
            {errorMessage}
          </p>
        )}

        <div className="card-actions">
          <button type="submit" className="primary" disabled={isSending}>
            {isSending ? "Envoi en cours..." : "Envoyer un e-mail de test"}
          </button>
          <button type="button" className="ghost" onClick={handleReset} disabled={isSending}>
            Réinitialiser
          </button>
        </div>
      </form>
      <p className="muted small">
        Astuce : basculez entre Mailhog et Mailjet en ajustant `EMAIL__PROVIDER` dans votre `.env`, puis relancez le backend.
      </p>
    </article>
  );
};

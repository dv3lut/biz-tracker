import { type FormEvent } from "react";

type Props = {
  isOpen: boolean;
  startDate: string;
  endDate: string;
  mode: "admin" | "client";
  isSubmitting: boolean;
  onClose: () => void;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onModeChange: (mode: "admin" | "client") => void;
  onSubmit: () => void;
};

export const GoogleExportModal = ({
  isOpen,
  startDate,
  endDate,
  mode,
  isSubmitting,
  onClose,
  onStartDateChange,
  onEndDateChange,
  onModeChange,
  onSubmit,
}: Props) => {
  if (!isOpen) {
    return null;
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

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
          <div className="modal-actions">
            <button type="button" className="ghost" onClick={onClose} disabled={isSubmitting}>
              Annuler
            </button>
            <button type="submit" className="primary" disabled={isSubmitting}>
              {isSubmitting ? "Export en cours..." : "Télécharger l'export"}
            </button>
          </div>
          <p className="muted small">Filtre appliqué sur la date de création Sirene.</p>
        </form>
      </div>
    </div>
  );
};

import { type FormEvent } from "react";
import type { ListingStatus } from "../types";
import { DEFAULT_LISTING_STATUSES, LISTING_STATUS_OPTIONS } from "../constants/listingStatuses";

type Props = {
  isOpen: boolean;
  startDate: string;
  endDate: string;
  mode: "admin" | "client";
  listingStatuses: ListingStatus[];
  isSubmitting: boolean;
  onClose: () => void;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onModeChange: (mode: "admin" | "client") => void;
  onListingStatusesChange: (statuses: ListingStatus[]) => void;
  onSubmit: () => void;
};

export const GoogleExportModal = ({
  isOpen,
  startDate,
  endDate,
  mode,
  listingStatuses,
  isSubmitting,
  onClose,
  onStartDateChange,
  onEndDateChange,
  onModeChange,
  onListingStatusesChange,
  onSubmit,
}: Props) => {
  if (!isOpen) {
    return null;
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
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

import { useEffect, useState } from "react";

import { SyncMode } from "../types";
import { describeSyncMode, syncModeIsGoogleOnly, syncModeSendsAlerts } from "../utils/sync";

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
];

type Props = {
  isOpen: boolean;
  initialMode: SyncMode;
  onConfirm: (mode: SyncMode) => void;
  onCancel: () => void;
  isSubmitting: boolean;
};

export const SyncModeModal = ({ isOpen, initialMode, onConfirm, onCancel, isSubmitting }: Props) => {
  const [mode, setMode] = useState<SyncMode>(initialMode);

  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
    }
  }, [initialMode, isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleSubmit = () => {
    onConfirm(mode);
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <header className="modal-header">
          <div>
            <h2>Choisir le mode de synchronisation</h2>
            <p className="muted small">Sélectionnez la portée avant de lancer un nouveau traitement.</p>
          </div>
          <button type="button" className="ghost" onClick={onCancel} disabled={isSubmitting}>
            Fermer
          </button>
        </header>

        <div className="modal-content">
          <div className="mode-options">
            {MODE_OPTIONS.map((option) => {
              const isSelected = option.value === mode;
              return (
                <label key={option.value} className={`mode-option${isSelected ? " selected" : ""}`}>
                  <div className="mode-option-header">
                    <input
                      type="radio"
                      name="sync-mode"
                      value={option.value}
                      checked={isSelected}
                      onChange={() => setMode(option.value)}
                      disabled={isSubmitting}
                    />
                    <div>
                      <strong>{option.title}</strong>
                      <p className="muted small">{option.description}</p>
                    </div>
                  </div>
                  <p className="muted small">{option.impact}</p>
                </label>
              );
            })}
          </div>
          <p className="muted small">Mode actuel : {describeSyncMode(mode)}</p>
          {mode === "sirene_only" ? (
            <p className="muted small">
              <strong>⚠️ Google désactivé :</strong> aucune fiche ne sera vérifiée ni enrichie pendant ce run.
            </p>
          ) : null}
          {syncModeIsGoogleOnly(mode) ? (
            <p className="muted small">
              <strong>ℹ️ Synchro Google uniquement :</strong> la collecte Sirene n'est pas exécutée.
            </p>
          ) : null}
          {mode === "google_refresh" ? (
            <p className="muted small warning">
              <strong>⚠️ Remise à zéro :</strong> toutes les correspondances Google existantes seront supprimées avant la relance et
              aucune alerte ne sera renvoyée.
            </p>
          ) : null}
          {mode === "google_pending" && syncModeSendsAlerts(mode) ? (
            <p className="muted small">
              <strong>Alertes actives :</strong> les clients seront notifiés pour les nouvelles fiches détectées.
            </p>
          ) : null}
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

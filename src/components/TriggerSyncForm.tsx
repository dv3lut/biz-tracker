import { ChangeEvent, FormEvent, useState } from "react";

import { SyncRequestPayload } from "../types";

type Props = {
  onTriggerFull: (payload: SyncRequestPayload) => void;
  onTriggerIncremental: () => void;
  isFullSyncLoading: boolean;
  isIncrementalLoading: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
};

const MAX_RECORDS_PRESETS = [100, 500, 1000, 5000];

export const TriggerSyncForm = ({
  onTriggerFull,
  onTriggerIncremental,
  isFullSyncLoading,
  isIncrementalLoading,
  feedbackMessage,
  errorMessage,
}: Props) => {
  const [resume, setResume] = useState(true);
  const [maxRecords, setMaxRecords] = useState<number | "">("");

  const handlePresetClick = (value: number) => {
    setMaxRecords(value);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload: SyncRequestPayload = {
      resume,
      maxRecords: maxRecords === "" ? null : Number(maxRecords),
    };
    onTriggerFull(payload);
  };

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Déclencher une synchronisation</h2>
          <p className="muted">Commandes directes sur l'orchestrateur de synchronisation.</p>
        </div>
      </header>

      <form className="sync-form" onSubmit={handleSubmit}>
        <div className="input-group">
          <span className="input-label">Reprendre si disponible</span>
          <div className="toggle-group">
            <label className={`toggle ${resume ? "active" : ""}`}>
              <input
                type="radio"
                name="resume"
                value="true"
                checked={resume}
                onChange={() => setResume(true)}
              />
              Oui
            </label>
            <label className={`toggle ${!resume ? "active" : ""}`}>
              <input
                type="radio"
                name="resume"
                value="false"
                checked={!resume}
                onChange={() => setResume(false)}
              />
              Non
            </label>
          </div>
          <p className="muted small">
            Si activé, relance la synchro à partir d'un run interrompu lorsque c'est possible.
          </p>
        </div>
        <div className="input-group">
          <span className="input-label">Nombre maximal d'enregistrements</span>
          <input
            type="number"
            min={1}
            placeholder="Illimité"
            value={maxRecords}
            onChange={(event: ChangeEvent<HTMLInputElement>) => {
              const value = event.target.value;
              setMaxRecords(value === "" ? "" : Number(value));
            }}
          />
          <div className="chip-list">
            {MAX_RECORDS_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                className={`chip ${maxRecords === preset ? "active" : ""}`}
                onClick={() => handlePresetClick(preset)}
              >
                {preset.toLocaleString("fr-FR")}
              </button>
            ))}
            <button
              type="button"
              className={`chip ${maxRecords === "" ? "active" : ""}`}
              onClick={() => setMaxRecords("")}
            >
              Illimité
            </button>
          </div>
          <p className="muted small">
            Laisser vide pour ne pas limiter le volume de traitement (équivalent à `max_records = null`).
          </p>
        </div>
        <div className="actions">
          <button type="submit" className="primary" disabled={isFullSyncLoading}>
            {isFullSyncLoading ? "Déclenchement..." : "Synchro complète"}
          </button>
          <button type="button" className="secondary" onClick={onTriggerIncremental} disabled={isIncrementalLoading}>
            {isIncrementalLoading ? "Déclenchement..." : "Synchro incrémentale"}
          </button>
        </div>
      </form>

      {feedbackMessage && <p className="feedback success">{feedbackMessage}</p>}
      {errorMessage && <p className="feedback error">{errorMessage}</p>}
    </section>
  );
};

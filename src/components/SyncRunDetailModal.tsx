import { SiretLink } from "./SiretLink";
import { SyncRun } from "../types";
import { formatDateTime, formatDuration, formatNumber } from "../utils/format";
import {
  describeDayReplayReference,
  describeSyncMode,
  formatNafCodesPreview,
  syncModeIsGoogleOnly,
  syncModeSupportsSirene,
} from "../utils/sync";
import { RunModeBadges } from "./RunModeBadges";

const formatDisplayDate = (isoDate: string | null | undefined): string => {
  if (!isoDate) {
    return "—";
  }
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) {
    return isoDate;
  }
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(date);
};

const formatDayLabel = (isoDate: string | null | undefined): string => {
  if (!isoDate) {
    return "—";
  }
  const source = isoDate.includes("T") ? isoDate : `${isoDate}T00:00:00Z`;
  return formatDisplayDate(source);
};

const formatLocation = (commune: string | null | undefined, postal: string | null | undefined): string => {
  const items = [postal, commune].filter(Boolean) as string[];
  return items.length > 0 ? items.join(" ") : "—";
};

type Props = {
  isOpen: boolean;
  date: string | null;
  runs: SyncRun[];
  selectedRunId: string | null;
  isLoading: boolean;
  errorMessage: string | null;
  onSelectRun: (runId: string) => void;
  onClose: () => void;
};

export const SyncRunDetailModal = ({
  isOpen,
  date,
  runs,
  selectedRunId,
  isLoading,
  errorMessage,
  onSelectRun,
  onClose,
}: Props) => {
  if (!isOpen) {
    return null;
  }

  const activeRun = runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null;
  const summary = activeRun?.summary ?? null;
  const stats = summary?.stats;
  const googleStats = stats?.google;
  const alertsStats = stats?.alerts;
  const samples = summary?.samples;
  const googleEnabled = googleStats?.enabled ?? activeRun?.googleEnabled ?? false;
  const sireneEnabled = activeRun ? syncModeSupportsSirene(activeRun.mode) : true;
  const isGoogleOnly = activeRun ? syncModeIsGoogleOnly(activeRun.mode) : false;

  return (
    <div className="modal-overlay">
      <div className="modal run-detail-modal">
        <header className="modal-header">
          <div>
            <h2>Synchro détaillée</h2>
            <p className="muted small">
              {!!date ? `Journée du ${formatDayLabel(date)}` : "Journée inconnue"}
            </p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Fermer
          </button>
        </header>

        <div className="modal-content">
          {isLoading ? <p>Chargement des informations…</p> : null}
          {!isLoading && errorMessage ? <p className="error">{errorMessage}</p> : null}

          {!isLoading && !errorMessage ? (
            runs.length === 0 ? (
              <p className="muted">Aucun run terminé pour cette journée.</p>
            ) : (
              <>
                {runs.length > 1 ? (
                  <div className="run-selector">
                    {runs.map((run) => (
                      <button
                        key={run.id}
                        type="button"
                        className={`run-selector-button${activeRun && run.id === activeRun.id ? " active" : ""}`}
                        onClick={() => onSelectRun(run.id)}
                      >
                        <span className="run-selector-title">{formatDateTime(run.startedAt)}</span>
                        <span className={`badge status-${run.status}`}>{run.status}</span>
                      </button>
                    ))}
                  </div>
                ) : null}

                {activeRun ? (
                  <div className="run-detail-grid">
                    <article className="insight-card">
                      <h3>Informations générales</h3>
                      <RunModeBadges
                        run={{
                          mode: activeRun.mode,
                          targetNafCodes: activeRun.targetNafCodes,
                          targetClientIds: activeRun.targetClientIds,
                          notifyAdmins: activeRun.notifyAdmins,
                          dayReplayForceGoogle: activeRun.dayReplayForceGoogle,
                          dayReplayReference: activeRun.dayReplayReference,
                        }}
                      />
                      <ul className="metric-list">
                        <li>
                          <strong>Début</strong> {formatDateTime(activeRun.startedAt)}
                        </li>
                        <li>
                          <strong>Fin</strong> {formatDateTime(activeRun.finishedAt)}
                        </li>
                        <li>
                          <strong>Durée</strong> {formatDuration(summary?.run.durationSeconds)}
                        </li>
                        <li>
                          <strong>Scope</strong> {activeRun.scopeKey}
                        </li>
                        <li>
                          <strong>Mode</strong> {describeSyncMode(activeRun.mode)}
                        </li>
                        {activeRun.mode === "day_replay" ? (
                          <li>
                            <strong>Référence rejeu</strong> {describeDayReplayReference(activeRun.dayReplayReference)}
                          </li>
                        ) : null}
                        <li>
                          <strong>Ciblage NAF</strong> {formatNafCodesPreview(activeRun.targetNafCodes, 8)}
                        </li>
                        {!sireneEnabled ? (
                          <li>
                            <strong>Note</strong> Synchro Google uniquement (aucune collecte Sirene).
                          </li>
                        ) : null}
                        <li>
                          <strong>Google Places</strong> {googleEnabled ? "Activé" : "Désactivé"}
                        </li>
                        <li>
                          <strong>Statut</strong> <span className={`badge status-${activeRun.status}`}>{activeRun.status}</span>
                        </li>
                        <li>
                          <strong>Pages</strong> {formatNumber(summary?.run.pageCount ?? null)}
                        </li>
                      </ul>
                    </article>

                    <article className="insight-card">
                      <h3>Volumes</h3>
                      {sireneEnabled ? (
                        <ul className="metric-list">
                          <li>
                            <strong>Nouveaux établissements</strong> {formatNumber(stats?.createdRecords ?? activeRun.createdRecords)}
                          </li>
                          <li>
                            <strong>Mises à jour</strong> {formatNumber(stats?.updatedRecords ?? activeRun.updatedRecords)}
                          </li>
                          <li>
                            <strong>Enregistrements traités</strong> {formatNumber(stats?.fetchedRecords ?? activeRun.fetchedRecords)}
                          </li>
                          <li>
                            <strong>Appels API</strong> {formatNumber(stats?.apiCallCount ?? activeRun.apiCallCount)}
                          </li>
                        </ul>
                      ) : (
                        <p className="muted small">Ce run n'a pas sollicité l'API Sirene.</p>
                      )}
                    </article>

                    <article className="insight-card">
                      <h3>Google Places</h3>
                      {googleEnabled ? (
                        <ul className="metric-list">
                          <li>
                            <strong>Appels API</strong> {formatNumber(googleStats?.apiCallCount ?? activeRun.googleApiCallCount)}
                          </li>
                          <li>
                            <strong>File d'attente</strong> {formatNumber(googleStats?.queueCount ?? activeRun.googleQueueCount)}
                          </li>
                          <li>
                            <strong>Éligibles</strong> {formatNumber(googleStats?.eligibleCount ?? activeRun.googleEligibleCount)}
                          </li>
                          <li>
                            <strong>Correspondances immédiates</strong> {formatNumber(googleStats?.immediateMatches ?? activeRun.googleImmediateMatchedCount)}
                          </li>
                          <li>
                            <strong>Correspondances tardives</strong> {formatNumber(googleStats?.lateMatches ?? activeRun.googleLateMatchedCount)}
                          </li>
                          <li>
                            <strong>Total trouvées</strong> {formatNumber(googleStats?.matchedCount ?? activeRun.googleMatchedCount)}
                          </li>
                          <li>
                            <strong>En attente</strong> {formatNumber(googleStats?.pendingCount ?? activeRun.googlePendingCount)}
                          </li>
                        </ul>
                      ) : (
                        <p className="muted small">Google désactivé pour ce run.</p>
                      )}
                    </article>

                    <article className="insight-card">
                      <h3>Alertes</h3>
                      <ul className="metric-list">
                        <li>
                          <strong>Créées</strong> {formatNumber(alertsStats?.created)}
                        </li>
                        <li>
                          <strong>Envoyées</strong> {formatNumber(alertsStats?.sent)}
                        </li>
                      </ul>
                      {isGoogleOnly ? (
                        <p className="muted small">
                          {activeRun.mode === "google_refresh"
                            ? "Les alertes sont désactivées pour une remise à zéro complète."
                            : "Les alertes sont émises uniquement pour les nouvelles fiches Google détectées."}
                        </p>
                      ) : null}
                    </article>
                  </div>
                ) : null}

                {activeRun ? (
                  <div className="run-samples-grid">
                    <section className="run-samples-section">
                      <h3>Nouveaux établissements (top 10)</h3>
                      {samples?.newEstablishments?.length ? (
                        <ul className="run-sample-list">
                          {samples.newEstablishments.map((item) => (
                            <li key={item.siret}>
                              <div className="run-sample-main">
                                <strong>{item.name ?? "Nom indisponible"}</strong>
                                 <SiretLink value={item.siret} className="muted small" />
                              </div>
                              <div className="run-sample-meta">
                                <span>{formatLocation(item.libelleCommune, item.codePostal)}</span>
                                <span className="muted small">Google: {item.googleStatus ?? "—"}</span>
                                {item.googlePlaceUrl ? (
                                  <a href={item.googlePlaceUrl} target="_blank" rel="noreferrer">
                                    Fiche Google
                                  </a>
                                ) : null}
                              </div>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted small">Aucun nouvel établissement échantillonné.</p>
                      )}
                    </section>

                    <section className="run-samples-section">
                      <h3>Établissements mis à jour (top 10)</h3>
                      {samples?.updatedEstablishments?.length ? (
                        <ul className="run-sample-list">
                          {samples.updatedEstablishments.map((item) => (
                            <li key={`${item.siret}-${item.changedFields.join("-")}`}>
                              <div className="run-sample-main">
                                <strong>{item.name ?? "Nom indisponible"}</strong>
                                 <SiretLink value={item.siret} className="muted small" />
                              </div>
                              <div className="run-sample-meta">
                                <span>{formatLocation(item.libelleCommune, item.codePostal)}</span>
                                <span className="muted small">Champs: {item.changedFields.join(", ")}</span>
                              </div>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted small">Aucun changement significatif recensé.</p>
                      )}
                    </section>

                    <section className="run-samples-section">
                      <h3>Correspondances Google immédiates</h3>
                      {samples?.googleImmediateMatches?.length ? (
                        <ul className="run-sample-list">
                          {samples.googleImmediateMatches.map((item) => (
                            <li key={`${item.siret}-immediate`}>
                              <div className="run-sample-main">
                                <strong>{item.name ?? "Nom indisponible"}</strong>
                                 <SiretLink value={item.siret} className="muted small" />
                              </div>
                              <div className="run-sample-meta">
                                <span>{formatLocation(item.libelleCommune, item.codePostal)}</span>
                                {item.googlePlaceUrl ? (
                                  <a href={item.googlePlaceUrl} target="_blank" rel="noreferrer">
                                    Fiche Google
                                  </a>
                                ) : null}
                              </div>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted small">Pas de correspondances immédiates sur l'échantillon.</p>
                      )}
                    </section>

                    <section className="run-samples-section">
                      <h3>Correspondances Google tardives</h3>
                      {samples?.googleLateMatches?.length ? (
                        <ul className="run-sample-list">
                          {samples.googleLateMatches.map((item) => (
                            <li key={`${item.siret}-late`}>
                              <div className="run-sample-main">
                                <strong>{item.name ?? "Nom indisponible"}</strong>
                                 <SiretLink value={item.siret} className="muted small" />
                              </div>
                              <div className="run-sample-meta">
                                <span>{formatLocation(item.libelleCommune, item.codePostal)}</span>
                                {item.googlePlaceUrl ? (
                                  <a href={item.googlePlaceUrl} target="_blank" rel="noreferrer">
                                    Fiche Google
                                  </a>
                                ) : null}
                              </div>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted small">Pas de correspondances tardives sur l'échantillon.</p>
                      )}
                    </section>
                  </div>
                ) : null}
              </>
            )
          ) : null}
        </div>
      </div>
    </div>
  );
};

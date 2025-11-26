import { DashboardMetrics } from "../../types";
import { formatDateTime, formatNumber } from "../../utils/format";

type DashboardSummaryCardsProps = {
  metrics: DashboardMetrics;
};

export const DashboardSummaryCards = ({ metrics }: DashboardSummaryCardsProps) => {
  return (
    <div className="insight-grid">
      <article className="insight-card">
        <h3>Dernier run</h3>
        {metrics.latestRun && metrics.latestRunBreakdown ? (
          <>
            <p className="muted small">Demarre le {formatDateTime(metrics.latestRun.startedAt)}</p>
            <ul className="metric-list">
              <li>
                <strong>{formatNumber(metrics.latestRunBreakdown.createdRecords)}</strong> nouveaux etablissements
              </li>
              <li>
                <strong>{formatNumber(metrics.latestRunBreakdown.updatedRecords)}</strong> etablissements mis a jour
              </li>
              <li>
                <strong>{formatNumber(metrics.latestRunBreakdown.apiCallCount)}</strong> appels API
              </li>
              <li>
                <strong>{formatNumber(metrics.latestRunBreakdown.googleApiCallCount)}</strong> appels Google
              </li>
              <li>
                <strong>{formatNumber(metrics.latestRunBreakdown.alertsSent)}</strong> alertes envoyees
              </li>
            </ul>
          </>
        ) : (
          <p className="muted">Aucun run termine a ce jour.</p>
        )}
      </article>

      <article className="insight-card">
        <h3>Google (dernier run)</h3>
        {metrics.latestRunBreakdown ? (
          <ul className="metric-list">
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.googleApiCallCount)}</strong> appels API
            </li>
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.googleFound)}</strong> fiches trouvees (immediate)
            </li>
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.googleFoundLate)}</strong> fiches trouvees (rattrapage)
            </li>
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.googleNotFound)}</strong> sans resultat
            </li>
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.googleInsufficient)}</strong> identite insuffisante
            </li>
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.googlePending)}</strong> en attente
            </li>
            {metrics.latestRunBreakdown.googleOther > 0 ? (
              <li>
                <strong>{formatNumber(metrics.latestRunBreakdown.googleOther)}</strong> autres statuts
              </li>
            ) : null}
          </ul>
        ) : (
          <p className="muted">Aucun enrichissement recense.</p>
        )}
      </article>

      <article className="insight-card">
        <h3>Anciennete des fiches (dernier run)</h3>
        {metrics.latestRunBreakdown ? (
          <ul className="metric-list">
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.listingRecent)}</strong> creation recente
            </li>
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.listingRecentMissingContact)}</strong> creation recente sans contact
            </li>
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.listingNotRecent)}</strong> creation ancienne
            </li>
            <li>
              <strong>{formatNumber(metrics.latestRunBreakdown.listingUnknown)}</strong> statut inconnu
            </li>
          </ul>
        ) : (
          <p className="muted">Aucun enrichissement recense.</p>
        )}
      </article>

      <article className="insight-card">
        <h3>Google (global)</h3>
        <ul className="metric-list">
          <li>
            <strong>{formatNumber(metrics.googleStatusBreakdown.found)}</strong> fiches trouvees
          </li>
          <li>
            <strong>{formatNumber(metrics.googleStatusBreakdown.notFound)}</strong> sans resultat
          </li>
          <li>
            <strong>{formatNumber(metrics.googleStatusBreakdown.insufficient)}</strong> identite insuffisante
          </li>
          <li>
            <strong>{formatNumber(metrics.googleStatusBreakdown.pending)}</strong> en attente
          </li>
          {metrics.googleStatusBreakdown.other > 0 ? (
            <li>
              <strong>{formatNumber(metrics.googleStatusBreakdown.other)}</strong> autres statuts
            </li>
          ) : null}
        </ul>
      </article>

      <article className="insight-card">
        <h3>Anciennete des fiches Google</h3>
        {metrics.listingAgeBreakdown ? (
          <ul className="metric-list">
            <li>
              <strong>{formatNumber(metrics.listingAgeBreakdown.recentCreation)}</strong> creation recente
            </li>
            <li>
              <strong>{formatNumber(metrics.listingAgeBreakdown.recentCreationMissingContact)}</strong> creation recente sans contact
            </li>
            <li>
              <strong>{formatNumber(metrics.listingAgeBreakdown.notRecentCreation)}</strong> creation ancienne
            </li>
            <li>
              <strong>{formatNumber(metrics.listingAgeBreakdown.unknown)}</strong> statut inconnu
            </li>
          </ul>
        ) : (
          <p className="muted">Aucune donnee disponible.</p>
        )}
      </article>

      <article className="insight-card">
        <h3>Statuts etablissements</h3>
        {Object.keys(metrics.establishmentStatusBreakdown).length > 0 ? (
          <ul className="metric-list">
            {Object.entries(metrics.establishmentStatusBreakdown)
              .sort((a, b) => a[0].localeCompare(b[0]))
              .map(([status, count]) => (
                <li key={status}>
                  <strong>{formatNumber(count)}</strong> statut {status}
                </li>
              ))}
          </ul>
        ) : (
          <p className="muted">Aucun etablissements enregistre.</p>
        )}
      </article>
    </div>
  );
};

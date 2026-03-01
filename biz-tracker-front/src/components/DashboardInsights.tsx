import { DashboardMetrics } from "../types";

import { AlertsChartCard } from "./dashboard/AlertsChartCard";
import { ApiVolumeChartCard } from "./dashboard/ApiVolumeChartCard";
import { DashboardSummaryCards } from "./dashboard/DashboardSummaryCards";
import { GoogleStatusesChartCard } from "./dashboard/GoogleStatusesChartCard";
import { RunOutcomesChartCard } from "./dashboard/RunOutcomesChartCard";
import { useDashboardChartData } from "./dashboard/useDashboardChartData";

type DashboardInsightsProps = {
  metrics?: DashboardMetrics;
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
  isRefreshing: boolean;
  days: number;
  onSelectDay?: (isoDate: string) => void;
  selectedDay?: string | null;
};

export const DashboardInsights = ({
  metrics,
  isLoading,
  error,
  onRefresh,
  isRefreshing,
  days,
  onSelectDay,
  selectedDay,
}: DashboardInsightsProps) => {
  const {
    runOutcomeChartData,
    apiActivityChartData,
    alertsChartData,
    googleStatusChartData,
    hasRunOutcomeData,
    hasApiData,
    hasAlertsData,
    hasGoogleStatusData,
  } = useDashboardChartData(metrics, days);

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Monitoring quotidien</h2>
          <p className="muted">Vue synthetique des synchronisations, des appels API et des alertes recents.</p>
        </div>
        <div className="card-actions">
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Rafraichir
          </button>
        </div>
      </header>

      {isRefreshing && !isLoading ? <p className="refresh-indicator">Actualisation en cours…</p> : null}
      {isLoading ? <p>Chargement...</p> : null}
      {error ? <p className="error">{error.message}</p> : null}

      {metrics && !isLoading && !error ? (
        <>
          <DashboardSummaryCards metrics={metrics} />

          <div className="charts-grid">
            <RunOutcomesChartCard
              data={runOutcomeChartData}
              hasData={hasRunOutcomeData}
              onSelectDay={onSelectDay}
              selectedDay={selectedDay}
            />
            <ApiVolumeChartCard
              data={apiActivityChartData}
              hasData={hasApiData}
              onSelectDay={onSelectDay}
              selectedDay={selectedDay}
            />
          </div>

          <div className="charts-grid">
            <GoogleStatusesChartCard
              data={googleStatusChartData}
              hasData={hasGoogleStatusData}
              onSelectDay={onSelectDay}
              selectedDay={selectedDay}
            />
            <AlertsChartCard
              data={alertsChartData}
              hasData={hasAlertsData}
              onSelectDay={onSelectDay}
              selectedDay={selectedDay}
            />
          </div>
        </>
      ) : null}
    </section>
  );
};

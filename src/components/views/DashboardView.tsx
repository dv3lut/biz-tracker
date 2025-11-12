import { StatsSummaryCard } from "../StatsSummaryCard";
import { DashboardInsights } from "../DashboardInsights";
import type { DashboardMetrics, StatsSummary } from "../../types";

export type DashboardViewProps = {
  stats: StatsSummary | undefined;
  isStatsLoading: boolean;
  statsError: Error | null;
  onRefreshStats: () => void;
  onTriggerSync: () => void;
  isTriggeringSync: boolean;
  onExportGooglePlaces: () => void;
  isExportingGooglePlaces: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
  isStatsRefreshing: boolean;
  metrics: DashboardMetrics | undefined;
  isMetricsLoading: boolean;
  metricsError: Error | null;
  onRefreshMetrics: () => void;
  isMetricsRefreshing: boolean;
  days: number;
  onSelectDay: (isoDate: string) => void;
  selectedDay: string | null;
  hasActiveRun: boolean;
};

export const DashboardView = ({
  stats,
  isStatsLoading,
  statsError,
  onRefreshStats,
  onTriggerSync,
  isTriggeringSync,
  onExportGooglePlaces,
  isExportingGooglePlaces,
  feedbackMessage,
  errorMessage,
  isStatsRefreshing,
  metrics,
  isMetricsLoading,
  metricsError,
  onRefreshMetrics,
  isMetricsRefreshing,
  days,
  onSelectDay,
  selectedDay,
  hasActiveRun,
}: DashboardViewProps) => {
  return (
    <section className="dashboard-section">
      <div className="section-grid">
        <StatsSummaryCard
          summary={stats}
          isLoading={isStatsLoading}
          error={statsError}
          onRefresh={onRefreshStats}
          onTriggerSync={onTriggerSync}
          isTriggering={isTriggeringSync}
          onExportGooglePlaces={onExportGooglePlaces}
          isExportingGooglePlaces={isExportingGooglePlaces}
          feedbackMessage={feedbackMessage}
          errorMessage={errorMessage}
          isRefreshing={hasActiveRun && isStatsRefreshing}
        />
        <DashboardInsights
          metrics={metrics}
          isLoading={isMetricsLoading}
          error={metricsError}
          onRefresh={onRefreshMetrics}
          isRefreshing={hasActiveRun && isMetricsRefreshing}
          days={days}
          onSelectDay={onSelectDay}
          selectedDay={selectedDay}
        />
      </div>
    </section>
  );
};

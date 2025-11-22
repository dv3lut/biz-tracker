import { StatsSummaryCard } from "../StatsSummaryCard";
import { DashboardInsights } from "../DashboardInsights";
import { GoogleRetryConfigCard } from "../GoogleRetryConfigCard";
import type { DashboardMetrics, GoogleRetryConfig, StatsSummary } from "../../types";

export type DashboardViewProps = {
  stats: StatsSummary | undefined;
  isStatsLoading: boolean;
  statsError: Error | null;
  onRefreshStats: () => void;
  onTriggerSync: () => void;
  isTriggeringSync: boolean;
  onOpenGoogleExportModal: () => void;
  isExportingGooglePlaces: boolean;
  googleRetryConfig: GoogleRetryConfig | undefined;
  isGoogleRetryConfigLoading: boolean;
  isGoogleRetryConfigRefreshing: boolean;
  googleRetryConfigError: Error | null;
  onRefreshGoogleRetryConfig: () => void;
  onSubmitGoogleRetryConfig: (payload: GoogleRetryConfig) => void;
  isSavingGoogleRetryConfig: boolean;
  googleRetryConfigFeedback: string | null;
  googleRetryConfigMessageError: string | null;
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
  onOpenGoogleExportModal,
  isExportingGooglePlaces,
  googleRetryConfig,
  isGoogleRetryConfigLoading,
  isGoogleRetryConfigRefreshing,
  googleRetryConfigError,
  onRefreshGoogleRetryConfig,
  onSubmitGoogleRetryConfig,
  isSavingGoogleRetryConfig,
  googleRetryConfigFeedback,
  googleRetryConfigMessageError,
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
          onOpenGoogleExportModal={onOpenGoogleExportModal}
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
      <GoogleRetryConfigCard
        config={googleRetryConfig}
        isLoading={isGoogleRetryConfigLoading}
        isRefreshing={isGoogleRetryConfigRefreshing}
        error={googleRetryConfigError}
        onRefresh={onRefreshGoogleRetryConfig}
        onSubmit={onSubmitGoogleRetryConfig}
        isSubmitting={isSavingGoogleRetryConfig}
        feedbackMessage={googleRetryConfigFeedback}
        errorMessage={googleRetryConfigMessageError}
      />
    </section>
  );
};

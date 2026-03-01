import { StatsSummaryCard } from "../StatsSummaryCard";
import { DashboardInsights } from "../DashboardInsights";
import { StatisticsPanel } from "../StatisticsPanel";
import { GoogleRetryConfigCard } from "../GoogleRetryConfigCard";
import { ManualGoogleCheckCard } from "../ManualGoogleCheckCard";
import type { DashboardMetrics, GoogleCheckResult, GoogleRetryConfig, StatsSummary } from "../../types";

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
  manualGoogleSiret: string;
  manualGoogleFeedback: string | null;
  manualGoogleError: string | null;
  manualGoogleResult: GoogleCheckResult | null;
  onManualGoogleSiretChange: (value: string) => void;
  onManualGoogleCheck: (siret: string) => void;
  manualGoogleNotify: boolean;
  onManualGoogleNotifyChange: (value: boolean) => void;
  isManualGoogleCheckPending: boolean;
  isGoogleCheckPending: boolean;
  checkingGoogleSiret: string | null;
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
  manualGoogleSiret,
  manualGoogleFeedback,
  manualGoogleError,
  manualGoogleResult,
  onManualGoogleSiretChange,
  onManualGoogleCheck,
  manualGoogleNotify,
  onManualGoogleNotifyChange,
  isManualGoogleCheckPending,
  isGoogleCheckPending,
  checkingGoogleSiret,
}: DashboardViewProps) => {
  return (
    <section className="dashboard-section">
      <div className="dashboard-grid">
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
        <StatisticsPanel
          categories={metrics?.nafCategoryBreakdown ?? []}
          isLoading={isMetricsLoading}
          error={metricsError}
          onRefresh={onRefreshMetrics}
          isRefreshing={hasActiveRun && isMetricsRefreshing}
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
        <ManualGoogleCheckCard
          siret={manualGoogleSiret}
          onSiretChange={onManualGoogleSiretChange}
          onSubmit={onManualGoogleCheck}
          notify={manualGoogleNotify}
          onNotifyChange={onManualGoogleNotifyChange}
          isSubmitting={isManualGoogleCheckPending}
          isGlobalSubmitting={isGoogleCheckPending}
          checkingGoogleSiret={checkingGoogleSiret}
          feedbackMessage={manualGoogleFeedback}
          errorMessage={manualGoogleError}
          result={manualGoogleResult}
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

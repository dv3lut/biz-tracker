import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, clientsApi, googleApi, statsApi, syncApi } from "../../api";
import { DEFAULT_LISTING_STATUSES } from "../../constants/listingStatuses";
import type {
  Client,
  DashboardMetrics,
  DayReplayReference,
  GoogleCheckResult,
  GoogleRetryConfig,
  StatsSummary,
  SyncMode,
  SyncRun,
  SyncRequestPayload,
} from "../../types";
import { DashboardView } from "../../components/views/DashboardView";
import { SyncRunDetailModal } from "../../components/SyncRunDetailModal";
import { SyncModeModal } from "../../components/SyncModeModal";
import { GoogleExportModal } from "../../components/GoogleExportModal";
import { useRefreshIndicator } from "../../hooks/useRefreshIndicator";

const DASHBOARD_DAYS = 30;
const GOOGLE_EXPORT_DEFAULT_WINDOW_DAYS = 30;
const RUN_HISTORY_LIMIT = 100;
const DEFAULT_REPLAY_REFERENCE: DayReplayReference = "creation_date";

const runMatchesDay = (run: SyncRun, isoDate: string): boolean => {
  if (!run.startedAt) {
    return false;
  }
  return run.startedAt.slice(0, 10) === isoDate;
};

const getDefaultGoogleExportRange = () => {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - GOOGLE_EXPORT_DEFAULT_WINDOW_DAYS);
  const format = (value: Date) => value.toISOString().slice(0, 10);
  return { start: format(start), end: format(end) };
};

type RunDetailModalState = {
  isOpen: boolean;
  date: string | null;
  runs: SyncRun[];
  selectedRunId: string | null;
  isLoading: boolean;
  error: string | null;
};

type Props = {
  onUnauthorized: () => void;
};

export const DashboardSection = ({ onUnauthorized }: Props) => {
  const queryClient = useQueryClient();
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [runDetailModal, setRunDetailModal] = useState<RunDetailModalState | null>(null);
  type SyncTriggerSelection = SyncRequestPayload & { mode: SyncMode };
  const [isSyncModeModalOpen, setSyncModeModalOpen] = useState(false);
  const [pendingSyncRequest, setPendingSyncRequest] = useState<SyncTriggerSelection>({
    mode: "full",
    notifyAdmins: true,
    replayReference: DEFAULT_REPLAY_REFERENCE,
    forceGoogleReplay: false,
    googleStatuses: [],
  });
  const [isGoogleExportModalOpen, setGoogleExportModalOpen] = useState(false);
  const initialExportRange = useMemo(getDefaultGoogleExportRange, []);
  const [googleExportStartDate, setGoogleExportStartDate] = useState(initialExportRange.start);
  const [googleExportEndDate, setGoogleExportEndDate] = useState(initialExportRange.end);
  const [googleExportMode, setGoogleExportMode] = useState<"admin" | "client">("client");
  const [googleExportListingStatuses, setGoogleExportListingStatuses] = useState(() => [...DEFAULT_LISTING_STATUSES]);
  const [isExportingGooglePlaces, setIsExportingGooglePlaces] = useState(false);
  const [manualGoogleSiret, setManualGoogleSiret] = useState("");
  const [manualGoogleNotify, setManualGoogleNotify] = useState(false);
  const [manualGoogleFeedback, setManualGoogleFeedback] = useState<string | null>(null);
  const [manualGoogleError, setManualGoogleError] = useState<string | null>(null);
  const [manualGoogleResult, setManualGoogleResult] = useState<GoogleCheckResult | null>(null);

  const statsQuery = useQuery<StatsSummary>({
    queryKey: ["stats-summary"],
    queryFn: () => statsApi.fetchSummary(),
  });

  const dashboardQuery = useQuery<DashboardMetrics>({
    queryKey: ["dashboard-metrics", DASHBOARD_DAYS],
    queryFn: () => statsApi.fetchDashboardMetrics(DASHBOARD_DAYS),
  });

  const googleRetryConfigQuery = useQuery<GoogleRetryConfig>({
    queryKey: ["google-retry-config"],
    queryFn: () => googleApi.fetchRetryConfig(),
  });

  const googleStatusesQuery = useQuery<string[]>({
    queryKey: ["google-check-statuses"],
    queryFn: () => googleApi.fetchCheckStatuses(),
  });

  const syncRunsQuery = useQuery<SyncRun[]>({
    queryKey: ["sync-runs", 10],
    queryFn: () => syncApi.fetchRuns(10),
  });

  const clientsQuery = useQuery<Client[]>({
    queryKey: ["clients"],
    queryFn: () => clientsApi.list(),
    staleTime: 5 * 60 * 1000,
  });

  const hasActiveRun = syncRunsQuery.data?.some((run) => run.status === "running" || run.status === "pending") ?? false;
  const statsIsRefreshing = useRefreshIndicator(statsQuery.isFetching && !statsQuery.isLoading);
  const metricsIsRefreshing = useRefreshIndicator(dashboardQuery.isFetching && !dashboardQuery.isLoading);
  const googleRetryConfigIsRefreshing = useRefreshIndicator(
    googleRetryConfigQuery.isFetching && !googleRetryConfigQuery.isLoading,
  );

  const showError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
      setErrorMessage(message);
      setFeedbackMessage(null);
    },
    [onUnauthorized],
  );

  const syncMutation = useMutation({
    mutationFn: (payload: SyncRequestPayload) => syncApi.trigger(payload),
    onSuccess: (result) => {
      const detail = result.detail ? `: ${result.detail}` : "";
      setFeedbackMessage(`Synchro acceptée${detail}`);
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ["stats-summary"] });
      queryClient.invalidateQueries({ queryKey: ["sync-runs"] });
      queryClient.invalidateQueries({ queryKey: ["sync-state"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] });
    },
    onError: showError,
  });

  const updateGoogleRetryConfigMutation = useMutation({
    mutationFn: (payload: GoogleRetryConfig) => googleApi.updateRetryConfig(payload),
    onSuccess: (config) => {
      queryClient.setQueryData(["google-retry-config"], config);
      setFeedbackMessage("Configuration Google mise à jour.");
      setErrorMessage(null);
    },
    onError: showError,
  });

  const manualGoogleCheckMutation = useMutation({
    mutationFn: (siret: string) =>
      googleApi.checkEstablishment(siret, {
        notifyClients: manualGoogleNotify,
      }),
    onSuccess: (result) => {
      const message = result.message || `Vérification Google relancée pour ${manualGoogleSiret}.`;
      setManualGoogleFeedback(message);
      setManualGoogleError(null);
      setManualGoogleResult(result);
      setManualGoogleSiret("");
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["establishments"] });
      queryClient.invalidateQueries({ queryKey: ["establishment-detail"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "La vérification Google a échoué.";
      setManualGoogleError(message);
      setManualGoogleFeedback(null);
      setManualGoogleResult(null);
    },
  });

  const handleManualGoogleCheck = useCallback(() => {
    if (!manualGoogleSiret.trim()) {
      setManualGoogleError("Merci de saisir un SIRET valide.");
      setManualGoogleFeedback(null);
      return;
    }
    manualGoogleCheckMutation.mutate(manualGoogleSiret.trim());
  }, [manualGoogleSiret, manualGoogleCheckMutation]);

  const handleTriggerSync = useCallback(() => {
    setSyncModeModalOpen(true);
  }, []);

  const handleConfirmSyncMode = useCallback(
    (payload: SyncTriggerSelection) => {
      const persistedRequest: SyncTriggerSelection = {
        ...payload,
        notifyAdmins: payload.notifyAdmins ?? pendingSyncRequest.notifyAdmins ?? true,
        forceGoogleReplay: payload.forceGoogleReplay ?? pendingSyncRequest.forceGoogleReplay ?? false,
        replayReference: payload.replayReference ?? pendingSyncRequest.replayReference ?? DEFAULT_REPLAY_REFERENCE,
        googleStatuses: payload.googleStatuses ?? pendingSyncRequest.googleStatuses ?? [],
      };
      setPendingSyncRequest(persistedRequest);
      syncMutation.mutate(payload);
      setSyncModeModalOpen(false);
    },
    [
      pendingSyncRequest.forceGoogleReplay,
      pendingSyncRequest.notifyAdmins,
      pendingSyncRequest.replayReference,
      pendingSyncRequest.googleStatuses,
      syncMutation,
    ],
  );

  const handleCloseSyncModeModal = useCallback(() => {
    setSyncModeModalOpen(false);
  }, []);

  const handleDashboardDaySelect = useCallback(
    async (isoDate: string) => {
      setRunDetailModal({
        isOpen: true,
        date: isoDate,
        runs: [],
        selectedRunId: null,
        isLoading: true,
        error: null,
      });

      const cachedRuns = (syncRunsQuery.data ?? []).filter((run) => runMatchesDay(run, isoDate));
      if (cachedRuns.length > 0) {
        setRunDetailModal({
          isOpen: true,
          date: isoDate,
          runs: cachedRuns,
          selectedRunId: cachedRuns[0]?.id ?? null,
          isLoading: false,
          error: null,
        });
        return;
      }

      try {
        const runs = await syncApi.fetchRuns(RUN_HISTORY_LIMIT);
        const matches = runs.filter((run) => runMatchesDay(run, isoDate));
        setRunDetailModal({
          isOpen: true,
          date: isoDate,
          runs: matches,
          selectedRunId: matches[0]?.id ?? null,
          isLoading: false,
          error: matches.length === 0 ? "Aucun run trouvé pour cette journée dans l'historique." : null,
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 403) {
          onUnauthorized();
          setRunDetailModal(null);
          return;
        }
        const message = error instanceof ApiError ? error.message : "Impossible de charger le détail de cette synchro.";
        setRunDetailModal({
          isOpen: true,
          date: isoDate,
          runs: [],
          selectedRunId: null,
          isLoading: false,
          error: message,
        });
      }
    },
    [onUnauthorized, syncRunsQuery.data],
  );

  const handleOpenGoogleExportModal = useCallback(() => {
    setFeedbackMessage(null);
    setErrorMessage(null);
    setGoogleExportModalOpen(true);
  }, []);

  const resetGoogleExportRange = useCallback(() => {
    const { start, end } = getDefaultGoogleExportRange();
    setGoogleExportStartDate(start);
    setGoogleExportEndDate(end);
    setGoogleExportListingStatuses([...DEFAULT_LISTING_STATUSES]);
  }, []);

  const handleConfirmGoogleExport = useCallback(async (nafCodes?: string[]) => {
    if (googleExportListingStatuses.length === 0) {
      setErrorMessage("Merci de sélectionner au moins un statut de fiche Google.");
      setFeedbackMessage(null);
      return;
    }
    setIsExportingGooglePlaces(true);
    try {
      const blob = await googleApi.exportPlaces({
        startDate: googleExportStartDate,
        endDate: googleExportEndDate,
        mode: googleExportMode,
        listingStatuses: googleExportListingStatuses,
        nafCodes: nafCodes && nafCodes.length > 0 ? nafCodes : undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      const today = new Date().toISOString().slice(0, 10);
      anchor.download = `business-tracker-google-places-${googleExportMode}-${today}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setFeedbackMessage("Export Google Places téléchargé.");
      setErrorMessage(null);
      setGoogleExportModalOpen(false);
    } catch (error) {
      showError(error);
    } finally {
      setIsExportingGooglePlaces(false);
    }
  }, [
    googleExportStartDate,
    googleExportEndDate,
    googleExportMode,
    googleExportListingStatuses,
    showError,
  ]);

  const handleCloseGoogleExportModal = useCallback(() => {
    setGoogleExportModalOpen(false);
  }, []);

  const handleSelectRunFromModal = useCallback((runId: string) => {
    setRunDetailModal((current) => {
      if (!current) {
        return current;
      }
      return { ...current, selectedRunId: runId };
    });
  }, []);

  const handleCloseRunDetailModal = useCallback(() => {
    setRunDetailModal(null);
  }, []);

  const statsError = statsQuery.error instanceof Error ? statsQuery.error : null;
  const metricsError = dashboardQuery.error instanceof Error ? dashboardQuery.error : null;
  const googleRetryConfigError = googleRetryConfigQuery.error instanceof Error ? googleRetryConfigQuery.error : null;
  const clientsError = clientsQuery.error instanceof Error ? clientsQuery.error : null;

  useEffect(() => {
    if (clientsQuery.error instanceof ApiError && clientsQuery.error.status === 403) {
      onUnauthorized();
    }
  }, [clientsQuery.error, onUnauthorized]);

  useEffect(() => {
    if (googleStatusesQuery.error instanceof ApiError && googleStatusesQuery.error.status === 403) {
      onUnauthorized();
    }
  }, [googleStatusesQuery.error, onUnauthorized]);

  const manualGoogleCheckState = useMemo(
    () => ({
      siret: manualGoogleSiret,
      notify: manualGoogleNotify,
      feedback: manualGoogleFeedback,
      error: manualGoogleError,
      result: manualGoogleResult,
    }),
    [manualGoogleSiret, manualGoogleNotify, manualGoogleFeedback, manualGoogleError, manualGoogleResult],
  );

  return (
    <>
      <DashboardView
        stats={statsQuery.data}
        isStatsLoading={statsQuery.isLoading}
        statsError={statsError}
        onRefreshStats={() => statsQuery.refetch()}
        onTriggerSync={handleTriggerSync}
        isTriggeringSync={syncMutation.isPending}
        onOpenGoogleExportModal={handleOpenGoogleExportModal}
        isExportingGooglePlaces={isExportingGooglePlaces}
        googleRetryConfig={googleRetryConfigQuery.data}
        isGoogleRetryConfigLoading={googleRetryConfigQuery.isLoading}
        isGoogleRetryConfigRefreshing={googleRetryConfigIsRefreshing}
        googleRetryConfigError={googleRetryConfigError}
        onRefreshGoogleRetryConfig={() => googleRetryConfigQuery.refetch()}
        onSubmitGoogleRetryConfig={(payload) => updateGoogleRetryConfigMutation.mutate(payload)}
        isSavingGoogleRetryConfig={updateGoogleRetryConfigMutation.isPending}
        googleRetryConfigFeedback={feedbackMessage}
        googleRetryConfigMessageError={errorMessage}
        feedbackMessage={feedbackMessage}
        errorMessage={errorMessage}
        isStatsRefreshing={statsIsRefreshing}
        metrics={dashboardQuery.data}
        isMetricsLoading={dashboardQuery.isLoading}
        metricsError={metricsError}
        onRefreshMetrics={() => dashboardQuery.refetch()}
        isMetricsRefreshing={metricsIsRefreshing}
        days={DASHBOARD_DAYS}
        onSelectDay={handleDashboardDaySelect}
        selectedDay={runDetailModal?.date ?? null}
        hasActiveRun={hasActiveRun}
        manualGoogleSiret={manualGoogleCheckState.siret}
        manualGoogleFeedback={manualGoogleCheckState.feedback}
        manualGoogleError={manualGoogleCheckState.error}
        manualGoogleResult={manualGoogleCheckState.result}
        onManualGoogleSiretChange={setManualGoogleSiret}
        onManualGoogleCheck={handleManualGoogleCheck}
        manualGoogleNotify={manualGoogleCheckState.notify}
        onManualGoogleNotifyChange={setManualGoogleNotify}
        isManualGoogleCheckPending={manualGoogleCheckMutation.isPending}
        isGoogleCheckPending={manualGoogleCheckMutation.isPending}
        checkingGoogleSiret={manualGoogleCheckMutation.isPending ? manualGoogleSiret : null}
      />

      <SyncRunDetailModal
        isOpen={Boolean(runDetailModal?.isOpen)}
        date={runDetailModal?.date ?? null}
        runs={runDetailModal?.runs ?? []}
        selectedRunId={runDetailModal?.selectedRunId ?? null}
        isLoading={runDetailModal?.isLoading ?? false}
        errorMessage={runDetailModal?.error ?? null}
        onSelectRun={handleSelectRunFromModal}
        onClose={handleCloseRunDetailModal}
      />

      <SyncModeModal
        isOpen={isSyncModeModalOpen}
        initialMode={pendingSyncRequest.mode}
        initialReplayDate={pendingSyncRequest.replayForDate ?? null}
        initialNafCodes={pendingSyncRequest.nafCodes ?? []}
        nafCategories={dashboardQuery.data?.nafCategoryBreakdown ?? []}
        initialTargetClientIds={pendingSyncRequest.targetClientIds ?? null}
        initialNotifyAdmins={pendingSyncRequest.notifyAdmins}
        initialForceGoogleReplay={pendingSyncRequest.forceGoogleReplay ?? false}
        initialReplayReference={pendingSyncRequest.replayReference ?? DEFAULT_REPLAY_REFERENCE}
        initialGoogleStatuses={pendingSyncRequest.googleStatuses ?? []}
        googleStatuses={googleStatusesQuery.data ?? []}
        isGoogleStatusesLoading={googleStatusesQuery.isLoading}
        googleStatusesError={googleStatusesQuery.error instanceof Error ? googleStatusesQuery.error.message : null}
        clients={clientsQuery.data ?? []}
        isClientsLoading={clientsQuery.isLoading}
        clientsError={clientsError?.message ?? null}
        onConfirm={handleConfirmSyncMode}
        onCancel={handleCloseSyncModeModal}
        isSubmitting={syncMutation.isPending}
      />

      <GoogleExportModal
        isOpen={isGoogleExportModalOpen}
        startDate={googleExportStartDate}
        endDate={googleExportEndDate}
        mode={googleExportMode}
        listingStatuses={googleExportListingStatuses}
        nafCategories={dashboardQuery.data?.nafCategoryBreakdown ?? []}
        isSubmitting={isExportingGooglePlaces}
        onClose={handleCloseGoogleExportModal}
        onStartDateChange={setGoogleExportStartDate}
        onEndDateChange={setGoogleExportEndDate}
        onModeChange={setGoogleExportMode}
        onListingStatusesChange={setGoogleExportListingStatuses}
        onSubmit={handleConfirmGoogleExport}
      />
    </>
  );
};

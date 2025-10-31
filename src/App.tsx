import { useEffect, useState, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  adminApi,
  ApiError,
  type TriggerSyncResult,
  getAdminToken,
  setAdminToken,
  clearAdminToken,
} from "./api/client";
import { AdminTokenPrompt } from "./components/AdminTokenPrompt";
import { TriggerSyncForm } from "./components/TriggerSyncForm";
import { StatsSummaryCard } from "./components/StatsSummaryCard";
import { SyncRunsTable } from "./components/SyncRunsTable";
import { SyncStateTable } from "./components/SyncStateTable";
import { AlertsList } from "./components/AlertsList";
import { SyncRequestPayload } from "./types";

const REFRESH_LONG = 60_000;
const REFRESH_SHORT = 30_000;

const isUnauthorizedError = (error: unknown): error is ApiError => {
  return error instanceof ApiError && error.status === 403;
};

const App = () => {
  const [adminToken, setAdminTokenState] = useState<string | null>(() => getAdminToken());
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [syncRunsLimit, setSyncRunsLimit] = useState(20);
  const [alertsLimit, setAlertsLimit] = useState(20);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const isAuthenticated = Boolean(adminToken);

  const dismissFeedback = useCallback(() => setFeedbackMessage(null), []);
  const dismissError = useCallback(() => setErrorMessage(null), []);

  useEffect(() => {
    if (!feedbackMessage) {
      return;
    }
    const timeout = window.setTimeout(dismissFeedback, 5000);
    return () => window.clearTimeout(timeout);
  }, [feedbackMessage, dismissFeedback]);

  useEffect(() => {
    if (!errorMessage) {
      return;
    }
    const timeout = window.setTimeout(dismissError, 5000);
    return () => window.clearTimeout(timeout);
  }, [errorMessage, dismissError]);

  const handleUnauthorized = useCallback(() => {
    clearAdminToken();
    setAdminTokenState(null);
    setTokenError("Jeton invalide. Merci de le ressaisir.");
    setFeedbackMessage(null);
    setErrorMessage(null);
  }, [setAdminTokenState, setTokenError, setFeedbackMessage, setErrorMessage]);

  const statsQuery = useQuery({
    queryKey: ["stats-summary"],
    queryFn: adminApi.getStatsSummary,
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? REFRESH_LONG : false,
  });

  const syncRunsQuery = useQuery({
    queryKey: ["sync-runs", syncRunsLimit],
    queryFn: () => adminApi.getSyncRuns(syncRunsLimit),
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? REFRESH_SHORT : false,
  });

  const syncStateQuery = useQuery({
    queryKey: ["sync-state"],
    queryFn: adminApi.getSyncState,
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? REFRESH_LONG : false,
  });

  const alertsQuery = useQuery({
    queryKey: ["alerts", alertsLimit],
    queryFn: () => adminApi.getRecentAlerts(alertsLimit),
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? REFRESH_SHORT : false,
  });

  useEffect(() => {
    if (!adminToken) {
      return;
    }
    if (
      isUnauthorizedError(statsQuery.error) ||
      isUnauthorizedError(syncRunsQuery.error) ||
      isUnauthorizedError(syncStateQuery.error) ||
      isUnauthorizedError(alertsQuery.error)
    ) {
      handleUnauthorized();
    }
  }, [
    adminToken,
    statsQuery.error,
    syncRunsQuery.error,
    syncStateQuery.error,
    alertsQuery.error,
    handleUnauthorized,
  ]);

  const showError = useCallback(
    (error: unknown) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
      setErrorMessage(message);
      setFeedbackMessage(null);
    },
    [handleUnauthorized, setErrorMessage, setFeedbackMessage]
  );

  const fullSyncMutation = useMutation<TriggerSyncResult, unknown, SyncRequestPayload>({
    mutationFn: (payload: SyncRequestPayload) => adminApi.triggerFullSync(payload),
    onSuccess: (result: TriggerSyncResult) => {
      const { run } = result;
      setFeedbackMessage(`Synchro complète déclenchée (scope ${run?.scopeKey ?? "?"}).`);
      setErrorMessage(null);
      statsQuery.refetch();
      syncRunsQuery.refetch();
      syncStateQuery.refetch();
    },
    onError: showError,
  });

  const incrementalSyncMutation = useMutation<TriggerSyncResult, unknown, void>({
    mutationFn: () => adminApi.triggerIncrementalSync(),
    onSuccess: (result: TriggerSyncResult) => {
      const { run, detail, status } = result;
      if (!run) {
        setFeedbackMessage(detail ?? "Aucune mise à jour disponible.");
      } else {
        setFeedbackMessage(`Synchro incrémentale déclenchée (scope ${run.scopeKey}).`);
      }
      setErrorMessage(null);
      if (status !== 202) {
        statsQuery.refetch();
        syncRunsQuery.refetch();
        syncStateQuery.refetch();
      }
    },
    onError: showError,
  });

  const handleTriggerFull = (payload: SyncRequestPayload) => {
    if (!isAuthenticated) {
      setTokenError("Merci de saisir un jeton administrateur.");
      return;
    }
    fullSyncMutation.mutate(payload);
  };

  const handleTriggerIncremental = () => {
    if (!isAuthenticated) {
      setTokenError("Merci de saisir un jeton administrateur.");
      return;
    }
    incrementalSyncMutation.mutate();
  };

  const handleTokenSubmit = useCallback(
    (token: string) => {
      setAdminToken(token);
      setAdminTokenState(token);
      setTokenError(null);
      setFeedbackMessage(null);
      setErrorMessage(null);
      queryClient.invalidateQueries();
    },
    [queryClient, setAdminTokenState, setTokenError, setFeedbackMessage, setErrorMessage]
  );

  const handleTokenReset = useCallback(() => {
    clearAdminToken();
    setAdminTokenState(null);
    setTokenError(null);
    setFeedbackMessage(null);
    setErrorMessage(null);
  }, [setAdminTokenState, setTokenError, setFeedbackMessage, setErrorMessage]);

  if (!adminToken) {
    return <AdminTokenPrompt onSubmit={handleTokenSubmit} errorMessage={tokenError} />;
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-titles">
          <h1>Biz Tracker Admin</h1>
          <p className="muted">Console de pilotage des synchronisations et alertes.</p>
        </div>
        <button type="button" className="ghost" onClick={handleTokenReset}>
          Changer de jeton
        </button>
      </header>
      <main className="app-grid">
        <StatsSummaryCard
          summary={statsQuery.data}
          isLoading={statsQuery.isLoading}
          error={statsQuery.error as Error | null}
          onRefresh={() => statsQuery.refetch()}
        />

        <TriggerSyncForm
          onTriggerFull={handleTriggerFull}
          onTriggerIncremental={handleTriggerIncremental}
          isFullSyncLoading={fullSyncMutation.isPending}
          isIncrementalLoading={incrementalSyncMutation.isPending}
          feedbackMessage={feedbackMessage}
          errorMessage={errorMessage}
        />

        <SyncRunsTable
          runs={syncRunsQuery.data}
          isLoading={syncRunsQuery.isLoading}
          error={syncRunsQuery.error as Error | null}
          limit={syncRunsLimit}
          onLimitChange={setSyncRunsLimit}
          onRefresh={() => syncRunsQuery.refetch()}
        />

        <SyncStateTable
          states={syncStateQuery.data}
          isLoading={syncStateQuery.isLoading}
          error={syncStateQuery.error as Error | null}
          onRefresh={() => syncStateQuery.refetch()}
        />

        <AlertsList
          alerts={alertsQuery.data}
          isLoading={alertsQuery.isLoading}
          error={alertsQuery.error as Error | null}
          limit={alertsLimit}
          onLimitChange={setAlertsLimit}
          onRefresh={() => alertsQuery.refetch()}
        />
      </main>
    </div>
  );
};

export default App;

import { useEffect, useState, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  adminApi,
  ApiError,
  type TriggerSyncResult,
  type DeleteRunResponse,
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
import { EstablishmentsSection } from "./components/EstablishmentsSection";
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
  const [establishmentsLimit, setEstablishmentsLimit] = useState(20);
  const [establishmentsPage, setEstablishmentsPage] = useState(0);
  const [establishmentsQuery, setEstablishmentsQuery] = useState("");
  const [establishmentsFeedback, setEstablishmentsFeedback] = useState<string | null>(null);
  const [establishmentsError, setEstablishmentsError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const isAuthenticated = Boolean(adminToken);

  const dismissFeedback = useCallback(() => setFeedbackMessage(null), []);
  const dismissError = useCallback(() => setErrorMessage(null), []);
  const dismissEstablishmentsFeedback = useCallback(() => setEstablishmentsFeedback(null), []);
  const dismissEstablishmentsError = useCallback(() => setEstablishmentsError(null), []);

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

  useEffect(() => {
    if (!establishmentsFeedback) {
      return;
    }
    const timeout = window.setTimeout(dismissEstablishmentsFeedback, 5000);
    return () => window.clearTimeout(timeout);
  }, [establishmentsFeedback, dismissEstablishmentsFeedback]);

  useEffect(() => {
    if (!establishmentsError) {
      return;
    }
    const timeout = window.setTimeout(dismissEstablishmentsError, 5000);
    return () => window.clearTimeout(timeout);
  }, [establishmentsError, dismissEstablishmentsError]);

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

  const establishmentsQueryResult = useQuery({
    queryKey: [
      "establishments",
      establishmentsLimit,
      establishmentsPage,
      establishmentsQuery,
    ],
    queryFn: () =>
      adminApi.getEstablishments({
        limit: establishmentsLimit,
        offset: establishmentsPage * establishmentsLimit,
        q: establishmentsQuery ? establishmentsQuery : undefined,
      }),
    enabled: isAuthenticated,
  });

  useEffect(() => {
    if (!adminToken) {
      return;
    }
    if (
      isUnauthorizedError(statsQuery.error) ||
      isUnauthorizedError(syncRunsQuery.error) ||
      isUnauthorizedError(syncStateQuery.error) ||
      isUnauthorizedError(alertsQuery.error) ||
      isUnauthorizedError(establishmentsQueryResult.error)
    ) {
      handleUnauthorized();
    }
  }, [
    adminToken,
    statsQuery.error,
    syncRunsQuery.error,
    syncStateQuery.error,
    alertsQuery.error,
    establishmentsQueryResult.error,
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

  const showEstablishmentsError = useCallback(
    (error: unknown) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
      setEstablishmentsError(message);
      setEstablishmentsFeedback(null);
    },
    [handleUnauthorized]
  );

  const deleteEstablishmentMutation = useMutation<void, unknown, string>({
    mutationFn: (siret: string) => adminApi.deleteEstablishment(siret),
    onSuccess: (_, variables) => {
      setEstablishmentsFeedback(`Établissement ${variables} supprimé.`);
      setEstablishmentsError(null);
      establishmentsQueryResult.refetch();
    },
    onError: showEstablishmentsError,
  });

  const deleteRunMutation = useMutation<DeleteRunResponse, unknown, string>({
    mutationFn: (runId: string) => adminApi.deleteRun(runId),
    onSuccess: (result, runId) => {
      setFeedbackMessage(
        `Run ${runId} supprimé (${result.establishments_deleted} établissements, ${result.alerts_deleted} alertes).`
      );
      setErrorMessage(null);
      statsQuery.refetch();
      syncRunsQuery.refetch();
      syncStateQuery.refetch();
      alertsQuery.refetch();
      establishmentsQueryResult.refetch();
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

  const handleEstablishmentsLimitChange = (limit: number) => {
    setEstablishmentsLimit(limit);
    setEstablishmentsPage(0);
  };

  const handleEstablishmentsPageChange = (page: number) => {
    setEstablishmentsPage(page < 0 ? 0 : page);
  };

  const handleEstablishmentsQueryChange = (value: string) => {
    setEstablishmentsQuery(value);
    setEstablishmentsPage(0);
  };

  const handleDeleteEstablishment = (siret: string) => {
    if (!isAuthenticated) {
      setTokenError("Merci de saisir un jeton administrateur.");
      return;
    }
    deleteEstablishmentMutation.mutate(siret);
  };

  const handleDeleteRun = (runId: string) => {
    if (!isAuthenticated) {
      setTokenError("Merci de saisir un jeton administrateur.");
      return;
    }
    deleteRunMutation.mutate(runId);
  };

  const deletingRunId = deleteRunMutation.isPending ? deleteRunMutation.variables ?? null : null;

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
        <section className="dashboard-section">
          <div className="section-header">
            <div>
              <h2>Synchronisations</h2>
              <p className="muted">Pilotage des traitements batch et suivi d'exécution.</p>
            </div>
          </div>
          <div className="section-grid-two">
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
          </div>
          <div className="section-grid">
            <SyncRunsTable
              runs={syncRunsQuery.data}
              isLoading={syncRunsQuery.isLoading}
              error={syncRunsQuery.error as Error | null}
              limit={syncRunsLimit}
              onLimitChange={setSyncRunsLimit}
              onRefresh={() => syncRunsQuery.refetch()}
              onDeleteRun={handleDeleteRun}
              deletingRunId={deletingRunId}
              isDeletingRun={deleteRunMutation.isPending}
            />

            <SyncStateTable
              states={syncStateQuery.data}
              isLoading={syncStateQuery.isLoading}
              error={syncStateQuery.error as Error | null}
              onRefresh={() => syncStateQuery.refetch()}
            />
          </div>
        </section>

        <section className="dashboard-section">
          <div className="section-header">
            <div>
              <h2>Alertes</h2>
              <p className="muted">Dernières notifications envoyées aux équipes.</p>
            </div>
          </div>
          <div className="section-grid">
            <AlertsList
              alerts={alertsQuery.data}
              isLoading={alertsQuery.isLoading}
              error={alertsQuery.error as Error | null}
              limit={alertsLimit}
              onLimitChange={setAlertsLimit}
              onRefresh={() => alertsQuery.refetch()}
            />
          </div>
        </section>

        <section className="dashboard-section">
          <div className="section-header">
            <div>
              <h2>Etablissements</h2>
              <p className="muted">Recherche et suppression sécurisée des établissements.</p>
            </div>
          </div>
          <div className="section-grid">
            <EstablishmentsSection
              establishments={establishmentsQueryResult.data}
              isLoading={establishmentsQueryResult.isLoading}
              error={establishmentsQueryResult.error as Error | null}
              limit={establishmentsLimit}
              page={establishmentsPage}
              query={establishmentsQuery}
              hasNextPage={(establishmentsQueryResult.data?.length ?? 0) === establishmentsLimit}
              onLimitChange={handleEstablishmentsLimitChange}
              onPageChange={handleEstablishmentsPageChange}
              onQueryChange={handleEstablishmentsQueryChange}
              onRefresh={() => establishmentsQueryResult.refetch()}
              onDeleteEstablishment={handleDeleteEstablishment}
              deletingSiret={
                deleteEstablishmentMutation.isPending
                  ? (deleteEstablishmentMutation.variables as string | null | undefined) ?? null
                  : null
              }
              isDeletingOne={deleteEstablishmentMutation.isPending}
              feedbackMessage={establishmentsFeedback}
              errorMessage={establishmentsError}
            />
          </div>
        </section>
      </main>
    </div>
  );
};

export default App;

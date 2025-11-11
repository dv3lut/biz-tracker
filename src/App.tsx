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
import { StatsSummaryCard } from "./components/StatsSummaryCard";
import { SyncRunsTable } from "./components/SyncRunsTable";
import { SyncStateTable } from "./components/SyncStateTable";
import { AlertsList } from "./components/AlertsList";
import { EstablishmentsSection } from "./components/EstablishmentsSection";
import { EmailTestPanel } from "./components/EmailTestPanel";
import { EstablishmentDetailModal } from "./components/EstablishmentDetailModal";
import { DashboardInsights } from "./components/DashboardInsights";
import {
  EmailTestPayload,
  EmailTestResult,
  EstablishmentDetail,
  GoogleCheckResult,
  SyncRequestPayload,
  SyncRun,
} from "./types";

const REFRESH_LONG = 60_000;
const REFRESH_SHORT = 30_000;
const REFRESH_ACTIVE = 1_000;
const DASHBOARD_DAYS = 30;

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
  const [emailFeedback, setEmailFeedback] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [alertsFeedback, setAlertsFeedback] = useState<string | null>(null);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [checkingGoogleSiret, setCheckingGoogleSiret] = useState<string | null>(null);
  const [selectedEstablishmentSiret, setSelectedEstablishmentSiret] = useState<string | null>(null);
  const [isExportingGooglePlaces, setIsExportingGooglePlaces] = useState(false);

  const queryClient = useQueryClient();
  const isAuthenticated = Boolean(adminToken);

  const dismissFeedback = useCallback(() => setFeedbackMessage(null), []);
  const dismissError = useCallback(() => setErrorMessage(null), []);
  const dismissEstablishmentsFeedback = useCallback(() => setEstablishmentsFeedback(null), []);
  const dismissEstablishmentsError = useCallback(() => setEstablishmentsError(null), []);
  const dismissEmailFeedback = useCallback(() => setEmailFeedback(null), []);
  const dismissEmailError = useCallback(() => setEmailError(null), []);
  const dismissAlertsFeedback = useCallback(() => setAlertsFeedback(null), []);
  const dismissAlertsError = useCallback(() => setAlertsError(null), []);

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

  useEffect(() => {
    if (!emailFeedback) {
      return;
    }
    const timeout = window.setTimeout(dismissEmailFeedback, 5000);
    return () => window.clearTimeout(timeout);
  }, [emailFeedback, dismissEmailFeedback]);

  useEffect(() => {
    if (!emailError) {
      return;
    }
    const timeout = window.setTimeout(dismissEmailError, 5000);
    return () => window.clearTimeout(timeout);
  }, [emailError, dismissEmailError]);

  useEffect(() => {
    if (!alertsFeedback) {
      return;
    }
    const timeout = window.setTimeout(dismissAlertsFeedback, 5000);
    return () => window.clearTimeout(timeout);
  }, [alertsFeedback, dismissAlertsFeedback]);

  useEffect(() => {
    if (!alertsError) {
      return;
    }
    const timeout = window.setTimeout(dismissAlertsError, 5000);
    return () => window.clearTimeout(timeout);
  }, [alertsError, dismissAlertsError]);

  const handleUnauthorized = useCallback(() => {
    clearAdminToken();
    setAdminTokenState(null);
    setTokenError("Jeton invalide. Merci de le ressaisir.");
    setFeedbackMessage(null);
    setErrorMessage(null);
    setEmailFeedback(null);
    setEmailError(null);
    setEstablishmentsFeedback(null);
    setEstablishmentsError(null);
    setAlertsFeedback(null);
    setAlertsError(null);
    setCheckingGoogleSiret(null);
    setSelectedEstablishmentSiret(null);
    setIsExportingGooglePlaces(false);
  }, [
    setAdminTokenState,
    setTokenError,
    setFeedbackMessage,
    setErrorMessage,
    setEmailFeedback,
    setEmailError,
    setEstablishmentsFeedback,
    setEstablishmentsError,
    setAlertsFeedback,
    setAlertsError,
    setCheckingGoogleSiret,
    setSelectedEstablishmentSiret,
    setIsExportingGooglePlaces,
  ]);

  const syncRunsQuery = useQuery<SyncRun[]>({
    queryKey: ["sync-runs", syncRunsLimit],
    queryFn: () => adminApi.getSyncRuns(syncRunsLimit),
    enabled: isAuthenticated,
    refetchInterval: (query) => {
      if (!isAuthenticated) {
        return false;
      }
      const runs = (query.state.data as SyncRun[] | undefined) ?? [];
      const active = runs.some((run) => run.status === "running" || run.status === "pending");
      return active ? REFRESH_ACTIVE : REFRESH_SHORT;
    },
  });

  const hasActiveRun = syncRunsQuery.data?.some((run) => run.status === "running" || run.status === "pending") ?? false;
  const isSyncActive = hasActiveRun;

  const statsQuery = useQuery({
    queryKey: ["stats-summary"],
    queryFn: adminApi.getStatsSummary,
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? (isSyncActive ? REFRESH_ACTIVE : REFRESH_LONG) : false,
  });

  const syncStateQuery = useQuery({
    queryKey: ["sync-state"],
    queryFn: adminApi.getSyncState,
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? (isSyncActive ? REFRESH_ACTIVE : REFRESH_LONG) : false,
  });

  const dashboardQuery = useQuery({
    queryKey: ["dashboard-metrics", DASHBOARD_DAYS],
    queryFn: () => adminApi.getDashboardMetrics(DASHBOARD_DAYS),
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? (isSyncActive ? REFRESH_ACTIVE : REFRESH_LONG) : false,
  });

  const alertsQuery = useQuery({
    queryKey: ["alerts", alertsLimit],
    queryFn: () => adminApi.getRecentAlerts(alertsLimit),
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? (isSyncActive ? REFRESH_ACTIVE : REFRESH_SHORT) : false,
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

  const establishmentDetailQuery = useQuery<EstablishmentDetail>({
    queryKey: ["establishment-detail", selectedEstablishmentSiret],
    queryFn: () => adminApi.getEstablishment(selectedEstablishmentSiret!),
    enabled: isAuthenticated && Boolean(selectedEstablishmentSiret),
    staleTime: 60_000,
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
      isUnauthorizedError(establishmentsQueryResult.error) ||
      isUnauthorizedError(dashboardQuery.error)
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
    dashboardQuery.error,
    handleUnauthorized,
  ]);

  useEffect(() => {
    if (!selectedEstablishmentSiret) {
      return;
    }
    if (isUnauthorizedError(establishmentDetailQuery.error)) {
      handleUnauthorized();
    }
  }, [selectedEstablishmentSiret, establishmentDetailQuery.error, handleUnauthorized]);

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

  const showEmailError = useCallback(
    (error: unknown) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "L'envoi du test a échoué.";
      setEmailError(message);
      setEmailFeedback(null);
    },
    [handleUnauthorized]
  );

  const syncMutation = useMutation<TriggerSyncResult, unknown, SyncRequestPayload>({
    mutationFn: (payload: SyncRequestPayload) => adminApi.triggerSync(payload),
    onSuccess: ({ run, status, detail }: TriggerSyncResult) => {
      if (run) {
        const label = status === 202 ? "programmée" : "déclenchée";
        setFeedbackMessage(`Synchro ${label} (scope ${run.scopeKey}).`);
      } else {
        setFeedbackMessage(detail ?? "Synchro acceptée.");
      }
      setErrorMessage(null);
      statsQuery.refetch();
      syncRunsQuery.refetch();
      syncStateQuery.refetch();
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

  const emailTestMutation = useMutation<EmailTestResult, unknown, EmailTestPayload>({
    mutationFn: (payload: EmailTestPayload) => adminApi.sendEmailTest(payload),
    onSuccess: (result) => {
      const recipients = result.recipients.length > 0 ? result.recipients.join(", ") : "destinataires configurés";
      setEmailFeedback(`E-mail de test envoyé via ${result.provider} vers ${recipients}.`);
      setEmailError(null);
    },
    onError: showEmailError,
  });

  const manualGoogleCheckMutation = useMutation<GoogleCheckResult, unknown, { siret: string; source: "alerts" | "establishments" }>({
    mutationFn: ({ siret }) => adminApi.checkGoogleForEstablishment(siret),
    onMutate: ({ siret, source }) => {
      setCheckingGoogleSiret(siret);
      if (source === "alerts") {
        setAlertsFeedback(null);
        setAlertsError(null);
      } else {
        setEstablishmentsFeedback(null);
        setEstablishmentsError(null);
      }
    },
    onSuccess: (result, variables) => {
      const message = result.message || `Vérification Google relancée pour ${variables.siret}.`;
      if (variables.source === "alerts") {
        setAlertsFeedback(message);
        setAlertsError(null);
      } else {
        setEstablishmentsFeedback(message);
        setEstablishmentsError(null);
      }
      alertsQuery.refetch();
      establishmentsQueryResult.refetch();
      queryClient.invalidateQueries({ queryKey: ["establishment-detail", variables.siret] });
    },
    onError: (error, variables) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "La vérification Google a échoué.";
      if (variables.source === "alerts") {
        setAlertsError(message);
        setAlertsFeedback(null);
      } else {
        setEstablishmentsError(message);
        setEstablishmentsFeedback(null);
      }
    },
    onSettled: () => {
      setCheckingGoogleSiret(null);
    },
  });

  const triggerManualGoogleCheck = manualGoogleCheckMutation.mutate;

  const establishmentDetailErrorMessage = establishmentDetailQuery.error
    ? establishmentDetailQuery.error instanceof ApiError
      ? establishmentDetailQuery.error.message
      : "Impossible de charger la fiche établissement."
    : null;

  const handleTriggerSync = useCallback(() => {
    if (!isAuthenticated) {
      setTokenError("Merci de saisir un jeton administrateur.");
      return;
    }
    syncMutation.mutate({ checkForUpdates: true });
  }, [isAuthenticated, syncMutation, setTokenError]);

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

  const handleOpenEstablishmentDetail = useCallback(
    (siret: string) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
      setSelectedEstablishmentSiret(siret);
    },
    [isAuthenticated, setTokenError]
  );

  const handleCloseEstablishmentDetail = useCallback(() => {
    const currentSiret = selectedEstablishmentSiret;
    setSelectedEstablishmentSiret(null);
    if (currentSiret) {
      queryClient.removeQueries({ queryKey: ["establishment-detail", currentSiret], exact: true });
    }
  }, [queryClient, selectedEstablishmentSiret]);

  const handleTriggerGoogleCheckFromAlerts = useCallback(
    (siret: string) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
      triggerManualGoogleCheck({ siret, source: "alerts" });
    },
    [isAuthenticated, triggerManualGoogleCheck, setTokenError]
  );

  const handleTriggerGoogleCheckFromEstablishments = useCallback(
    (siret: string) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
      triggerManualGoogleCheck({ siret, source: "establishments" });
    },
    [isAuthenticated, triggerManualGoogleCheck, setTokenError]
  );

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
      setEmailFeedback(null);
      setEmailError(null);
      setEstablishmentsFeedback(null);
      setEstablishmentsError(null);
      setAlertsFeedback(null);
      setAlertsError(null);
      setCheckingGoogleSiret(null);
      setSelectedEstablishmentSiret(null);
      queryClient.invalidateQueries();
    },
    [
      queryClient,
      setAdminTokenState,
      setTokenError,
      setFeedbackMessage,
      setErrorMessage,
      setEmailFeedback,
      setEmailError,
      setEstablishmentsFeedback,
      setEstablishmentsError,
      setAlertsFeedback,
      setAlertsError,
      setCheckingGoogleSiret,
      setSelectedEstablishmentSiret,
    ]
  );

  const handleTokenReset = useCallback(() => {
    clearAdminToken();
    setAdminTokenState(null);
    setTokenError(null);
    setFeedbackMessage(null);
    setErrorMessage(null);
    setEmailFeedback(null);
    setEmailError(null);
    setEstablishmentsFeedback(null);
    setEstablishmentsError(null);
    setAlertsFeedback(null);
    setAlertsError(null);
    setCheckingGoogleSiret(null);
    setSelectedEstablishmentSiret(null);
  }, [
    setAdminTokenState,
    setTokenError,
    setFeedbackMessage,
    setErrorMessage,
    setEmailFeedback,
    setEmailError,
    setEstablishmentsFeedback,
    setEstablishmentsError,
    setAlertsFeedback,
    setAlertsError,
    setCheckingGoogleSiret,
    setSelectedEstablishmentSiret,
  ]);

  const handleSendEmailTest = useCallback(
    (payload: EmailTestPayload) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
      emailTestMutation.mutate(payload);
    },
    [isAuthenticated, emailTestMutation, setTokenError]
  );

  const handleResetEmailMessages = useCallback(() => {
    setEmailFeedback(null);
    setEmailError(null);
  }, []);

  const handleExportGooglePlaces = useCallback(async () => {
    if (!isAuthenticated) {
      setTokenError("Merci de saisir un jeton administrateur.");
      return;
    }
    setIsExportingGooglePlaces(true);
    try {
      const blob = await adminApi.exportGooglePlaces();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      const today = new Date().toISOString().slice(0, 10);
      anchor.download = `biz-tracker-google-places-${today}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setFeedbackMessage("Export Google Places téléchargé.");
      setErrorMessage(null);
    } catch (error) {
      showError(error);
    } finally {
      setIsExportingGooglePlaces(false);
    }
  }, [isAuthenticated, showError]);

  if (!adminToken) {
    return <AdminTokenPrompt onSubmit={handleTokenSubmit} errorMessage={tokenError} />;
  }

  const isCheckingGoogle = manualGoogleCheckMutation.isPending;
  const isDetailLoading =
    establishmentDetailQuery.isLoading ||
    (establishmentDetailQuery.isFetching && !establishmentDetailQuery.data);

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
          <div className="section-grid">
            <StatsSummaryCard
              summary={statsQuery.data}
              isLoading={statsQuery.isLoading}
              error={statsQuery.error as Error | null}
              onRefresh={() => statsQuery.refetch()}
              onTriggerSync={handleTriggerSync}
              isTriggering={syncMutation.isPending}
              onExportGooglePlaces={handleExportGooglePlaces}
              isExportingGooglePlaces={isExportingGooglePlaces}
              feedbackMessage={feedbackMessage}
              errorMessage={errorMessage}
              isRefreshing={isSyncActive && statsQuery.isFetching}
            />
            <DashboardInsights
              metrics={dashboardQuery.data}
              isLoading={dashboardQuery.isLoading}
              error={dashboardQuery.error as Error | null}
              onRefresh={() => dashboardQuery.refetch()}
              isRefreshing={isSyncActive && dashboardQuery.isFetching}
              days={DASHBOARD_DAYS}
            />
          </div>
          <div className="section-grid two-column">
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
              isRefreshing={isSyncActive && syncRunsQuery.isFetching}
            />

            <SyncStateTable
              states={syncStateQuery.data}
              isLoading={syncStateQuery.isLoading}
              error={syncStateQuery.error as Error | null}
              onRefresh={() => syncStateQuery.refetch()}
              isRefreshing={isSyncActive && syncStateQuery.isFetching}
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
              onTriggerGoogleCheck={handleTriggerGoogleCheckFromAlerts}
              isCheckingGoogle={isCheckingGoogle}
              checkingGoogleSiret={checkingGoogleSiret}
              feedbackMessage={alertsFeedback}
              errorMessage={alertsError}
              onSelect={handleOpenEstablishmentDetail}
            />
          </div>
        </section>

        <section className="dashboard-section">
          <div className="section-header">
            <div>
              <h2>E-mails</h2>
              <p className="muted">Tester et valider la configuration SMTP.</p>
            </div>
          </div>
          <div className="section-grid">
            <EmailTestPanel
              onSend={handleSendEmailTest}
              isSending={emailTestMutation.isPending}
              feedbackMessage={emailFeedback}
              errorMessage={emailError}
              onResetMessages={handleResetEmailMessages}
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
              onTriggerGoogleCheck={handleTriggerGoogleCheckFromEstablishments}
              isCheckingGoogle={isCheckingGoogle}
              checkingGoogleSiret={checkingGoogleSiret}
              onSelectEstablishment={handleOpenEstablishmentDetail}
            />
          </div>
        </section>
      </main>
      <EstablishmentDetailModal
        isOpen={Boolean(selectedEstablishmentSiret)}
        establishment={establishmentDetailQuery.data ?? null}
        isLoading={isDetailLoading}
        errorMessage={establishmentDetailErrorMessage}
        onClose={handleCloseEstablishmentDetail}
      />
    </div>
  );
};

export default App;

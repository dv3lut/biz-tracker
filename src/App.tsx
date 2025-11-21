import { useEffect, useState, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  alertsApi,
  adminConfigApi,
  clearAdminToken,
  emailApi,
  establishmentsApi,
  getAdminToken,
  googleApi,
  clientsApi,
  nafApi,
  setAdminToken,
  statsApi,
  syncApi,
  type AdminEmailConfigPayload,
  type ClientCreatePayload,
  type ClientUpdatePayload,
  type DeleteRunResponse,
  type TriggerSyncResult,
} from "./api";
import { AdminTokenPrompt } from "./components/AdminTokenPrompt";
import { EstablishmentDetailModal } from "./components/EstablishmentDetailModal";
import { SyncRunDetailModal } from "./components/SyncRunDetailModal";
import { ClientModal, type ClientFormSubmitPayload } from "./components/ClientModal";
import { SidebarNav } from "./components/layout/SidebarNav";
import { AppHeader } from "./components/layout/AppHeader";
import { DashboardView } from "./components/views/DashboardView";
import { SyncView } from "./components/views/SyncView";
import { AlertsView } from "./components/views/AlertsView";
import { ClientsView } from "./components/views/ClientsView";
import { EmailsView } from "./components/views/EmailsView";
import { EstablishmentsView } from "./components/views/EstablishmentsView";
import { NafConfigView } from "./components/views/NafConfigView";
import {
  Alert,
  AdminEmailConfig,
  DashboardMetrics,
  EmailTestPayload,
  EmailTestResult,
  Establishment,
  EstablishmentDetail,
  EstablishmentIndividualFilter,
  Client,
  NafCategory,
  GoogleCheckResult,
  GoogleRetryConfig,
  StatsSummary,
  SyncRequestPayload,
  SyncRun,
  SyncState,
} from "./types";
import { NAV_SECTIONS, type SectionKey } from "./constants/sections";
import { useRefreshIndicator } from "./hooks/useRefreshIndicator";

type RunDetailModalState = {
  isOpen: boolean;
  date: string | null;
  runs: SyncRun[];
  selectedRunId: string | null;
  isLoading: boolean;
  error: string | null;
};

const runMatchesDay = (run: SyncRun, isoDate: string): boolean => {
  if (!run.startedAt) {
    return false;
  }
  return run.startedAt.slice(0, 10) === isoDate;
};

const DASHBOARD_DAYS = 30;
const GOOGLE_EXPORT_DEFAULT_WINDOW_DAYS = 30;

const getDefaultGoogleExportRange = () => {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - GOOGLE_EXPORT_DEFAULT_WINDOW_DAYS);
  const format = (value: Date) => value.toISOString().slice(0, 10);
  return { start: format(start), end: format(end) };
};

const isUnauthorizedError = (error: unknown): error is ApiError => {
  return error instanceof ApiError && error.status === 403;
};

const App = () => {
  const [adminToken, setAdminTokenState] = useState<string | null>(() => getAdminToken());
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<SectionKey>("dashboard");
  const [syncRunsLimit, setSyncRunsLimit] = useState(20);
  const [alertsLimit, setAlertsLimit] = useState(20);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [establishmentsLimit, setEstablishmentsLimit] = useState(20);
  const [establishmentsPage, setEstablishmentsPage] = useState(0);
  const [establishmentsQuery, setEstablishmentsQuery] = useState("");
  const [establishmentsIndividualFilter, setEstablishmentsIndividualFilter] =
    useState<EstablishmentIndividualFilter>("all");
  const [establishmentsFeedback, setEstablishmentsFeedback] = useState<string | null>(null);
  const [establishmentsError, setEstablishmentsError] = useState<string | null>(null);
  const [emailFeedback, setEmailFeedback] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [alertsFeedback, setAlertsFeedback] = useState<string | null>(null);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [alertsExportDays, setAlertsExportDays] = useState(30);
  const [isExportingAlerts, setIsExportingAlerts] = useState(false);
  const [clientsFeedback, setClientsFeedback] = useState<string | null>(null);
  const [clientsError, setClientsError] = useState<string | null>(null);
  const [adminEmailFeedback, setAdminEmailFeedback] = useState<string | null>(null);
  const [adminEmailError, setAdminEmailError] = useState<string | null>(null);
  const [checkingGoogleSiret, setCheckingGoogleSiret] = useState<string | null>(null);
  const [selectedEstablishmentSiret, setSelectedEstablishmentSiret] = useState<string | null>(null);
  const [isExportingGooglePlaces, setIsExportingGooglePlaces] = useState(false);
  const [googleExportStartDate, setGoogleExportStartDate] = useState<string>(() => getDefaultGoogleExportRange().start);
  const [googleExportEndDate, setGoogleExportEndDate] = useState<string>(() => getDefaultGoogleExportRange().end);
  const [runDetailModal, setRunDetailModal] = useState<RunDetailModalState | null>(null);
  const [clientModalState, setClientModalState] = useState<{ mode: "create" | "edit"; client: Client | null } | null>(
    null,
  );
  const [googleRetryConfigFeedback, setGoogleRetryConfigFeedback] = useState<string | null>(null);
  const [googleRetryConfigMessageError, setGoogleRetryConfigMessageError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const isAuthenticated = Boolean(adminToken);
  const requestAdminToken = useCallback(() => {
    setTokenError("Merci de saisir un jeton administrateur.");
  }, [setTokenError]);

  const dismissFeedback = useCallback(() => setFeedbackMessage(null), []);
  const dismissError = useCallback(() => setErrorMessage(null), []);
  const dismissEstablishmentsFeedback = useCallback(() => setEstablishmentsFeedback(null), []);
  const dismissEstablishmentsError = useCallback(() => setEstablishmentsError(null), []);
  const dismissEmailFeedback = useCallback(() => setEmailFeedback(null), []);
  const dismissEmailError = useCallback(() => setEmailError(null), []);
  const dismissAlertsFeedback = useCallback(() => setAlertsFeedback(null), []);
  const dismissAlertsError = useCallback(() => setAlertsError(null), []);
  const dismissClientsFeedback = useCallback(() => setClientsFeedback(null), []);
  const dismissClientsError = useCallback(() => setClientsError(null), []);
  const dismissAdminEmailFeedback = useCallback(() => setAdminEmailFeedback(null), []);
  const dismissAdminEmailError = useCallback(() => setAdminEmailError(null), []);
  const dismissGoogleRetryConfigFeedback = useCallback(() => setGoogleRetryConfigFeedback(null), []);
  const dismissGoogleRetryConfigError = useCallback(() => setGoogleRetryConfigMessageError(null), []);

  const resetGoogleExportRange = useCallback(() => {
    const { start, end } = getDefaultGoogleExportRange();
    setGoogleExportStartDate(start);
    setGoogleExportEndDate(end);
  }, [setGoogleExportStartDate, setGoogleExportEndDate]);

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
    setClientsFeedback(null);
    setClientsError(null);
    setAdminEmailFeedback(null);
    setAdminEmailError(null);
  setGoogleRetryConfigFeedback(null);
  setGoogleRetryConfigMessageError(null);
    setCheckingGoogleSiret(null);
    setSelectedEstablishmentSiret(null);
    setIsExportingGooglePlaces(false);
    resetGoogleExportRange();
    setAlertsExportDays(30);
    setIsExportingAlerts(false);
    setRunDetailModal(null);
    setClientModalState(null);
    setActiveSection("dashboard");
  }, [resetGoogleExportRange]);

  const syncRunsQuery = useQuery<SyncRun[]>({
    queryKey: ["sync-runs", syncRunsLimit],
    queryFn: () => syncApi.fetchRuns(syncRunsLimit),
    enabled: isAuthenticated,
  });

  const hasActiveRun =
    syncRunsQuery.data?.some((run) => run.status === "running" || run.status === "pending") ?? false;
  const isSyncActive = hasActiveRun;

  const statsQuery = useQuery<StatsSummary>({
    queryKey: ["stats-summary"],
    queryFn: () => statsApi.fetchSummary(),
    enabled: isAuthenticated,
  });

  const syncStateQuery = useQuery<SyncState[]>({
    queryKey: ["sync-state"],
    queryFn: () => syncApi.fetchState(),
    enabled: isAuthenticated,
  });

  const dashboardQuery = useQuery<DashboardMetrics>({
    queryKey: ["dashboard-metrics", DASHBOARD_DAYS],
    queryFn: () => statsApi.fetchDashboardMetrics(DASHBOARD_DAYS),
    enabled: isAuthenticated,
  });

  const alertsQuery = useQuery<Alert[]>({
    queryKey: ["alerts", alertsLimit],
    queryFn: () => alertsApi.fetchRecent(alertsLimit),
    enabled: isAuthenticated,
  });

  const clientsQuery = useQuery<Client[]>({
    queryKey: ["clients"],
    queryFn: () => clientsApi.list(),
    enabled: isAuthenticated,
  });

  const nafCategoriesQuery = useQuery<NafCategory[]>({
    queryKey: ["naf-categories"],
    queryFn: () => nafApi.listCategories(),
    enabled: isAuthenticated,
  });

  const adminEmailConfigQuery = useQuery<AdminEmailConfig>({
    queryKey: ["admin-email-config"],
    queryFn: () => adminConfigApi.fetch(),
    enabled: isAuthenticated,
  });

  const googleRetryConfigQuery = useQuery<GoogleRetryConfig>({
    queryKey: ["google-retry-config"],
    queryFn: () => googleApi.fetchRetryConfig(),
    enabled: isAuthenticated,
  });

  const establishmentsQueryResult = useQuery<Establishment[]>({
    queryKey: [
      "establishments",
      establishmentsLimit,
      establishmentsPage,
      establishmentsQuery,
      establishmentsIndividualFilter,
    ],
    queryFn: () =>
      establishmentsApi.fetchMany({
        limit: establishmentsLimit,
        offset: establishmentsPage * establishmentsLimit,
        q: establishmentsQuery ? establishmentsQuery : undefined,
        isIndividual:
          establishmentsIndividualFilter === "all"
            ? undefined
            : establishmentsIndividualFilter === "individual",
      }),
    enabled: isAuthenticated,
  });

  const establishmentDetailQuery = useQuery<EstablishmentDetail>({
    queryKey: ["establishment-detail", selectedEstablishmentSiret],
    queryFn: () => establishmentsApi.fetchOne(selectedEstablishmentSiret!),
    enabled: isAuthenticated && Boolean(selectedEstablishmentSiret),
    staleTime: 60_000,
  });

  const runsIsRefreshing = useRefreshIndicator(syncRunsQuery.isFetching);
  const statsIsRefreshing = useRefreshIndicator(statsQuery.isFetching);
  const statesIsRefreshing = useRefreshIndicator(syncStateQuery.isFetching);
  const metricsIsRefreshing = useRefreshIndicator(dashboardQuery.isFetching);

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

  useEffect(() => {
    if (!clientsFeedback) {
      return;
    }
    const timeout = window.setTimeout(dismissClientsFeedback, 5000);
    return () => window.clearTimeout(timeout);
  }, [clientsFeedback, dismissClientsFeedback]);

  useEffect(() => {
    if (!clientsError) {
      return;
    }
    const timeout = window.setTimeout(dismissClientsError, 5000);
    return () => window.clearTimeout(timeout);
  }, [clientsError, dismissClientsError]);

  useEffect(() => {
    if (!adminEmailFeedback) {
      return;
    }
    const timeout = window.setTimeout(dismissAdminEmailFeedback, 5000);
    return () => window.clearTimeout(timeout);
  }, [adminEmailFeedback, dismissAdminEmailFeedback]);

  useEffect(() => {
    if (!adminEmailError) {
      return;
    }
    const timeout = window.setTimeout(dismissAdminEmailError, 5000);
    return () => window.clearTimeout(timeout);
  }, [adminEmailError, dismissAdminEmailError]);

  useEffect(() => {
    if (!googleRetryConfigFeedback) {
      return;
    }
    const timeout = window.setTimeout(dismissGoogleRetryConfigFeedback, 5000);
    return () => window.clearTimeout(timeout);
  }, [googleRetryConfigFeedback, dismissGoogleRetryConfigFeedback]);

  useEffect(() => {
    if (!googleRetryConfigMessageError) {
      return;
    }
    const timeout = window.setTimeout(dismissGoogleRetryConfigError, 5000);
    return () => window.clearTimeout(timeout);
  }, [googleRetryConfigMessageError, dismissGoogleRetryConfigError]);

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
      isUnauthorizedError(dashboardQuery.error) ||
      isUnauthorizedError(clientsQuery.error) ||
      isUnauthorizedError(adminEmailConfigQuery.error) ||
      isUnauthorizedError(googleRetryConfigQuery.error)
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
    clientsQuery.error,
    adminEmailConfigQuery.error,
    googleRetryConfigQuery.error,
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

  const handleDashboardDaySelect = useCallback(
    async (isoDate: string) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
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
        const limit = Math.max(syncRunsLimit, 100);
        const runs = await syncApi.fetchRuns(limit);
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
        if (isUnauthorizedError(error)) {
          handleUnauthorized();
          return;
        }
        const message =
          error instanceof ApiError ? error.message : "Impossible de charger le détail de cette synchro.";
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
    [isAuthenticated, syncRunsQuery.data, syncRunsLimit, handleUnauthorized, setTokenError],
  );

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
    [handleUnauthorized],
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

  const showClientsError = useCallback(
    (error: unknown) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
      setClientsError(message);
      setClientsFeedback(null);
    },
    [handleUnauthorized]
  );

  const showAdminEmailError = useCallback(
    (error: unknown) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "La mise à jour a échoué.";
      setAdminEmailError(message);
      setAdminEmailFeedback(null);
    },
    [handleUnauthorized]
  );

  const showGoogleRetryConfigError = useCallback(
    (error: unknown) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      const message =
        error instanceof ApiError
          ? error.message
          : "La mise à jour de la configuration Google a échoué.";
  setGoogleRetryConfigMessageError(message);
      setGoogleRetryConfigFeedback(null);
    },
    [handleUnauthorized]
  );

  const syncMutation = useMutation<TriggerSyncResult, unknown, SyncRequestPayload>({
    mutationFn: (payload: SyncRequestPayload) => syncApi.trigger(payload),
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
    mutationFn: (siret: string) => establishmentsApi.deleteOne(siret),
    onSuccess: (_, variables) => {
      setEstablishmentsFeedback(`Établissement ${variables} supprimé.`);
      setEstablishmentsError(null);
      establishmentsQueryResult.refetch();
    },
    onError: showEstablishmentsError,
  });

  const deleteRunMutation = useMutation<DeleteRunResponse, unknown, string>({
    mutationFn: (runId: string) => syncApi.deleteRun(runId),
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
    mutationFn: (payload: EmailTestPayload) => emailApi.sendTest(payload),
    onSuccess: (result) => {
      const recipients = result.recipients.length > 0 ? result.recipients.join(", ") : "destinataires configurés";
      setEmailFeedback(`E-mail de test envoyé via ${result.provider} vers ${recipients}.`);
      setEmailError(null);
    },
    onError: showEmailError,
  });

  const createClientMutation = useMutation<Client, unknown, ClientCreatePayload>({
    mutationFn: (payload: ClientCreatePayload) => clientsApi.create(payload),
    onSuccess: (client) => {
      setClientsFeedback(`Client ${client.name} créé.`);
      setClientsError(null);
      clientsQuery.refetch();
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setClientModalState(null);
    },
    onError: showClientsError,
  });

  const updateClientMutation = useMutation<Client, unknown, { clientId: string; payload: ClientUpdatePayload }>({
    mutationFn: ({ clientId, payload }) => clientsApi.update(clientId, payload),
    onSuccess: (client) => {
      setClientsFeedback(`Client ${client.name} mis à jour.`);
      setClientsError(null);
      clientsQuery.refetch();
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setClientModalState(null);
    },
    onError: showClientsError,
  });

  const deleteClientMutation = useMutation<void, unknown, { clientId: string; clientName: string }>({
    mutationFn: ({ clientId }) => clientsApi.delete(clientId),
    onSuccess: (_, variables) => {
      setClientsFeedback(`Client ${variables.clientName} supprimé.`);
      setClientsError(null);
      clientsQuery.refetch();
    },
    onError: showClientsError,
  });

  const updateAdminEmailConfigMutation = useMutation<AdminEmailConfig, unknown, AdminEmailConfigPayload>({
    mutationFn: (payload: AdminEmailConfigPayload) => adminConfigApi.update(payload),
    onSuccess: (config) => {
      setAdminEmailFeedback(
        config.recipients.length === 0
          ? "Destinataires admin mis à jour (aucun destinataire)."
          : `Destinataires admin mis à jour (${config.recipients.length}).`,
      );
      setAdminEmailError(null);
      adminEmailConfigQuery.refetch();
    },
    onError: showAdminEmailError,
  });

  const updateGoogleRetryConfigMutation = useMutation<GoogleRetryConfig, unknown, GoogleRetryConfig>({
    mutationFn: (payload: GoogleRetryConfig) => googleApi.updateRetryConfig(payload),
    onMutate: () => {
      setGoogleRetryConfigFeedback(null);
      setGoogleRetryConfigMessageError(null);
    },
    onSuccess: (config) => {
      setGoogleRetryConfigFeedback("Configuration Google mise à jour.");
      setGoogleRetryConfigMessageError(null);
      queryClient.setQueryData(["google-retry-config"], config);
    },
    onError: showGoogleRetryConfigError,
  });

  const manualGoogleCheckMutation = useMutation<GoogleCheckResult, unknown, { siret: string; source: "alerts" | "establishments" }>({
    mutationFn: ({ siret }) => googleApi.checkEstablishment(siret),
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

  const handleEstablishmentsIndividualFilterChange = (value: EstablishmentIndividualFilter) => {
    setEstablishmentsIndividualFilter(value);
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

  const handleAlertsExportDaysChange = useCallback((value: number) => {
    const nextValue = Number.isFinite(value) ? Math.round(value) : 30;
    const clamped = Math.max(1, Math.min(nextValue, 365));
    setAlertsExportDays(clamped);
  }, []);

  const handleExportAlerts = useCallback(async () => {
    if (!isAuthenticated) {
      setTokenError("Merci de saisir un jeton administrateur.");
      return;
    }
    setAlertsFeedback(null);
    setAlertsError(null);
    setIsExportingAlerts(true);
    try {
      const days = Math.max(1, Math.min(Math.round(alertsExportDays), 365));
      const blob = await alertsApi.exportByCreation(days);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      const today = new Date().toISOString().slice(0, 10);
      anchor.download = `biz-tracker-alerts-${days}d-${today}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setAlertsFeedback(`Export des alertes (${days} jours) téléchargé.`);
      setAlertsError(null);
    } catch (error) {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "Export des alertes impossible.";
      setAlertsError(message);
      setAlertsFeedback(null);
    } finally {
      setIsExportingAlerts(false);
    }
  }, [isAuthenticated, alertsExportDays, handleUnauthorized, setTokenError]);

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
  const deletingClientId = deleteClientMutation.isPending
    ? (deleteClientMutation.variables?.clientId ?? null)
    : null;

  const handleOpenCreateClient = useCallback(() => {
    setClientsFeedback(null);
    setClientsError(null);
    setClientModalState({ mode: "create", client: null });
  }, []);

  const handleOpenEditClient = useCallback((client: Client) => {
    setClientsFeedback(null);
    setClientsError(null);
    setClientModalState({ mode: "edit", client });
  }, []);

  const handleCloseClientModal = useCallback(() => {
    setClientModalState(null);
  }, []);

  const handleSubmitClientModal = useCallback(
    (payload: ClientFormSubmitPayload) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
      if (!clientModalState) {
        return;
      }
      if (clientModalState.mode === "edit" && clientModalState.client) {
        updateClientMutation.mutate({
          clientId: clientModalState.client.id,
          payload: {
            name: payload.name,
            startDate: payload.startDate,
            endDate: payload.endDate,
            recipients: payload.recipients,
            subscriptionIds: payload.subscriptionIds,
          },
        });
      } else {
        createClientMutation.mutate({
          name: payload.name,
          startDate: payload.startDate,
          endDate: payload.endDate,
          recipients: payload.recipients,
          subscriptionIds: payload.subscriptionIds,
        });
      }
    },
    [
      isAuthenticated,
      setTokenError,
      clientModalState,
      updateClientMutation,
      createClientMutation,
    ],
  );

  const handleDeleteClient = useCallback(
    (client: Client) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
      deleteClientMutation.mutate({ clientId: client.id, clientName: client.name });
    },
    [isAuthenticated, deleteClientMutation, setTokenError],
  );

  const handleSubmitAdminEmailConfig = useCallback(
    (payload: AdminEmailConfigPayload) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
      updateAdminEmailConfigMutation.mutate(payload);
    },
    [isAuthenticated, updateAdminEmailConfigMutation, setTokenError],
  );

  const handleSubmitGoogleRetryConfig = useCallback(
    (payload: GoogleRetryConfig) => {
      if (!isAuthenticated) {
        setTokenError("Merci de saisir un jeton administrateur.");
        return;
      }
      updateGoogleRetryConfigMutation.mutate(payload);
    },
    [isAuthenticated, updateGoogleRetryConfigMutation, setTokenError],
  );

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
      setClientsFeedback(null);
      setClientsError(null);
      setAdminEmailFeedback(null);
      setAdminEmailError(null);
  setGoogleRetryConfigFeedback(null);
  setGoogleRetryConfigMessageError(null);
      setCheckingGoogleSiret(null);
      setSelectedEstablishmentSiret(null);
      setAlertsExportDays(30);
      setIsExportingAlerts(false);
      setIsExportingGooglePlaces(false);
      resetGoogleExportRange();
      setRunDetailModal(null);
      setClientModalState(null);
      setActiveSection("dashboard");
      queryClient.invalidateQueries();
    },
    [queryClient, resetGoogleExportRange],
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
    setClientsFeedback(null);
    setClientsError(null);
    setAdminEmailFeedback(null);
    setAdminEmailError(null);
  setGoogleRetryConfigFeedback(null);
  setGoogleRetryConfigMessageError(null);
    setCheckingGoogleSiret(null);
    setSelectedEstablishmentSiret(null);
    setRunDetailModal(null);
    setClientModalState(null);
    setAlertsExportDays(30);
    setIsExportingAlerts(false);
    setIsExportingGooglePlaces(false);
    resetGoogleExportRange();
    setActiveSection("dashboard");
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
    setClientsFeedback,
    setClientsError,
    setAdminEmailFeedback,
    setAdminEmailError,
  setGoogleRetryConfigFeedback,
  setGoogleRetryConfigMessageError,
    setCheckingGoogleSiret,
    setSelectedEstablishmentSiret,
    setRunDetailModal,
    setClientModalState,
    setIsExportingGooglePlaces,
    setActiveSection,
    resetGoogleExportRange,
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

  const handleGoogleExportStartDateChange = useCallback(
    (value: string) => {
      setGoogleExportStartDate(value);
      setErrorMessage(null);
      setFeedbackMessage(null);
    },
    [setErrorMessage, setFeedbackMessage],
  );

  const handleGoogleExportEndDateChange = useCallback(
    (value: string) => {
      setGoogleExportEndDate(value);
      setErrorMessage(null);
      setFeedbackMessage(null);
    },
    [setErrorMessage, setFeedbackMessage],
  );

  const handleExportGooglePlaces = useCallback(async () => {
    if (!isAuthenticated) {
      setTokenError("Merci de saisir un jeton administrateur.");
      return;
    }
    if (!googleExportStartDate || !googleExportEndDate) {
      setErrorMessage("Merci de renseigner une date de début et une date de fin pour l'export Google Places.");
      setFeedbackMessage(null);
      return;
    }
    if (googleExportStartDate > googleExportEndDate) {
      setErrorMessage("La date de début doit précéder (ou être égale à) la date de fin.");
      setFeedbackMessage(null);
      return;
    }
    setIsExportingGooglePlaces(true);
    try {
      const blob = await googleApi.exportPlaces({
        startDate: googleExportStartDate,
        endDate: googleExportEndDate,
      });
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
  }, [
    isAuthenticated,
    googleExportStartDate,
    googleExportEndDate,
    showError,
    setTokenError,
    setErrorMessage,
    setFeedbackMessage,
  ]);

  if (!adminToken) {
    return <AdminTokenPrompt onSubmit={handleTokenSubmit} errorMessage={tokenError} />;
  }

  const isCheckingGoogle = manualGoogleCheckMutation.isPending;
  const isDetailLoading =
    establishmentDetailQuery.isLoading ||
    (establishmentDetailQuery.isFetching && !establishmentDetailQuery.data);

  const clientsIsRefreshing = useRefreshIndicator(
    clientsQuery.isFetching && !clientsQuery.isLoading,
    { delay: 300, minVisible: 250 },
  );
  const adminConfigIsRefreshing = useRefreshIndicator(
    adminEmailConfigQuery.isFetching && !adminEmailConfigQuery.isLoading,
    { delay: 300, minVisible: 250 },
  );
  const googleRetryConfigIsRefreshing = useRefreshIndicator(
    googleRetryConfigQuery.isFetching && !googleRetryConfigQuery.isLoading,
    { delay: 300, minVisible: 250 },
  );
  const establishmentsHasNextPage = (establishmentsQueryResult.data?.length ?? 0) === establishmentsLimit;
  const deletingEstablishmentSiret = deleteEstablishmentMutation.isPending
    ? ((deleteEstablishmentMutation.variables as string | null | undefined) ?? null)
    : null;

  return (
    <>
      <div className="app-frame">
        <SidebarNav sections={NAV_SECTIONS} activeSection={activeSection} onSelect={setActiveSection} />
        <div className="app-frame-content">
          <AppHeader onTokenReset={handleTokenReset} />
          <main className="app-main">
            {activeSection === "dashboard" ? (
              <DashboardView
                stats={statsQuery.data}
                isStatsLoading={statsQuery.isLoading}
                statsError={statsQuery.error as Error | null}
                onRefreshStats={() => statsQuery.refetch()}
                onTriggerSync={handleTriggerSync}
                isTriggeringSync={syncMutation.isPending}
                onExportGooglePlaces={handleExportGooglePlaces}
                isExportingGooglePlaces={isExportingGooglePlaces}
                googleExportStartDate={googleExportStartDate}
                googleExportEndDate={googleExportEndDate}
                onGoogleExportStartDateChange={handleGoogleExportStartDateChange}
                onGoogleExportEndDateChange={handleGoogleExportEndDateChange}
                googleRetryConfig={googleRetryConfigQuery.data}
                isGoogleRetryConfigLoading={googleRetryConfigQuery.isLoading}
                isGoogleRetryConfigRefreshing={googleRetryConfigIsRefreshing}
                googleRetryConfigError={googleRetryConfigQuery.error as Error | null}
                onRefreshGoogleRetryConfig={() => googleRetryConfigQuery.refetch()}
                onSubmitGoogleRetryConfig={handleSubmitGoogleRetryConfig}
                isSavingGoogleRetryConfig={updateGoogleRetryConfigMutation.isPending}
                googleRetryConfigFeedback={googleRetryConfigFeedback}
                googleRetryConfigMessageError={googleRetryConfigMessageError}
                feedbackMessage={feedbackMessage}
                errorMessage={errorMessage}
                isStatsRefreshing={statsIsRefreshing}
                metrics={dashboardQuery.data}
                isMetricsLoading={dashboardQuery.isLoading}
                metricsError={dashboardQuery.error as Error | null}
                onRefreshMetrics={() => dashboardQuery.refetch()}
                isMetricsRefreshing={metricsIsRefreshing}
                days={DASHBOARD_DAYS}
                onSelectDay={handleDashboardDaySelect}
                selectedDay={runDetailModal?.date ?? null}
                hasActiveRun={isSyncActive}
              />
            ) : null}

            {activeSection === "sync" ? (
              <SyncView
                runs={syncRunsQuery.data}
                isRunsLoading={syncRunsQuery.isLoading}
                runsError={syncRunsQuery.error as Error | null}
                runsLimit={syncRunsLimit}
                onRunsLimitChange={setSyncRunsLimit}
                onRefreshRuns={() => syncRunsQuery.refetch()}
                onDeleteRun={handleDeleteRun}
                deletingRunId={deletingRunId}
                isDeletingRun={deleteRunMutation.isPending}
                isRunsRefreshing={runsIsRefreshing}
                states={syncStateQuery.data}
                isStatesLoading={syncStateQuery.isLoading}
                statesError={syncStateQuery.error as Error | null}
                onRefreshStates={() => syncStateQuery.refetch()}
                isStatesRefreshing={statesIsRefreshing}
              />
            ) : null}

            {activeSection === "alerts" ? (
              <AlertsView
                alerts={alertsQuery.data}
                isLoading={alertsQuery.isLoading}
                error={alertsQuery.error as Error | null}
                limit={alertsLimit}
                onLimitChange={setAlertsLimit}
                onRefresh={() => alertsQuery.refetch()}
                exportDays={alertsExportDays}
                onExportDaysChange={handleAlertsExportDaysChange}
                onExportAlerts={handleExportAlerts}
                isExportingAlerts={isExportingAlerts}
                onTriggerGoogleCheck={handleTriggerGoogleCheckFromAlerts}
                isCheckingGoogle={isCheckingGoogle}
                checkingGoogleSiret={checkingGoogleSiret}
                feedbackMessage={alertsFeedback}
                errorMessage={alertsError}
                onSelectAlert={handleOpenEstablishmentDetail}
              />
            ) : null}

            {activeSection === "clients" ? (
              <ClientsView
                clients={clientsQuery.data}
                isLoading={clientsQuery.isLoading}
                isRefreshing={clientsIsRefreshing}
                error={clientsQuery.error as Error | null}
                feedbackMessage={clientsFeedback}
                errorMessage={clientsError}
                onRefresh={() => clientsQuery.refetch()}
                onCreateClient={handleOpenCreateClient}
                onEditClient={handleOpenEditClient}
                onDeleteClient={handleDeleteClient}
                deletingClientId={deletingClientId}
              />
            ) : null}

            {activeSection === "naf-config" ? (
              <NafConfigView
                categories={nafCategoriesQuery.data}
                isLoading={nafCategoriesQuery.isLoading}
                isFetching={nafCategoriesQuery.isFetching}
                error={nafCategoriesQuery.error as Error | null}
                onRefresh={() => nafCategoriesQuery.refetch()}
                isAuthenticated={isAuthenticated}
                onRequireToken={requestAdminToken}
                onUnauthorized={handleUnauthorized}
              />
            ) : null}

            {activeSection === "emails" ? (
              <EmailsView
                adminConfig={adminEmailConfigQuery.data}
                isAdminConfigLoading={adminEmailConfigQuery.isLoading}
                isAdminConfigRefreshing={adminConfigIsRefreshing}
                adminConfigError={adminEmailConfigQuery.error as Error | null}
                adminConfigFeedback={adminEmailFeedback}
                adminConfigMessageError={adminEmailError}
                onRefreshAdminConfig={() => adminEmailConfigQuery.refetch()}
                onSubmitAdminConfig={handleSubmitAdminEmailConfig}
                isSubmittingAdminConfig={updateAdminEmailConfigMutation.isPending}
                onSendTestEmail={handleSendEmailTest}
                isSendingTestEmail={emailTestMutation.isPending}
                emailFeedbackMessage={emailFeedback}
                emailErrorMessage={emailError}
                onResetEmailMessages={handleResetEmailMessages}
              />
            ) : null}

            {activeSection === "establishments" ? (
              <EstablishmentsView
                establishments={establishmentsQueryResult.data}
                isLoading={establishmentsQueryResult.isLoading}
                error={establishmentsQueryResult.error as Error | null}
                limit={establishmentsLimit}
                page={establishmentsPage}
                query={establishmentsQuery}
                hasNextPage={establishmentsHasNextPage}
                onLimitChange={handleEstablishmentsLimitChange}
                onPageChange={handleEstablishmentsPageChange}
                onQueryChange={handleEstablishmentsQueryChange}
                onRefresh={() => establishmentsQueryResult.refetch()}
                onDeleteEstablishment={handleDeleteEstablishment}
                deletingSiret={deletingEstablishmentSiret}
                isDeletingOne={deleteEstablishmentMutation.isPending}
                feedbackMessage={establishmentsFeedback}
                errorMessage={establishmentsError}
                individualFilter={establishmentsIndividualFilter}
                onIndividualFilterChange={handleEstablishmentsIndividualFilterChange}
                onTriggerGoogleCheck={handleTriggerGoogleCheckFromEstablishments}
                isCheckingGoogle={isCheckingGoogle}
                checkingGoogleSiret={checkingGoogleSiret}
                onSelectEstablishment={handleOpenEstablishmentDetail}
              />
            ) : null}
          </main>
        </div>
      </div>

      <EstablishmentDetailModal
        isOpen={Boolean(selectedEstablishmentSiret)}
        establishment={establishmentDetailQuery.data ?? null}
        isLoading={isDetailLoading}
        errorMessage={establishmentDetailErrorMessage}
        onClose={handleCloseEstablishmentDetail}
      />

      <ClientModal
        isOpen={Boolean(clientModalState)}
        mode={clientModalState?.mode ?? "create"}
        client={clientModalState?.client ?? null}
        nafCategories={nafCategoriesQuery.data}
        isLoadingNafCategories={nafCategoriesQuery.isLoading}
        onSubmit={handleSubmitClientModal}
        onCancel={handleCloseClientModal}
        isProcessing={createClientMutation.isPending || updateClientMutation.isPending}
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
    </>
  );
};

export default App;

import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ApiError, alertsApi } from "../../api";
import type { Alert } from "../../types";
import { AlertsView } from "../../components/views/AlertsView";
import { useGoogleCheckMutation } from "../hooks/useGoogleCheckMutation";

type Props = {
  onUnauthorized: () => void;
  onOpenEstablishmentDetail: (siret: string) => void;
};

export const AlertsSection = ({ onUnauthorized, onOpenEstablishmentDetail }: Props) => {
  const [limit, setLimit] = useState(20);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [exportDays, setExportDays] = useState(30);
  const [isExportingAlerts, setIsExportingAlerts] = useState(false);

  const alertsQuery = useQuery<Alert[]>({
    queryKey: ["alerts", limit],
    queryFn: () => alertsApi.fetchRecent(limit),
  });

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

  const { trigger: triggerGoogleCheck, checkingSiret, isPending } = useGoogleCheckMutation({
    onUnauthorized,
    onSuccess: (result, payload) => {
      const message = result.message || `Vérification Google relancée pour ${payload.siret}.`;
      setFeedbackMessage(message);
      setErrorMessage(null);
    },
    onError: (message) => {
      setErrorMessage(message);
      setFeedbackMessage(null);
    },
  });

  const handleExport = useCallback(async () => {
    setFeedbackMessage(null);
    setErrorMessage(null);
    setIsExportingAlerts(true);
    try {
      const days = Math.max(1, Math.min(Math.round(exportDays), 365));
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
      setFeedbackMessage(`Export des alertes (${days} jours) téléchargé.`);
    } catch (error) {
      showError(error);
    } finally {
      setIsExportingAlerts(false);
    }
  }, [exportDays, showError]);

  const handleGoogleCheck = useCallback(
    (siret: string) => {
      triggerGoogleCheck({ siret, source: "alerts" });
    },
    [triggerGoogleCheck],
  );

  const alertsError = alertsQuery.error instanceof Error ? alertsQuery.error : null;

  const handleLimitChange = useCallback((value: number) => {
    setLimit(Math.max(5, Math.min(value, 100)));
  }, []);

  const handleExportDaysChange = useCallback((value: number) => {
    const nextValue = Number.isFinite(value) ? Math.round(value) : 30;
    const clamped = Math.max(1, Math.min(nextValue, 365));
    setExportDays(clamped);
  }, []);

  const checkingSiretValue = useMemo(() => (isPending ? checkingSiret : null), [checkingSiret, isPending]);

  return (
    <AlertsView
      alerts={alertsQuery.data}
      isLoading={alertsQuery.isLoading}
      error={alertsError}
      limit={limit}
      onLimitChange={handleLimitChange}
      onRefresh={() => alertsQuery.refetch()}
      exportDays={exportDays}
      onExportDaysChange={handleExportDaysChange}
      onExportAlerts={handleExport}
      isExportingAlerts={isExportingAlerts}
      onTriggerGoogleCheck={handleGoogleCheck}
      isCheckingGoogle={isPending}
      checkingGoogleSiret={checkingSiretValue}
      feedbackMessage={feedbackMessage}
      errorMessage={errorMessage}
      onSelectAlert={onOpenEstablishmentDetail}
    />
  );
};

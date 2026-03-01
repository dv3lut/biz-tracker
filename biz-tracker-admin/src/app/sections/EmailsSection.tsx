import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, adminConfigApi, emailApi, type AdminEmailConfigPayload } from "../../api";
import type { AdminEmailConfig, EmailTestPayload, EmailTestResult } from "../../types";
import { EmailsView } from "../../components/views/EmailsView";
import { useRefreshIndicator } from "../../hooks/useRefreshIndicator";

const buildErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
};

type Props = {
  onUnauthorized: () => void;
};

export const EmailsSection = ({ onUnauthorized }: Props) => {
  const queryClient = useQueryClient();
  const [adminConfigFeedback, setAdminConfigFeedback] = useState<string | null>(null);
  const [adminConfigError, setAdminConfigError] = useState<string | null>(null);
  const [emailFeedback, setEmailFeedback] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);

  const adminEmailConfigQuery = useQuery<AdminEmailConfig>({
    queryKey: ["admin-email-config"],
    queryFn: () => adminConfigApi.fetch(),
  });

  const adminConfigIsRefreshing = useRefreshIndicator(
    adminEmailConfigQuery.isFetching && !adminEmailConfigQuery.isLoading,
    { delay: 300, minVisible: 250 },
  );

  useEffect(() => {
    if (!adminConfigFeedback) {
      return;
    }
    const timeout = window.setTimeout(() => setAdminConfigFeedback(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [adminConfigFeedback]);

  useEffect(() => {
    if (!adminConfigError) {
      return;
    }
    const timeout = window.setTimeout(() => setAdminConfigError(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [adminConfigError]);

  useEffect(() => {
    if (!emailFeedback) {
      return;
    }
    const timeout = window.setTimeout(() => setEmailFeedback(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [emailFeedback]);

  useEffect(() => {
    if (!emailError) {
      return;
    }
    const timeout = window.setTimeout(() => setEmailError(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [emailError]);

  const handleAdminConfigError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      setAdminConfigError(buildErrorMessage(error, "La mise à jour de la configuration admin a échoué."));
      setAdminConfigFeedback(null);
    },
    [onUnauthorized],
  );

  const handleEmailError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      setEmailError(buildErrorMessage(error, "L'envoi de l'e-mail de test a échoué."));
      setEmailFeedback(null);
    },
    [onUnauthorized],
  );

  const updateAdminConfigMutation = useMutation({
    mutationFn: (payload: AdminEmailConfigPayload) => adminConfigApi.update(payload),
    onSuccess: (config) => {
      setAdminConfigFeedback("Configuration mise à jour.");
      setAdminConfigError(null);
      queryClient.setQueryData(["admin-email-config"], config);
    },
    onError: handleAdminConfigError,
  });

  const emailTestMutation = useMutation<EmailTestResult, unknown, EmailTestPayload>({
    mutationFn: (payload) => emailApi.sendTest(payload),
    onSuccess: (result) => {
      const recipients = result.recipients.length > 0 ? result.recipients.join(", ") : "destinataires configurés";
      setEmailFeedback(`E-mail de test envoyé via ${result.provider} vers ${recipients}.`);
      setEmailError(null);
    },
    onError: handleEmailError,
  });

  const adminConfigQueryError = adminEmailConfigQuery.error instanceof Error ? adminEmailConfigQuery.error : null;

  const handleResetEmailMessages = useCallback(() => {
    setEmailFeedback(null);
    setEmailError(null);
  }, []);

  return (
    <EmailsView
      adminConfig={adminEmailConfigQuery.data}
      isAdminConfigLoading={adminEmailConfigQuery.isLoading}
      isAdminConfigRefreshing={adminConfigIsRefreshing}
      adminConfigError={adminConfigQueryError}
      adminConfigFeedback={adminConfigFeedback}
      adminConfigMessageError={adminConfigError}
      onRefreshAdminConfig={() => adminEmailConfigQuery.refetch()}
      onSubmitAdminConfig={(payload) => updateAdminConfigMutation.mutate(payload)}
      isSubmittingAdminConfig={updateAdminConfigMutation.isPending}
      onSendTestEmail={(payload) => emailTestMutation.mutate(payload)}
      isSendingTestEmail={emailTestMutation.isPending}
      emailFeedbackMessage={emailFeedback}
      emailErrorMessage={emailError}
      onResetEmailMessages={handleResetEmailMessages}
    />
  );
};

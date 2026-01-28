import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, stripeSettingsApi } from "../../api";
import type {
  AdminStripeSettings,
  AdminStripeSettingsUpdatePayload,
  AdminStripeSettingsUpdateResult,
} from "../../types";
import { StripeSettingsView } from "../../components/views/StripeSettingsView";
import { useRefreshIndicator } from "../../hooks/useRefreshIndicator";

const buildErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
};

const buildSuccessMessage = (result: AdminStripeSettingsUpdateResult): string => {
  const base = `Durée d'essai mise à jour (${result.trialPeriodDays} jours).`;
  if (result.updatedTrials === 0 && result.failedTrials === 0) {
    return base;
  }
  const parts = [`${result.updatedTrials} essai(s) mis à jour`];
  if (result.failedTrials > 0) {
    parts.push(`${result.failedTrials} en échec`);
  }
  return `${base} ${parts.join(", ")}.`;
};

type Props = {
  onUnauthorized: () => void;
};

export const StripeSettingsSection = ({ onUnauthorized }: Props) => {
  const queryClient = useQueryClient();
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const stripeSettingsQuery = useQuery<AdminStripeSettings>({
    queryKey: ["admin-stripe-settings"],
    queryFn: () => stripeSettingsApi.fetch(),
  });

  const isRefreshing = useRefreshIndicator(
    stripeSettingsQuery.isFetching && !stripeSettingsQuery.isLoading,
    { delay: 300, minVisible: 250 },
  );

  useEffect(() => {
    if (!feedbackMessage) {
      return;
    }
    const timeout = window.setTimeout(() => setFeedbackMessage(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [feedbackMessage]);

  useEffect(() => {
    if (!errorMessage) {
      return;
    }
    const timeout = window.setTimeout(() => setErrorMessage(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [errorMessage]);

  const handleError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      setErrorMessage(buildErrorMessage(error, "La mise à jour de l'essai Stripe a échoué."));
      setFeedbackMessage(null);
    },
    [onUnauthorized],
  );

  const updateMutation = useMutation<
    AdminStripeSettingsUpdateResult,
    unknown,
    AdminStripeSettingsUpdatePayload
  >({
    mutationFn: (payload) => stripeSettingsApi.update(payload),
    onSuccess: (result) => {
      setFeedbackMessage(buildSuccessMessage(result));
      setErrorMessage(null);
      queryClient.setQueryData(["admin-stripe-settings"], {
        trialPeriodDays: result.trialPeriodDays,
      });
    },
    onError: handleError,
  });

  const queryError = stripeSettingsQuery.error instanceof Error ? stripeSettingsQuery.error : null;

  return (
    <StripeSettingsView
      settings={stripeSettingsQuery.data}
      isLoading={stripeSettingsQuery.isLoading}
      isRefreshing={isRefreshing}
      error={queryError}
      feedbackMessage={feedbackMessage}
      errorMessage={errorMessage}
      onRefresh={() => stripeSettingsQuery.refetch()}
      onSubmit={(payload) => updateMutation.mutate(payload)}
      isSubmitting={updateMutation.isPending}
    />
  );
};

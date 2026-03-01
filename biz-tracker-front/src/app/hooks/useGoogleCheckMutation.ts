import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError, googleApi } from "../../api";
import type { GoogleCheckResult } from "../../types";

type GoogleCheckSource = "alerts" | "establishments" | "manual";

type TriggerPayload = {
  siret: string;
  source: GoogleCheckSource;
  notify?: boolean;
};

type Options = {
  onUnauthorized: () => void;
  onSuccess: (result: GoogleCheckResult, payload: TriggerPayload) => void;
  onError: (message: string, payload: TriggerPayload) => void;
};

export const useGoogleCheckMutation = ({ onUnauthorized, onSuccess, onError }: Options) => {
  const queryClient = useQueryClient();
  const [checkingSiret, setCheckingSiret] = useState<string | null>(null);

  const mutation = useMutation<GoogleCheckResult, unknown, TriggerPayload>({
    mutationFn: ({ siret, source, notify }) =>
      googleApi.checkEstablishment(siret, {
        notifyClients: notify ?? source !== "manual",
      }),
    onMutate: ({ siret }) => {
      setCheckingSiret(siret);
    },
    onSuccess: (result, payload) => {
      onSuccess(result, payload);
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["establishments"] });
      queryClient.invalidateQueries({ queryKey: ["establishment-detail", payload.siret] });
    },
    onError: (error, payload) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "La vérification Google a échoué.";
      onError(message, payload);
    },
    onSettled: () => {
      setCheckingSiret(null);
    },
  });

  const trigger = useCallback(
    (payload: TriggerPayload) => {
      mutation.mutate(payload);
    },
    [mutation],
  );

  return {
    trigger,
    checkingSiret,
    isPending: mutation.isPending,
  } as const;
};

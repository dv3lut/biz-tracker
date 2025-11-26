import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, establishmentsApi } from "../../api";
import type { EstablishmentDetail } from "../../types";

const buildErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Impossible de charger la fiche établissement.";
};

export const useEstablishmentDetailModal = (isAuthenticated: boolean, onUnauthorized: () => void) => {
  const [selectedSiret, setSelectedSiret] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const detailQuery = useQuery<EstablishmentDetail>({
    queryKey: ["establishment-detail", selectedSiret],
    queryFn: () => establishmentsApi.fetchOne(selectedSiret!),
    enabled: isAuthenticated && Boolean(selectedSiret),
    staleTime: 60_000,
  });

  const isLoading = detailQuery.isLoading || (detailQuery.isFetching && !detailQuery.data);
  const errorMessage = detailQuery.error ? buildErrorMessage(detailQuery.error) : null;

  const openDetail = useCallback((siret: string) => {
    setSelectedSiret(siret);
  }, []);

  const closeDetail = useCallback(() => {
    setSelectedSiret(null);
  }, []);

  useEffect(() => {
    if (!selectedSiret) {
      return;
    }
    const error = detailQuery.error;
    if (error instanceof ApiError && error.status === 403) {
      onUnauthorized();
      setSelectedSiret(null);
    }
  }, [detailQuery.error, onUnauthorized, selectedSiret]);

  const modalProps = useMemo(
    () => ({
      isOpen: Boolean(selectedSiret),
      establishment: detailQuery.data ?? null,
      isLoading,
      errorMessage,
      onClose: closeDetail,
    }),
    [selectedSiret, detailQuery.data, isLoading, errorMessage, closeDetail],
  );

  const invalidateDetail = useCallback(
    (siret: string) => {
      queryClient.invalidateQueries({ queryKey: ["establishment-detail", siret] });
    },
    [queryClient],
  );

  return {
    openDetail,
    closeDetail,
    modalProps,
    invalidateDetail,
  } as const;
};

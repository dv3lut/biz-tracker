import { useCallback, useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, establishmentsApi } from "../../api";
import type { Establishment, EstablishmentIndividualFilter } from "../../types";
import { EstablishmentsView } from "../../components/views/EstablishmentsView";
import { useGoogleCheckMutation } from "../hooks/useGoogleCheckMutation";

const buildErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Une erreur est survenue.";
};

type Props = {
  onUnauthorized: () => void;
  onOpenEstablishmentDetail: (siret: string) => void;
};

export const EstablishmentsSection = ({ onUnauthorized, onOpenEstablishmentDetail }: Props) => {
  const queryClient = useQueryClient();
  const [limit, setLimit] = useState(20);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [individualFilter, setIndividualFilter] = useState<EstablishmentIndividualFilter>("all");
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const establishmentsQuery = useQuery<Establishment[]>({
    queryKey: ["establishments", limit, page, query, individualFilter],
    queryFn: () =>
      establishmentsApi.fetchMany({
        limit,
        offset: page * limit,
        q: query ? query : undefined,
        isIndividual:
          individualFilter === "all" ? undefined : individualFilter === "individual",
      }),
    placeholderData: keepPreviousData,
  });

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

  const showError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      setErrorMessage(buildErrorMessage(error));
      setFeedbackMessage(null);
    },
    [onUnauthorized],
  );

  const invalidateEstablishments = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["establishments"] });
  }, [queryClient]);

  const deleteEstablishmentMutation = useMutation<void, unknown, string>({
    mutationFn: (siret) => establishmentsApi.deleteOne(siret),
    onSuccess: (_, siret) => {
      setFeedbackMessage(`Établissement ${siret} supprimé.`);
      setErrorMessage(null);
      invalidateEstablishments();
    },
    onError: showError,
  });

  const { trigger: triggerGoogleCheck, checkingSiret, isPending: isCheckingGoogle } = useGoogleCheckMutation({
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

  const handleDeleteEstablishment = useCallback(
    (siret: string) => {
      deleteEstablishmentMutation.mutate(siret);
    },
    [deleteEstablishmentMutation],
  );

  const handleGoogleCheck = useCallback(
    (siret: string) => {
      triggerGoogleCheck({ siret, source: "establishments" });
    },
    [triggerGoogleCheck],
  );

  const handleLimitChange = useCallback((value: number) => {
    setLimit(value);
    setPage(0);
  }, []);

  const handlePageChange = useCallback((value: number) => {
    setPage(value < 0 ? 0 : value);
  }, []);

  const handleQueryChange = useCallback((value: string) => {
    setQuery(value);
    setPage(0);
  }, []);

  const handleIndividualFilterChange = useCallback((value: EstablishmentIndividualFilter) => {
    setIndividualFilter(value);
    setPage(0);
  }, []);

  const deletingSiret = useMemo(() => {
    if (!deleteEstablishmentMutation.isPending) {
      return null;
    }
    return (deleteEstablishmentMutation.variables as string | undefined) ?? null;
  }, [deleteEstablishmentMutation.isPending, deleteEstablishmentMutation.variables]);

  const hasNextPage = (establishmentsQuery.data?.length ?? 0) === limit;

  const establishmentsError = establishmentsQuery.error instanceof Error ? establishmentsQuery.error : null;

  return (
    <EstablishmentsView
      establishments={establishmentsQuery.data}
      isLoading={establishmentsQuery.isLoading}
      error={establishmentsError}
      limit={limit}
      page={page}
      query={query}
      individualFilter={individualFilter}
      hasNextPage={hasNextPage}
      onLimitChange={handleLimitChange}
      onPageChange={handlePageChange}
      onQueryChange={handleQueryChange}
      onIndividualFilterChange={handleIndividualFilterChange}
      onRefresh={() => establishmentsQuery.refetch()}
      onDeleteEstablishment={handleDeleteEstablishment}
      deletingSiret={deletingSiret}
      isDeletingOne={deleteEstablishmentMutation.isPending}
      feedbackMessage={feedbackMessage}
      errorMessage={errorMessage}
      onTriggerGoogleCheck={handleGoogleCheck}
      isCheckingGoogle={isCheckingGoogle}
      checkingGoogleSiret={checkingSiret}
      onSelectEstablishment={onOpenEstablishmentDetail}
    />
  );
};

import { useCallback, useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { ApiError, establishmentsApi, googleApi, nafApi, regionsApi } from "../../api";
import type {
  Establishment,
  EstablishmentIndividualFilter,
  GoogleFindPlaceDebugResult,
  LinkedInStatus,
  NafCategory,
  Region,
} from "../../types";
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
  const [draftQuery, setDraftQuery] = useState("");
  const [draftNafCodes, setDraftNafCodes] = useState<string[]>([]);
  const [draftDepartmentCodes, setDraftDepartmentCodes] = useState<string[]>([]);
  const [draftAddedFrom, setDraftAddedFrom] = useState("");
  const [draftAddedTo, setDraftAddedTo] = useState("");
  const [draftIndividualFilter, setDraftIndividualFilter] = useState<EstablishmentIndividualFilter>("all");
  const [draftGoogleCheckStatus, setDraftGoogleCheckStatus] = useState("");
  const [draftLinkedinStatuses, setDraftLinkedinStatuses] = useState<LinkedInStatus[]>([]);

  const [query, setQuery] = useState("");
  const [nafCodes, setNafCodes] = useState<string[]>([]);
  const [departmentCodes, setDepartmentCodes] = useState<string[]>([]);
  const [addedFrom, setAddedFrom] = useState("");
  const [addedTo, setAddedTo] = useState("");
  const [individualFilter, setIndividualFilter] = useState<EstablishmentIndividualFilter>("all");
  const [googleCheckStatus, setGoogleCheckStatus] = useState("");
  const [linkedinStatuses, setLinkedinStatuses] = useState<LinkedInStatus[]>([]);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [googleFindPlaceDebugModal, setGoogleFindPlaceDebugModal] = useState<
    { siret: string; result: GoogleFindPlaceDebugResult } | null
  >(null);

  const nafCategoriesQuery = useQuery<NafCategory[]>({
    queryKey: ["naf-categories"],
    queryFn: () => nafApi.listCategories(),
    staleTime: 5 * 60 * 1000,
  });

  const regionsQuery = useQuery<Region[]>({
    queryKey: ["regions"],
    queryFn: () => regionsApi.list(),
    staleTime: 5 * 60 * 1000,
  });

  const establishmentsQuery = useQuery<{ total: number; items: Establishment[] }>({
    queryKey: [
      "establishments",
      limit,
      page,
      query,
      nafCodes,
      departmentCodes,
      addedFrom,
      addedTo,
      individualFilter,
      googleCheckStatus,
      linkedinStatuses,
    ],
    queryFn: () =>
      establishmentsApi.fetchMany({
        limit,
        offset: page * limit,
        q: query ? query : undefined,
        nafCodes: nafCodes.length > 0 ? nafCodes : undefined,
        departmentCodes: departmentCodes.length > 0 ? departmentCodes : undefined,
        addedFrom: addedFrom ? addedFrom : undefined,
        addedTo: addedTo ? addedTo : undefined,
        googleCheckStatus: googleCheckStatus ? googleCheckStatus : undefined,
        isIndividual:
          individualFilter === "all" ? undefined : individualFilter === "individual",
        linkedinStatuses: linkedinStatuses.length > 0 ? linkedinStatuses : undefined,
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
      const message = buildErrorMessage(error);
      setErrorMessage(message);
      setFeedbackMessage(null);

      toast.error(message, { id: message });
    },
    [onUnauthorized],
  );

  useEffect(() => {
    if (!nafCategoriesQuery.error) {
      return;
    }
    showError(nafCategoriesQuery.error);
  }, [nafCategoriesQuery.error, showError]);

  useEffect(() => {
    if (!regionsQuery.error) {
      return;
    }
    showError(regionsQuery.error);
  }, [regionsQuery.error, showError]);


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

      toast.error(message, { id: message });
    },
  });

  const [debuggingGoogleFindPlaceSiret, setDebuggingGoogleFindPlaceSiret] = useState<string | null>(null);
  const googleFindPlaceDebugMutation = useMutation<GoogleFindPlaceDebugResult, unknown, string>({
    mutationFn: (siret) => googleApi.debugFindPlace(siret),
    onMutate: (siret) => {
      setDebuggingGoogleFindPlaceSiret(siret);
    },
    onSuccess: (result, siret) => {
      setGoogleFindPlaceDebugModal({ siret, result });
      setErrorMessage(null);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      const message = buildErrorMessage(error);
      setErrorMessage(message);
      setFeedbackMessage(null);

      toast.error(message, { id: message });
    },
    onSettled: () => {
      setDebuggingGoogleFindPlaceSiret(null);
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

  const handleGoogleFindPlaceDebug = useCallback(
    (siret: string) => {
      googleFindPlaceDebugMutation.mutate(siret);
    },
    [googleFindPlaceDebugMutation],
  );

  const handleLimitChange = useCallback((value: number) => {
    setLimit(value);
    setPage(0);
  }, []);

  const handlePageChange = useCallback((value: number) => {
    setPage(value < 0 ? 0 : value);
  }, []);

  const handleQueryChange = useCallback((value: string) => {
    setDraftQuery(value);
  }, []);

  const handleNafCodesChange = useCallback((value: string[]) => {
    setDraftNafCodes(value);
  }, []);

  const handleDepartmentCodesChange = useCallback((value: string[]) => {
    setDraftDepartmentCodes(value);
  }, []);

  const handleAddedFromChange = useCallback((value: string) => {
    setDraftAddedFrom(value);
  }, []);

  const handleAddedToChange = useCallback((value: string) => {
    setDraftAddedTo(value);
  }, []);

  const handleIndividualFilterChange = useCallback((value: EstablishmentIndividualFilter) => {
    setDraftIndividualFilter(value);
  }, []);

  const handleGoogleCheckStatusChange = useCallback((value: string) => {
    setDraftGoogleCheckStatus(value);
  }, []);

  const handleLinkedinStatusesChange = useCallback((value: LinkedInStatus[]) => {
    setDraftLinkedinStatuses(value);
  }, []);

  const handleApplyFilters = useCallback(() => {
    setQuery(draftQuery);
    setNafCodes(draftNafCodes);
    setDepartmentCodes(draftDepartmentCodes);
    setAddedFrom(draftAddedFrom);
    setAddedTo(draftAddedTo);
    setIndividualFilter(draftIndividualFilter);
    setGoogleCheckStatus(draftGoogleCheckStatus);
    setLinkedinStatuses(draftLinkedinStatuses);
    setPage(0);
  }, [
    draftAddedFrom,
    draftAddedTo,
    draftGoogleCheckStatus,
    draftIndividualFilter,
    draftNafCodes,
    draftQuery,
    draftDepartmentCodes,
    draftLinkedinStatuses,
  ]);

  const handleResetFilters = useCallback(() => {
    setDraftQuery("");
    setDraftNafCodes([]);
    setDraftDepartmentCodes([]);
    setDraftAddedFrom("");
    setDraftAddedTo("");
    setDraftIndividualFilter("all");
    setDraftGoogleCheckStatus("");
    setDraftLinkedinStatuses([]);

    setQuery("");
    setNafCodes([]);
    setDepartmentCodes([]);
    setAddedFrom("");
    setAddedTo("");
    setIndividualFilter("all");
    setGoogleCheckStatus("");
    setLinkedinStatuses([]);
    setPage(0);
  }, []);

  const hasPendingFilters = useMemo(() => {
    if (draftQuery !== query) {
      return true;
    }
    if (draftAddedFrom !== addedFrom) {
      return true;
    }
    if (draftAddedTo !== addedTo) {
      return true;
    }
    if (draftIndividualFilter !== individualFilter) {
      return true;
    }
    if (draftGoogleCheckStatus !== googleCheckStatus) {
      return true;
    }
    if (draftLinkedinStatuses.length !== linkedinStatuses.length) {
      return true;
    }
    if (draftNafCodes.length !== nafCodes.length) {
      return true;
    }
    if (draftDepartmentCodes.length !== departmentCodes.length) {
      return true;
    }
    const a = [...draftNafCodes].sort().join(",");
    const b = [...nafCodes].sort().join(",");
    if (a !== b) {
      return true;
    }
    const departmentA = [...draftDepartmentCodes].sort().join(",");
    const departmentB = [...departmentCodes].sort().join(",");
    if (departmentA !== departmentB) {
      return true;
    }
    const linkedinA = [...draftLinkedinStatuses].sort().join(",");
    const linkedinB = [...linkedinStatuses].sort().join(",");
    return linkedinA !== linkedinB;
  }, [
    addedFrom,
    addedTo,
    draftAddedFrom,
    draftAddedTo,
    draftGoogleCheckStatus,
    draftIndividualFilter,
    draftNafCodes,
    draftQuery,
    googleCheckStatus,
    individualFilter,
    nafCodes,
    query,
    draftDepartmentCodes,
    departmentCodes,
    draftLinkedinStatuses,
    linkedinStatuses,
  ]);

  const deletingSiret = useMemo(() => {
    if (!deleteEstablishmentMutation.isPending) {
      return null;
    }
    return (deleteEstablishmentMutation.variables as string | undefined) ?? null;
  }, [deleteEstablishmentMutation.isPending, deleteEstablishmentMutation.variables]);

  const hasNextPage = (establishmentsQuery.data?.items.length ?? 0) === limit;

  const establishmentsError = establishmentsQuery.error instanceof Error ? establishmentsQuery.error : null;

  return (
    <EstablishmentsView
      establishments={establishmentsQuery.data?.items}
      resultCount={establishmentsQuery.data?.total}
      isResultCountLoading={establishmentsQuery.isLoading}
      isLoading={establishmentsQuery.isLoading}
      error={establishmentsError}
      nafCategories={nafCategoriesQuery.data}
      isLoadingNafCategories={nafCategoriesQuery.isLoading}
      regions={regionsQuery.data}
      isLoadingRegions={regionsQuery.isLoading}
      limit={limit}
      page={page}
      query={draftQuery}
      nafCodes={draftNafCodes}
      departmentCodes={draftDepartmentCodes}
      addedFrom={draftAddedFrom}
      addedTo={draftAddedTo}
      individualFilter={draftIndividualFilter}
      googleCheckStatus={draftGoogleCheckStatus}
      linkedinStatuses={draftLinkedinStatuses}
      hasNextPage={hasNextPage}
      onLimitChange={handleLimitChange}
      onPageChange={handlePageChange}
      onQueryChange={handleQueryChange}
      onNafCodesChange={handleNafCodesChange}
      onDepartmentCodesChange={handleDepartmentCodesChange}
      onAddedFromChange={handleAddedFromChange}
      onAddedToChange={handleAddedToChange}
      onApplyFilters={handleApplyFilters}
      hasPendingFilters={hasPendingFilters}
      onResetFilters={handleResetFilters}
      onIndividualFilterChange={handleIndividualFilterChange}
      onGoogleCheckStatusChange={handleGoogleCheckStatusChange}
      onLinkedinStatusesChange={handleLinkedinStatusesChange}
      onRefresh={() => establishmentsQuery.refetch()}
      onDeleteEstablishment={handleDeleteEstablishment}
      deletingSiret={deletingSiret}
      isDeletingOne={deleteEstablishmentMutation.isPending}
      feedbackMessage={feedbackMessage}
      errorMessage={errorMessage}
      onTriggerGoogleCheck={handleGoogleCheck}
      isCheckingGoogle={isCheckingGoogle}
      checkingGoogleSiret={checkingSiret}
      onTriggerGoogleFindPlaceDebug={handleGoogleFindPlaceDebug}
      isDebuggingGoogleFindPlace={googleFindPlaceDebugMutation.isPending}
      debuggingGoogleFindPlaceSiret={debuggingGoogleFindPlaceSiret}
      googleFindPlaceDebugModal={googleFindPlaceDebugModal}
      onCloseGoogleFindPlaceDebugModal={() => setGoogleFindPlaceDebugModal(null)}
      onSelectEstablishment={onOpenEstablishmentDetail}
    />
  );
};

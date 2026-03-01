import { useCallback, useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { ApiError, clientsApi, establishmentsApi, googleApi, nafApi, regionsApi } from "../../api";
import type {
  Client,
  Establishment,
  EstablishmentDateFilterType,
  EstablishmentIndividualFilter,
  GoogleFindPlaceDebugResult,
  LinkedInStatus,
  NafCategory,
  Region,
  WebsiteScrapeStatus,
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
  const [draftDateFilterType, setDraftDateFilterType] = useState<EstablishmentDateFilterType>("added");
  const [draftDateFrom, setDraftDateFrom] = useState("");
  const [draftDateTo, setDraftDateTo] = useState("");
  const [draftIndividualFilter, setDraftIndividualFilter] = useState<EstablishmentIndividualFilter>("all");
  const [draftGoogleCheckStatuses, setDraftGoogleCheckStatuses] = useState<string[]>([]);
  const [draftSelectedClientId, setDraftSelectedClientId] = useState("");
  const [draftLinkedinStatuses, setDraftLinkedinStatuses] = useState<LinkedInStatus[]>([]);
  const [draftWebsiteScrapeStatuses, setDraftWebsiteScrapeStatuses] = useState<WebsiteScrapeStatus[]>([]);

  const [query, setQuery] = useState("");
  const [nafCodes, setNafCodes] = useState<string[]>([]);
  const [departmentCodes, setDepartmentCodes] = useState<string[]>([]);
  const [dateFilterType, setDateFilterType] = useState<EstablishmentDateFilterType>("added");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [individualFilter, setIndividualFilter] = useState<EstablishmentIndividualFilter>("all");
  const [googleCheckStatuses, setGoogleCheckStatuses] = useState<string[]>([]);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [linkedinStatuses, setLinkedinStatuses] = useState<LinkedInStatus[]>([]);
  const [websiteScrapeStatuses, setWebsiteScrapeStatuses] = useState<WebsiteScrapeStatus[]>([]);
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

  const clientsQuery = useQuery<Client[]>({
    queryKey: ["clients"],
    queryFn: () => clientsApi.list(),
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
      dateFilterType,
      dateFrom,
      dateTo,
      individualFilter,
      googleCheckStatuses,
      selectedClientId,
      linkedinStatuses,
      websiteScrapeStatuses,
    ],
    queryFn: () =>
      establishmentsApi.fetchMany({
        limit,
        offset: page * limit,
        q: query ? query : undefined,
        nafCodes: nafCodes.length > 0 ? nafCodes : undefined,
        departmentCodes: departmentCodes.length > 0 ? departmentCodes : undefined,
        addedFrom: dateFilterType === "added" && dateFrom ? dateFrom : undefined,
        addedTo: dateFilterType === "added" && dateTo ? dateTo : undefined,
        creationFrom: dateFilterType === "sirene_creation" && dateFrom ? dateFrom : undefined,
        creationTo: dateFilterType === "sirene_creation" && dateTo ? dateTo : undefined,
        lastTreatmentFrom:
          dateFilterType === "sirene_last_treatment" && dateFrom ? dateFrom : undefined,
        lastTreatmentTo: dateFilterType === "sirene_last_treatment" && dateTo ? dateTo : undefined,
        googleCheckStatuses: googleCheckStatuses.length > 0 ? googleCheckStatuses : undefined,
        isIndividual:
          individualFilter === "all" ? undefined : individualFilter === "individual",
        linkedinStatuses: linkedinStatuses.length > 0 ? linkedinStatuses : undefined,
        websiteScrapeStatuses: websiteScrapeStatuses.length > 0 ? websiteScrapeStatuses : undefined,
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

  useEffect(() => {
    if (!clientsQuery.error) {
      return;
    }
    showError(clientsQuery.error);
  }, [clientsQuery.error, showError]);


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

  const handleDateFilterTypeChange = useCallback((value: EstablishmentDateFilterType) => {
    setDraftDateFilterType(value);
  }, []);

  const handleDateFromChange = useCallback((value: string) => {
    setDraftDateFrom(value);
  }, []);

  const handleDateToChange = useCallback((value: string) => {
    setDraftDateTo(value);
  }, []);

  const handleIndividualFilterChange = useCallback((value: EstablishmentIndividualFilter) => {
    setDraftIndividualFilter(value);
  }, []);

  const handleGoogleCheckStatusesChange = useCallback((value: string[]) => {
    setDraftGoogleCheckStatuses(value);
  }, []);

  const handleSelectedClientIdChange = useCallback(
    (value: string) => {
      setDraftSelectedClientId(value);

      if (!value) {
        setDraftNafCodes([]);
        setDraftDepartmentCodes([]);
        return;
      }

      const client = (clientsQuery.data ?? []).find((item) => item.id === value);
      if (!client) {
        return;
      }

      const nextNafCodes = Array.from(
        new Set(
          client.subscriptions
            .map((subscription) => subscription.subcategory.nafCode)
            .map((code) => (code || "").trim())
            .filter((code) => Boolean(code)),
        ),
      );

      const nextDepartmentCodes = Array.from(
        new Set(
          client.departments
            .map((department) => department.code)
            .map((code) => (code || "").trim())
            .filter((code) => Boolean(code)),
        ),
      );

      setDraftNafCodes(nextNafCodes);
      setDraftDepartmentCodes(nextDepartmentCodes);
    },
    [clientsQuery.data],
  );

  const handleLinkedinStatusesChange = useCallback((value: LinkedInStatus[]) => {
    setDraftLinkedinStatuses(value);
  }, []);

  const handleWebsiteScrapeStatusesChange = useCallback((value: WebsiteScrapeStatus[]) => {
    setDraftWebsiteScrapeStatuses(value);
  }, []);

  const handleApplyFilters = useCallback(() => {
    setQuery(draftQuery);
    setNafCodes(draftNafCodes);
    setDepartmentCodes(draftDepartmentCodes);
    setDateFilterType(draftDateFilterType);
    setDateFrom(draftDateFrom);
    setDateTo(draftDateTo);
    setIndividualFilter(draftIndividualFilter);
    setGoogleCheckStatuses(draftGoogleCheckStatuses);
    setSelectedClientId(draftSelectedClientId);
    setLinkedinStatuses(draftLinkedinStatuses);
    setWebsiteScrapeStatuses(draftWebsiteScrapeStatuses);
    setPage(0);
  }, [
    draftDateFilterType,
    draftDateFrom,
    draftDateTo,
    draftGoogleCheckStatuses,
    draftIndividualFilter,
    draftNafCodes,
    draftQuery,
    draftSelectedClientId,
    draftDepartmentCodes,
    draftLinkedinStatuses,
    draftWebsiteScrapeStatuses,
  ]);

  const handleResetFilters = useCallback(() => {
    setDraftQuery("");
    setDraftNafCodes([]);
    setDraftDepartmentCodes([]);
    setDraftDateFilterType("added");
    setDraftDateFrom("");
    setDraftDateTo("");
    setDraftIndividualFilter("all");
    setDraftGoogleCheckStatuses([]);
    setDraftSelectedClientId("");
    setDraftLinkedinStatuses([]);
    setDraftWebsiteScrapeStatuses([]);

    setQuery("");
    setNafCodes([]);
    setDepartmentCodes([]);
    setDateFilterType("added");
    setDateFrom("");
    setDateTo("");
    setIndividualFilter("all");
    setGoogleCheckStatuses([]);
    setSelectedClientId("");
    setLinkedinStatuses([]);
    setWebsiteScrapeStatuses([]);
    setPage(0);
  }, []);

  const hasPendingFilters = useMemo(() => {
    if (draftQuery !== query) {
      return true;
    }
    if (draftDateFilterType !== dateFilterType) {
      return true;
    }
    if (draftDateFrom !== dateFrom) {
      return true;
    }
    if (draftDateTo !== dateTo) {
      return true;
    }
    if (draftIndividualFilter !== individualFilter) {
      return true;
    }
    if (draftSelectedClientId !== selectedClientId) {
      return true;
    }
    if (draftGoogleCheckStatuses.length !== googleCheckStatuses.length) {
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
    if (draftWebsiteScrapeStatuses.length !== websiteScrapeStatuses.length) {
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
    const googleStatusA = [...draftGoogleCheckStatuses].sort().join(",");
    const googleStatusB = [...googleCheckStatuses].sort().join(",");
    if (googleStatusA !== googleStatusB) {
      return true;
    }
    const linkedinA = [...draftLinkedinStatuses].sort().join(",");
    const linkedinB = [...linkedinStatuses].sort().join(",");
    if (linkedinA !== linkedinB) {
      return true;
    }
    const websiteA = [...draftWebsiteScrapeStatuses].sort().join(",");
    const websiteB = [...websiteScrapeStatuses].sort().join(",");
    return websiteA !== websiteB;
  }, [
    dateFilterType,
    dateFrom,
    dateTo,
    draftDateFilterType,
    draftDateFrom,
    draftDateTo,
    draftGoogleCheckStatuses,
    draftIndividualFilter,
    draftNafCodes,
    draftQuery,
    draftSelectedClientId,
    googleCheckStatuses,
    individualFilter,
    nafCodes,
    query,
    draftDepartmentCodes,
    departmentCodes,
    selectedClientId,
    draftLinkedinStatuses,
    linkedinStatuses,
    draftWebsiteScrapeStatuses,
    websiteScrapeStatuses,
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
      clients={clientsQuery.data}
      isLoadingClients={clientsQuery.isLoading}
      regions={regionsQuery.data}
      isLoadingRegions={regionsQuery.isLoading}
      limit={limit}
      page={page}
      query={draftQuery}
      nafCodes={draftNafCodes}
      departmentCodes={draftDepartmentCodes}
      dateFilterType={draftDateFilterType}
      dateFrom={draftDateFrom}
      dateTo={draftDateTo}
      individualFilter={draftIndividualFilter}
      googleCheckStatuses={draftGoogleCheckStatuses}
      selectedClientId={draftSelectedClientId}
      linkedinStatuses={draftLinkedinStatuses}
      websiteScrapeStatuses={draftWebsiteScrapeStatuses}
      hasNextPage={hasNextPage}
      onLimitChange={handleLimitChange}
      onPageChange={handlePageChange}
      onQueryChange={handleQueryChange}
      onNafCodesChange={handleNafCodesChange}
      onDepartmentCodesChange={handleDepartmentCodesChange}
      onDateFilterTypeChange={handleDateFilterTypeChange}
      onDateFromChange={handleDateFromChange}
      onDateToChange={handleDateToChange}
      onApplyFilters={handleApplyFilters}
      hasPendingFilters={hasPendingFilters}
      onResetFilters={handleResetFilters}
      onIndividualFilterChange={handleIndividualFilterChange}
      onGoogleCheckStatusesChange={handleGoogleCheckStatusesChange}
      onSelectedClientIdChange={handleSelectedClientIdChange}
      onLinkedinStatusesChange={handleLinkedinStatusesChange}
      onWebsiteScrapeStatusesChange={handleWebsiteScrapeStatusesChange}
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

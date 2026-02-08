import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { ApiError, googleApi, nafApi, regionsApi, toolsApi } from "../../api";
import type {
  AnnuaireDebugResult,
  GoogleFindPlaceDebugResult,
  NafCategory,
  Region,
  SireneNewBusinessesResult,
} from "../../types";
import { openGoogleSearchForEstablishment } from "../../utils/googleSearch";
import { parseNafInput, sanitizeNafCodes } from "../../utils/sync";
import { AnnuaireDebugModal } from "../../components/AnnuaireDebugModal";
import { GoogleFindPlaceDebugModal } from "../../components/GoogleFindPlaceDebugModal";
import { ToolsView } from "../../components/views/ToolsView";

const DEFAULT_LIMIT = 100;

const buildDefaultStartDate = (): string => {
  const now = new Date();
  return now.toISOString().slice(0, 10);
};

type Props = {
  onUnauthorized: () => void;
};

export const ToolsSection = ({ onUnauthorized }: Props) => {
  const [startDate, setStartDate] = useState(buildDefaultStartDate);
  const [endDate, setEndDate] = useState("");
  const [nafCodesInput, setNafCodesInput] = useState("");
  const [selectedNafCodes, setSelectedNafCodes] = useState<string[]>([]);
  const [selectedDepartmentCodes, setSelectedDepartmentCodes] = useState<string[]>([]);
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [enrichAnnuaire, setEnrichAnnuaire] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<SireneNewBusinessesResult | null>(null);
  const [googleFindPlaceDebugModal, setGoogleFindPlaceDebugModal] = useState<
    { siret: string; result: GoogleFindPlaceDebugResult } | null
  >(null);
  const [annuaireDebugModal, setAnnuaireDebugModal] = useState<
    { siret: string; result: AnnuaireDebugResult } | null
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

  const mutation = useMutation({
    mutationFn: toolsApi.fetchSireneNewBusinesses,
    onSuccess: (data) => {
      setResult(data);
      setErrorMessage(null);
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
      setErrorMessage(message);
    },
  });

  const googleFindPlaceDebugMutation = useMutation<GoogleFindPlaceDebugResult, unknown, string>({
    mutationFn: (siret) => googleApi.debugFindPlace(siret),
    onSuccess: (debugResult, siret) => {
      setGoogleFindPlaceDebugModal({ siret, result: debugResult });
      setErrorMessage(null);
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
      setErrorMessage(message);
      toast.error(message, { id: message });
    },
  });

  const annuaireDebugMutation = useMutation<AnnuaireDebugResult, unknown, string>({
    mutationFn: (siret) => toolsApi.fetchAnnuaireDebug(siret),
    onSuccess: (debugResult, siret) => {
      setAnnuaireDebugModal({ siret, result: debugResult });
      setErrorMessage(null);
    },
    onError: (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) {
        onUnauthorized();
        return;
      }
      const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
      setErrorMessage(message);
      toast.error(message, { id: message });
    },
  });

  useEffect(() => {
    if (!nafCategoriesQuery.error) {
      return;
    }
    const error = nafCategoriesQuery.error;
    if (error instanceof ApiError && error.status === 403) {
      onUnauthorized();
      return;
    }
    const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
    setErrorMessage(message);
    toast.error(message, { id: message });
  }, [nafCategoriesQuery.error, onUnauthorized]);

  useEffect(() => {
    if (!regionsQuery.error) {
      return;
    }
    const error = regionsQuery.error;
    if (error instanceof ApiError && error.status === 403) {
      onUnauthorized();
      return;
    }
    const message = error instanceof ApiError ? error.message : "Une erreur est survenue.";
    setErrorMessage(message);
    toast.error(message, { id: message });
  }, [regionsQuery.error, onUnauthorized]);

  const handleSubmit = useCallback(() => {
    if (!startDate) {
      setErrorMessage("La date de début est requise.");
      return;
    }
    const parsedCodes = sanitizeNafCodes([
      ...selectedNafCodes,
      ...parseNafInput(nafCodesInput),
    ]);
    if (parsedCodes.length === 0) {
      setErrorMessage("Renseignez au moins un code NAF valide.");
      return;
    }
    setErrorMessage(null);
    mutation.mutate({
      startDate,
      endDate: endDate || undefined,
      nafCodes: parsedCodes,
      limit,
      departmentCodes: selectedDepartmentCodes.length > 0 ? selectedDepartmentCodes : undefined,
      enrichAnnuaire,
    });
  }, [startDate, selectedNafCodes, nafCodesInput, endDate, limit, mutation, selectedDepartmentCodes, enrichAnnuaire]);

  const handleReset = useCallback(() => {
    setStartDate(buildDefaultStartDate());
    setEndDate("");
    setNafCodesInput("");
    setSelectedNafCodes([]);
    setSelectedDepartmentCodes([]);
    setLimit(DEFAULT_LIMIT);
    setEnrichAnnuaire(false);
    setErrorMessage(null);
    setResult(null);
  }, []);

  const handleToggleNafCode = useCallback((code: string) => {
    setSelectedNafCodes((current) => {
      if (current.includes(code)) {
        return current.filter((item) => item !== code);
      }
      return [...current, code];
    });
  }, []);

  const handleDepartmentCodesChange = useCallback((codes: string[]) => {
    setSelectedDepartmentCodes(codes);
  }, []);

  const handleGoogleSearch = useCallback(
    (siret: string) => {
      const entry = result?.establishments.find((item) => item.siret === siret);
      if (!entry) {
        return;
      }
      const opened = openGoogleSearchForEstablishment({
        name: entry.name,
        libelleCommune: entry.libelleCommune,
        libelleCommuneEtranger: entry.libelleCommuneEtranger,
        codePostal: entry.codePostal,
      });
      if (!opened) {
        const message = "Impossible de construire la recherche Google pour cet établissement.";
        setErrorMessage(message);
        toast.error(message, { id: message });
      }
    },
    [result],
  );

  const handleDebugGoogleFindPlace = useCallback(
    (siret: string) => {
      googleFindPlaceDebugMutation.mutate(siret);
    },
    [googleFindPlaceDebugMutation],
  );

  const handleDebugAnnuaire = useCallback(
    (siret: string) => {
      annuaireDebugMutation.mutate(siret);
    },
    [annuaireDebugMutation],
  );

  return (
    <>
      <ToolsView
        startDate={startDate}
        endDate={endDate}
        nafCodesInput={nafCodesInput}
        selectedNafCodes={selectedNafCodes}
        limit={limit}
        isLoading={mutation.isPending}
        nafCategories={nafCategoriesQuery.data}
        isLoadingNafCategories={nafCategoriesQuery.isLoading}
        regions={regionsQuery.data}
        isLoadingRegions={regionsQuery.isLoading}
        selectedDepartmentCodes={selectedDepartmentCodes}
        errorMessage={errorMessage}
        result={result}
        onStartDateChange={setStartDate}
        onEndDateChange={setEndDate}
        onNafCodesInputChange={setNafCodesInput}
        onToggleNafCode={handleToggleNafCode}
        onDepartmentCodesChange={handleDepartmentCodesChange}
        onLimitChange={setLimit}
        enrichAnnuaire={enrichAnnuaire}
        onEnrichAnnuaireChange={setEnrichAnnuaire}
        onSubmit={handleSubmit}
        onReset={handleReset}
        onGoogleSearch={handleGoogleSearch}
        onDebugGoogleFindPlace={handleDebugGoogleFindPlace}
        debuggingGoogleFindPlaceSiret={
          googleFindPlaceDebugMutation.isPending
            ? ((googleFindPlaceDebugMutation.variables as string | undefined) ?? null)
            : null
        }
        onDebugAnnuaire={handleDebugAnnuaire}
        debuggingAnnuaireSiret={
          annuaireDebugMutation.isPending
            ? ((annuaireDebugMutation.variables as string | undefined) ?? null)
            : null
        }
      />

      {annuaireDebugModal ? (
        <AnnuaireDebugModal
          siret={annuaireDebugModal.siret}
          result={annuaireDebugModal.result}
          onClose={() => setAnnuaireDebugModal(null)}
        />
      ) : null}

      {googleFindPlaceDebugModal ? (
        <GoogleFindPlaceDebugModal
          siret={googleFindPlaceDebugModal.siret}
          result={googleFindPlaceDebugModal.result}
          onClose={() => setGoogleFindPlaceDebugModal(null)}
        />
      ) : null}
    </>
  );
};

import { EstablishmentsSection } from "../EstablishmentsSection";
import type {
  Establishment,
  EstablishmentIndividualFilter,
  GoogleFindPlaceDebugResult,
  LinkedInStatus,
  NafCategory,
  Region,
} from "../../types";

type Props = {
  establishments: Establishment[] | undefined;
  resultCount: number | undefined;
  isResultCountLoading: boolean;
  isLoading: boolean;
  error: Error | null;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  regions: Region[] | undefined;
  isLoadingRegions: boolean;
  limit: number;
  page: number;
  query: string;
  nafCodes: string[];
  departmentCodes: string[];
  addedFrom: string;
  addedTo: string;
  lastTreatmentFrom: string;
  lastTreatmentTo: string;
  individualFilter: EstablishmentIndividualFilter;
  googleCheckStatus: string;
  linkedinStatuses: LinkedInStatus[];
  hasNextPage: boolean;
  onLimitChange: (limit: number) => void;
  onPageChange: (page: number) => void;
  onQueryChange: (query: string) => void;
  onNafCodesChange: (value: string[]) => void;
  onDepartmentCodesChange: (value: string[]) => void;
  onAddedFromChange: (value: string) => void;
  onAddedToChange: (value: string) => void;
  onLastTreatmentFromChange: (value: string) => void;
  onLastTreatmentToChange: (value: string) => void;
  onApplyFilters: () => void;
  hasPendingFilters: boolean;
  onResetFilters: () => void;
  onIndividualFilterChange: (value: EstablishmentIndividualFilter) => void;
  onGoogleCheckStatusChange: (value: string) => void;
  onLinkedinStatusesChange: (value: LinkedInStatus[]) => void;
  onRefresh: () => void;
  onDeleteEstablishment: (siret: string) => void;
  deletingSiret: string | null;
  isDeletingOne: boolean;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onTriggerGoogleCheck: (siret: string) => void;
  isCheckingGoogle: boolean;
  checkingGoogleSiret: string | null;
  onTriggerGoogleFindPlaceDebug: (siret: string) => void;
  isDebuggingGoogleFindPlace: boolean;
  debuggingGoogleFindPlaceSiret: string | null;
  googleFindPlaceDebugModal: { siret: string; result: GoogleFindPlaceDebugResult } | null;
  onCloseGoogleFindPlaceDebugModal: () => void;
  onSelectEstablishment: (siret: string) => void;
};

export const EstablishmentsView = ({
  establishments,
  resultCount,
  isResultCountLoading,
  isLoading,
  error,
  nafCategories,
  isLoadingNafCategories,
  regions,
  isLoadingRegions,
  limit,
  page,
  query,
  nafCodes,
  departmentCodes,
  addedFrom,
  addedTo,
  lastTreatmentFrom,
  lastTreatmentTo,
  individualFilter,
  googleCheckStatus,
  linkedinStatuses,
  hasNextPage,
  onLimitChange,
  onPageChange,
  onQueryChange,
  onNafCodesChange,
  onDepartmentCodesChange,
  onAddedFromChange,
  onAddedToChange,
  onLastTreatmentFromChange,
  onLastTreatmentToChange,
  onApplyFilters,
  hasPendingFilters,
  onResetFilters,
  onIndividualFilterChange,
  onGoogleCheckStatusChange,
  onLinkedinStatusesChange,
  onRefresh,
  onDeleteEstablishment,
  deletingSiret,
  isDeletingOne,
  feedbackMessage,
  errorMessage,
  onTriggerGoogleCheck,
  isCheckingGoogle,
  checkingGoogleSiret,
  onTriggerGoogleFindPlaceDebug,
  isDebuggingGoogleFindPlace,
  debuggingGoogleFindPlaceSiret,
  googleFindPlaceDebugModal,
  onCloseGoogleFindPlaceDebugModal,
  onSelectEstablishment,
}: Props) => {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <div>
          <h2>Etablissements</h2>
          <p className="muted">Recherche et suppression sécurisée des établissements.</p>
        </div>
      </div>
      <div className="section-grid">
        <EstablishmentsSection
          establishments={establishments}
          resultCount={resultCount}
          isResultCountLoading={isResultCountLoading}
          isLoading={isLoading}
          error={error}
          nafCategories={nafCategories}
          isLoadingNafCategories={isLoadingNafCategories}
          regions={regions}
          isLoadingRegions={isLoadingRegions}
          limit={limit}
          page={page}
          query={query}
          nafCodes={nafCodes}
          departmentCodes={departmentCodes}
          addedFrom={addedFrom}
          addedTo={addedTo}
          lastTreatmentFrom={lastTreatmentFrom}
          lastTreatmentTo={lastTreatmentTo}
          individualFilter={individualFilter}
          googleCheckStatus={googleCheckStatus}
          linkedinStatuses={linkedinStatuses}
          hasNextPage={hasNextPage}
          onLimitChange={onLimitChange}
          onPageChange={onPageChange}
          onQueryChange={onQueryChange}
          onNafCodesChange={onNafCodesChange}
          onDepartmentCodesChange={onDepartmentCodesChange}
          onAddedFromChange={onAddedFromChange}
          onAddedToChange={onAddedToChange}
          onLastTreatmentFromChange={onLastTreatmentFromChange}
          onLastTreatmentToChange={onLastTreatmentToChange}
          onApplyFilters={onApplyFilters}
          hasPendingFilters={hasPendingFilters}
          onResetFilters={onResetFilters}
          onIndividualFilterChange={onIndividualFilterChange}
          onGoogleCheckStatusChange={onGoogleCheckStatusChange}
          onLinkedinStatusesChange={onLinkedinStatusesChange}
          onRefresh={onRefresh}
          onDeleteEstablishment={onDeleteEstablishment}
          deletingSiret={deletingSiret}
          isDeletingOne={isDeletingOne}
          feedbackMessage={feedbackMessage}
          errorMessage={errorMessage}
          onTriggerGoogleCheck={onTriggerGoogleCheck}
          isCheckingGoogle={isCheckingGoogle}
          checkingGoogleSiret={checkingGoogleSiret}
          onTriggerGoogleFindPlaceDebug={onTriggerGoogleFindPlaceDebug}
          isDebuggingGoogleFindPlace={isDebuggingGoogleFindPlace}
          debuggingGoogleFindPlaceSiret={debuggingGoogleFindPlaceSiret}
          googleFindPlaceDebugModal={googleFindPlaceDebugModal}
          onCloseGoogleFindPlaceDebugModal={onCloseGoogleFindPlaceDebugModal}
          onSelectEstablishment={onSelectEstablishment}
        />
      </div>
    </section>
  );
};

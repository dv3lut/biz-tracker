import { EstablishmentsSection } from "../EstablishmentsSection";
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

type Props = {
  establishments: Establishment[] | undefined;
  resultCount: number | undefined;
  isResultCountLoading: boolean;
  isLoading: boolean;
  error: Error | null;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  clients: Client[] | undefined;
  isLoadingClients: boolean;
  regions: Region[] | undefined;
  isLoadingRegions: boolean;
  limit: number;
  page: number;
  query: string;
  nafCodes: string[];
  departmentCodes: string[];
  dateFilterType: EstablishmentDateFilterType;
  dateFrom: string;
  dateTo: string;
  individualFilter: EstablishmentIndividualFilter;
  googleCheckStatuses: string[];
  selectedClientId: string;
  linkedinStatuses: LinkedInStatus[];
  websiteScrapeStatuses: WebsiteScrapeStatus[];
  hasNextPage: boolean;
  onLimitChange: (limit: number) => void;
  onPageChange: (page: number) => void;
  onQueryChange: (query: string) => void;
  onNafCodesChange: (value: string[]) => void;
  onDepartmentCodesChange: (value: string[]) => void;
  onDateFilterTypeChange: (value: EstablishmentDateFilterType) => void;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  onApplyFilters: () => void;
  hasPendingFilters: boolean;
  onResetFilters: () => void;
  onIndividualFilterChange: (value: EstablishmentIndividualFilter) => void;
  onGoogleCheckStatusesChange: (value: string[]) => void;
  onSelectedClientIdChange: (value: string) => void;
  onLinkedinStatusesChange: (value: LinkedInStatus[]) => void;
  onWebsiteScrapeStatusesChange: (value: WebsiteScrapeStatus[]) => void;
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
  clients,
  isLoadingClients,
  regions,
  isLoadingRegions,
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
  hasNextPage,
  onLimitChange,
  onPageChange,
  onQueryChange,
  onNafCodesChange,
  onDepartmentCodesChange,
  onDateFilterTypeChange,
  onDateFromChange,
  onDateToChange,
  onApplyFilters,
  hasPendingFilters,
  onResetFilters,
  onIndividualFilterChange,
  onGoogleCheckStatusesChange,
  onSelectedClientIdChange,
  onLinkedinStatusesChange,
  onWebsiteScrapeStatusesChange,
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
          clients={clients}
          isLoadingClients={isLoadingClients}
          regions={regions}
          isLoadingRegions={isLoadingRegions}
          limit={limit}
          page={page}
          query={query}
          nafCodes={nafCodes}
          departmentCodes={departmentCodes}
          dateFilterType={dateFilterType}
          dateFrom={dateFrom}
          dateTo={dateTo}
          individualFilter={individualFilter}
          googleCheckStatuses={googleCheckStatuses}
          selectedClientId={selectedClientId}
          linkedinStatuses={linkedinStatuses}
          websiteScrapeStatuses={websiteScrapeStatuses}
          hasNextPage={hasNextPage}
          onLimitChange={onLimitChange}
          onPageChange={onPageChange}
          onQueryChange={onQueryChange}
          onNafCodesChange={onNafCodesChange}
          onDepartmentCodesChange={onDepartmentCodesChange}
          onDateFilterTypeChange={onDateFilterTypeChange}
          onDateFromChange={onDateFromChange}
          onDateToChange={onDateToChange}
          onApplyFilters={onApplyFilters}
          hasPendingFilters={hasPendingFilters}
          onResetFilters={onResetFilters}
          onIndividualFilterChange={onIndividualFilterChange}
          onGoogleCheckStatusesChange={onGoogleCheckStatusesChange}
          onSelectedClientIdChange={onSelectedClientIdChange}
          onLinkedinStatusesChange={onLinkedinStatusesChange}
          onWebsiteScrapeStatusesChange={onWebsiteScrapeStatusesChange}
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

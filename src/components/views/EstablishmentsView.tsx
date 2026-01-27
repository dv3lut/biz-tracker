import { EstablishmentsSection } from "../EstablishmentsSection";
import type {
  Establishment,
  EstablishmentIndividualFilter,
  GoogleFindPlaceDebugResult,
  NafCategory,
} from "../../types";

type Props = {
  establishments: Establishment[] | undefined;
  isLoading: boolean;
  error: Error | null;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  limit: number;
  page: number;
  query: string;
  nafCodes: string[];
  addedFrom: string;
  addedTo: string;
  individualFilter: EstablishmentIndividualFilter;
  googleCheckStatus: string;
  hasNextPage: boolean;
  onLimitChange: (limit: number) => void;
  onPageChange: (page: number) => void;
  onQueryChange: (query: string) => void;
  onNafCodesChange: (value: string[]) => void;
  onAddedFromChange: (value: string) => void;
  onAddedToChange: (value: string) => void;
  onApplyFilters: () => void;
  hasPendingFilters: boolean;
  onResetFilters: () => void;
  onIndividualFilterChange: (value: EstablishmentIndividualFilter) => void;
  onGoogleCheckStatusChange: (value: string) => void;
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
  isLoading,
  error,
  nafCategories,
  isLoadingNafCategories,
  limit,
  page,
  query,
  nafCodes,
  addedFrom,
  addedTo,
  individualFilter,
  googleCheckStatus,
  hasNextPage,
  onLimitChange,
  onPageChange,
  onQueryChange,
  onNafCodesChange,
  onAddedFromChange,
  onAddedToChange,
  onApplyFilters,
  hasPendingFilters,
  onResetFilters,
  onIndividualFilterChange,
  onGoogleCheckStatusChange,
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
          isLoading={isLoading}
          error={error}
          nafCategories={nafCategories}
          isLoadingNafCategories={isLoadingNafCategories}
          limit={limit}
          page={page}
          query={query}
          nafCodes={nafCodes}
          addedFrom={addedFrom}
          addedTo={addedTo}
          individualFilter={individualFilter}
          googleCheckStatus={googleCheckStatus}
          hasNextPage={hasNextPage}
          onLimitChange={onLimitChange}
          onPageChange={onPageChange}
          onQueryChange={onQueryChange}
          onNafCodesChange={onNafCodesChange}
          onAddedFromChange={onAddedFromChange}
          onAddedToChange={onAddedToChange}
          onApplyFilters={onApplyFilters}
          hasPendingFilters={hasPendingFilters}
          onResetFilters={onResetFilters}
          onIndividualFilterChange={onIndividualFilterChange}
          onGoogleCheckStatusChange={onGoogleCheckStatusChange}
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

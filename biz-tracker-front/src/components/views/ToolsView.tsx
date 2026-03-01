import type { NafCategory, Region, SireneNewBusinessesResult } from "../../types";
import { SireneNewBusinessesPanel } from "../SireneNewBusinessesPanel";

type Props = {
  startDate: string;
  endDate: string;
  lastTreatmentFrom: string;
  lastTreatmentTo: string;
  nafCodesInput: string;
  selectedNafCodes: string[];
  limit: number;
  isLoading: boolean;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  regions: Region[] | undefined;
  isLoadingRegions: boolean;
  selectedDepartmentCodes: string[];
  errorMessage: string | null;
  result: SireneNewBusinessesResult | null;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onLastTreatmentFromChange: (value: string) => void;
  onLastTreatmentToChange: (value: string) => void;
  onNafCodesInputChange: (value: string) => void;
  onToggleNafCode: (value: string) => void;
  onDepartmentCodesChange: (value: string[]) => void;
  onLimitChange: (value: number) => void;
  enrichAnnuaire: boolean;
  onEnrichAnnuaireChange: (value: boolean) => void;
  onSubmit: () => void;
  onReset: () => void;
  onGoogleSearch: (siret: string) => void;
  onDebugGoogleFindPlace: (siret: string) => void;
  debuggingGoogleFindPlaceSiret: string | null;
  onDebugAnnuaire: (siret: string) => void;
  debuggingAnnuaireSiret: string | null;
};

export const ToolsView = ({
  startDate,
  endDate,
  lastTreatmentFrom,
  lastTreatmentTo,
  nafCodesInput,
  selectedNafCodes,
  limit,
  isLoading,
  nafCategories,
  isLoadingNafCategories,
  regions,
  isLoadingRegions,
  selectedDepartmentCodes,
  errorMessage,
  result,
  onStartDateChange,
  onEndDateChange,
  onLastTreatmentFromChange,
  onLastTreatmentToChange,
  onNafCodesInputChange,
  onToggleNafCode,
  onDepartmentCodesChange,
  onLimitChange,
  enrichAnnuaire,
  onEnrichAnnuaireChange,
  onSubmit,
  onReset,
  onGoogleSearch,
  onDebugGoogleFindPlace,
  debuggingGoogleFindPlaceSiret,
  onDebugAnnuaire,
  debuggingAnnuaireSiret,
}: Props) => {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <div>
          <h2>Outils</h2>
          <p className="muted">Utilitaires de développement pour inspecter Sirene.</p>
        </div>
      </div>
      <div className="section-grid">
        <SireneNewBusinessesPanel
          startDate={startDate}
          endDate={endDate}
          lastTreatmentFrom={lastTreatmentFrom}
          lastTreatmentTo={lastTreatmentTo}
          nafCodesInput={nafCodesInput}
          selectedNafCodes={selectedNafCodes}
          limit={limit}
          isLoading={isLoading}
          nafCategories={nafCategories}
          isLoadingNafCategories={isLoadingNafCategories}
          regions={regions}
          isLoadingRegions={isLoadingRegions}
          selectedDepartmentCodes={selectedDepartmentCodes}
          errorMessage={errorMessage}
          result={result}
          onStartDateChange={onStartDateChange}
          onEndDateChange={onEndDateChange}
          onLastTreatmentFromChange={onLastTreatmentFromChange}
          onLastTreatmentToChange={onLastTreatmentToChange}
          onNafCodesInputChange={onNafCodesInputChange}
          onToggleNafCode={onToggleNafCode}
          onDepartmentCodesChange={onDepartmentCodesChange}
          onLimitChange={onLimitChange}
          enrichAnnuaire={enrichAnnuaire}
          onEnrichAnnuaireChange={onEnrichAnnuaireChange}
          onSubmit={onSubmit}
          onReset={onReset}
          onGoogleSearch={onGoogleSearch}
          onDebugGoogleFindPlace={onDebugGoogleFindPlace}
          debuggingGoogleFindPlaceSiret={debuggingGoogleFindPlaceSiret}
          onDebugAnnuaire={onDebugAnnuaire}
          debuggingAnnuaireSiret={debuggingAnnuaireSiret}
        />
      </div>
    </section>
  );
};

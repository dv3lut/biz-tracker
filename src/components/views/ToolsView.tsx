import type { NafCategory, SireneNewBusinessesResult } from "../../types";
import { SireneNewBusinessesPanel } from "../SireneNewBusinessesPanel";

type Props = {
  startDate: string;
  endDate: string;
  nafCodesInput: string;
  selectedNafCodes: string[];
  limit: number;
  isLoading: boolean;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  errorMessage: string | null;
  result: SireneNewBusinessesResult | null;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onNafCodesInputChange: (value: string) => void;
  onToggleNafCode: (value: string) => void;
  onLimitChange: (value: number) => void;
  onSubmit: () => void;
  onReset: () => void;
  onGoogleSearch: (siret: string) => void;
  onDebugGoogleFindPlace: (siret: string) => void;
  debuggingGoogleFindPlaceSiret: string | null;
};

export const ToolsView = ({
  startDate,
  endDate,
  nafCodesInput,
  selectedNafCodes,
  limit,
  isLoading,
  nafCategories,
  isLoadingNafCategories,
  errorMessage,
  result,
  onStartDateChange,
  onEndDateChange,
  onNafCodesInputChange,
  onToggleNafCode,
  onLimitChange,
  onSubmit,
  onReset,
  onGoogleSearch,
  onDebugGoogleFindPlace,
  debuggingGoogleFindPlaceSiret,
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
          nafCodesInput={nafCodesInput}
          selectedNafCodes={selectedNafCodes}
          limit={limit}
          isLoading={isLoading}
          nafCategories={nafCategories}
          isLoadingNafCategories={isLoadingNafCategories}
          errorMessage={errorMessage}
          result={result}
          onStartDateChange={onStartDateChange}
          onEndDateChange={onEndDateChange}
          onNafCodesInputChange={onNafCodesInputChange}
          onToggleNafCode={onToggleNafCode}
          onLimitChange={onLimitChange}
          onSubmit={onSubmit}
          onReset={onReset}
          onGoogleSearch={onGoogleSearch}
          onDebugGoogleFindPlace={onDebugGoogleFindPlace}
          debuggingGoogleFindPlaceSiret={debuggingGoogleFindPlaceSiret}
        />
      </div>
    </section>
  );
};

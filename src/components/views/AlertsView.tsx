import { AlertsList } from "../AlertsList";
import type { Alert } from "../../types";

type Props = {
  alerts: Alert[] | undefined;
  isLoading: boolean;
  error: Error | null;
  limit: number;
  onLimitChange: (limit: number) => void;
  onRefresh: () => void;
  exportDays: number;
  onExportDaysChange: (days: number) => void;
  onExportAlerts: () => void;
  isExportingAlerts: boolean;
  onTriggerGoogleCheck: (siret: string) => void;
  isCheckingGoogle: boolean;
  checkingGoogleSiret: string | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onSelectAlert: (siret: string) => void;
};

export const AlertsView = ({
  alerts,
  isLoading,
  error,
  limit,
  onLimitChange,
  onRefresh,
  exportDays,
  onExportDaysChange,
  onExportAlerts,
  isExportingAlerts,
  onTriggerGoogleCheck,
  isCheckingGoogle,
  checkingGoogleSiret,
  feedbackMessage,
  errorMessage,
  onSelectAlert,
}: Props) => {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <div>
          <h2>Alertes</h2>
          <p className="muted">Dernières notifications envoyées aux équipes.</p>
        </div>
      </div>
      <div className="section-grid">
        <AlertsList
          alerts={alerts}
          isLoading={isLoading}
          error={error}
          limit={limit}
          onLimitChange={onLimitChange}
          onRefresh={onRefresh}
          exportDays={exportDays}
          onExportDaysChange={onExportDaysChange}
          onExport={onExportAlerts}
          isExporting={isExportingAlerts}
          onTriggerGoogleCheck={onTriggerGoogleCheck}
          isCheckingGoogle={isCheckingGoogle}
          checkingGoogleSiret={checkingGoogleSiret}
          feedbackMessage={feedbackMessage}
          errorMessage={errorMessage}
          onSelect={onSelectAlert}
        />
      </div>
    </section>
  );
};

import { StripeSettingsCard } from "../StripeSettingsCard";
import type { AdminStripeSettings, AdminStripeSettingsUpdatePayload } from "../../types";

type Props = {
  settings: AdminStripeSettings | undefined;
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onRefresh: () => void;
  onSubmit: (payload: AdminStripeSettingsUpdatePayload) => void;
  isSubmitting: boolean;
};

export const StripeSettingsView = ({
  settings,
  isLoading,
  isRefreshing,
  error,
  feedbackMessage,
  errorMessage,
  onRefresh,
  onSubmit,
  isSubmitting,
}: Props) => {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <div>
          <h2>Facturation</h2>
          <p className="muted">Configuration de l'essai gratuit Stripe.</p>
        </div>
      </div>
      <div className="section-grid">
        <StripeSettingsCard
          settings={settings}
          isLoading={isLoading}
          isRefreshing={isRefreshing}
          error={error}
          feedbackMessage={feedbackMessage}
          errorMessage={errorMessage}
          onRefresh={onRefresh}
          onSubmit={onSubmit}
          isSubmitting={isSubmitting}
        />
      </div>
    </section>
  );
};

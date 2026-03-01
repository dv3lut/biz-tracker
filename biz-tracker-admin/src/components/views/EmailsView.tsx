import { AdminEmailConfigSection } from "../AdminEmailConfigSection";
import { EmailTestPanel } from "../EmailTestPanel";
import type { AdminEmailConfig, EmailTestPayload } from "../../types";
import type { AdminEmailConfigPayload } from "../../api/adminConfig";

type Props = {
  adminConfig: AdminEmailConfig | undefined;
  isAdminConfigLoading: boolean;
  isAdminConfigRefreshing: boolean;
  adminConfigError: Error | null;
  adminConfigFeedback: string | null;
  adminConfigMessageError: string | null;
  onRefreshAdminConfig: () => void;
  onSubmitAdminConfig: (payload: AdminEmailConfigPayload) => void;
  isSubmittingAdminConfig: boolean;
  onSendTestEmail: (payload: EmailTestPayload) => void;
  isSendingTestEmail: boolean;
  emailFeedbackMessage: string | null;
  emailErrorMessage: string | null;
  onResetEmailMessages: () => void;
};

export const EmailsView = ({
  adminConfig,
  isAdminConfigLoading,
  isAdminConfigRefreshing,
  adminConfigError,
  adminConfigFeedback,
  adminConfigMessageError,
  onRefreshAdminConfig,
  onSubmitAdminConfig,
  isSubmittingAdminConfig,
  onSendTestEmail,
  isSendingTestEmail,
  emailFeedbackMessage,
  emailErrorMessage,
  onResetEmailMessages,
}: Props) => {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <div>
          <h2>E-mails</h2>
          <p className="muted">Configuration administrative et tests d'envoi.</p>
        </div>
      </div>
      <div className="section-grid two-column">
        <AdminEmailConfigSection
          config={adminConfig}
          isLoading={isAdminConfigLoading}
          isRefreshing={isAdminConfigRefreshing}
          error={adminConfigError}
          feedbackMessage={adminConfigFeedback}
          errorMessage={adminConfigMessageError}
          onRefresh={onRefreshAdminConfig}
          onSubmit={onSubmitAdminConfig}
          isSubmitting={isSubmittingAdminConfig}
        />
        <EmailTestPanel
          onSend={onSendTestEmail}
          isSending={isSendingTestEmail}
          feedbackMessage={emailFeedbackMessage}
          errorMessage={emailErrorMessage}
          onResetMessages={onResetEmailMessages}
        />
      </div>
    </section>
  );
};

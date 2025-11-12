import type { Client } from "../../types";
import { ClientsSection } from "../ClientsSection";

type Props = {
  clients: Client[] | undefined;
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onRefresh: () => void;
  onCreateClient: () => void;
  onEditClient: (client: Client) => void;
  onDeleteClient: (client: Client) => void;
  deletingClientId: string | null;
};

export const ClientsView = ({
  clients,
  isLoading,
  isRefreshing,
  error,
  feedbackMessage,
  errorMessage,
  onRefresh,
  onCreateClient,
  onEditClient,
  onDeleteClient,
  deletingClientId,
}: Props) => {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <div>
          <h2>Clients</h2>
          <p className="muted">Gestion des fenêtres d'activation et destinataires.</p>
        </div>
      </div>
      <div className="section-grid">
        <ClientsSection
          clients={clients}
          isLoading={isLoading}
          isRefreshing={isRefreshing}
          error={error}
          feedbackMessage={feedbackMessage}
          errorMessage={errorMessage}
          onRefresh={onRefresh}
          onCreate={onCreateClient}
          onEdit={onEditClient}
          onDelete={onDeleteClient}
          deletingClientId={deletingClientId}
        />
      </div>
    </section>
  );
};

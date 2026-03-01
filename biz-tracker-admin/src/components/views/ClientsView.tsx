import type { Client, NafCategory, Region } from "../../types";
import { ClientsSection } from "../ClientsSection";

type Props = {
  clients: Client[] | undefined;
  nafCategories?: NafCategory[];
  regions?: Region[];
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
  nafCategories,
  regions,
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
          nafCategories={nafCategories}
          regions={regions}
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

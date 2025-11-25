import { Client } from "../types";
import { formatDate, formatDateTime, formatNumber } from "../utils/format";
import { LISTING_STATUS_LABELS } from "../constants/listingStatuses";

type Props = {
  clients?: Client[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onRefresh: () => void;
  onCreate: () => void;
  onEdit: (client: Client) => void;
  onDelete: (client: Client) => void;
  deletingClientId: string | null;
};

const isClientActive = (client: Client): boolean => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(client.startDate);
  start.setHours(0, 0, 0, 0);
  if (Number.isNaN(start.getTime()) || start > today) {
    return false;
  }
  if (!client.endDate) {
    return true;
  }
  const end = new Date(client.endDate);
  end.setHours(0, 0, 0, 0);
  return !Number.isNaN(end.getTime()) && end >= today;
};

export const ClientsSection = ({
  clients,
  isLoading,
  isRefreshing,
  error,
  feedbackMessage,
  errorMessage,
  onRefresh,
  onCreate,
  onEdit,
  onDelete,
  deletingClientId,
}: Props) => {
  const handleDelete = (client: Client) => {
    const confirmed = window.confirm(
      `Supprimer le client "${client.name}" et toutes ses adresses e-mail associées ?`
    );
    if (confirmed) {
      onDelete(client);
    }
  };

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Clients</h2>
          <p className="muted">
            Configurez les fenêtres d'activation et les destinataires associés à chaque client.
          </p>
        </div>
        <div className="card-actions">
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Rafraîchir
          </button>
          <button type="button" className="primary" onClick={onCreate}>
            Nouveau client
          </button>
        </div>
      </header>

      {feedbackMessage ? <p className="feedback success">{feedbackMessage}</p> : null}
      {errorMessage ? <p className="feedback error">{errorMessage}</p> : null}

      {isLoading && <p>Chargement des clients…</p>}
      {isRefreshing && !isLoading && <p className="refresh-indicator">Actualisation en cours…</p>}
      {error && <p className="error">{error.message}</p>}

      {!isLoading && !error && clients && clients.length === 0 && (
        <p className="muted">Aucun client configuré pour le moment.</p>
      )}

      {!isLoading && !error && clients && clients.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Client</th>
                <th>Période d'activation</th>
                <th>Destinataires</th>
                <th>Abonnements NAF</th>
                <th>Statuts Google</th>
                <th>Statistiques</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client) => {
                const active = isClientActive(client);
                return (
                  <tr key={client.id}>
                    <td>
                      <strong>{client.name}</strong>
                      <br />
                      <span className={`badge status-${active ? "success" : "error"}`}>
                        {active ? "Actif" : "Inactif"}
                      </span>
                      <br />
                      <span className="small muted">
                        Créé le {formatDate(client.createdAt)} — Mis à jour le {formatDate(client.updatedAt)}
                      </span>
                    </td>
                    <td>
                      <span className="small muted">Début: {formatDate(client.startDate)}</span>
                      <br />
                      <span className="small muted">
                        Fin: {client.endDate ? formatDate(client.endDate) : "Aucune"}
                      </span>
                    </td>
                    <td>
                      {client.recipients.length === 0 ? (
                        <span className="small muted">Aucun destinataire</span>
                      ) : (
                        <div className="chip-list">
                          {client.recipients.map((recipient) => (
                            <span key={recipient.id} className="chip">
                              {recipient.email}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      {client.subscriptions.length === 0 ? (
                        <span className="small muted">Aucun code NAF sélectionné</span>
                      ) : (
                        <div className="chip-list">
                          {client.subscriptions.map((subscription) => (
                            <span key={subscription.subcategoryId} className="chip">
                              {subscription.subcategory.nafCode} · {subscription.subcategory.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      {client.listingStatuses.length === 0 ? (
                        <span className="small muted">Tous les statuts</span>
                      ) : (
                        <div className="chip-list">
                          {client.listingStatuses.map((status) => (
                            <span key={status} className="chip">
                              {LISTING_STATUS_LABELS[status] ?? status}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className="small muted">
                        E-mails envoyés: {formatNumber(client.emailsSentCount)}
                      </span>
                      <br />
                      <span className="small muted">
                        Dernier envoi: {formatDateTime(client.lastEmailSentAt)}
                      </span>
                    </td>
                    <td>
                      <div className="card-actions">
                        <button type="button" className="ghost" onClick={() => onEdit(client)}>
                          Modifier
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={() => handleDelete(client)}
                          disabled={deletingClientId === client.id}
                        >
                          {deletingClientId === client.id ? "Suppression…" : "Supprimer"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

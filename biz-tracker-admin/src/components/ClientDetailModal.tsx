import { useEffect, useMemo } from "react";

import { Client, ClientSubscriptionEvent, NafCategory, Region } from "../types";
import { formatDate, formatDateTime, formatNumber } from "../utils/format";
import { LISTING_STATUS_LABELS } from "../constants/listingStatuses";

type Props = {
  isOpen: boolean;
  client: Client | null;
  nafCategories?: NafCategory[];
  regions?: Region[];
  onClose: () => void;
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  upgrade: "Upgrade",
  downgrade_requested: "Downgrade programmé",
  downgrade_applied: "Downgrade appliqué",
  categories_updated: "Mise à jour des catégories",
};

const formatEventType = (eventType: string): string => {
  return EVENT_TYPE_LABELS[eventType] ?? eventType;
};

const formatPlan = (value: string | null): string => {
  if (!value) {
    return "—";
  }
  return value;
};

const formatCategories = (
  categories: string[] | null,
  categoryNames: Map<string, string>,
) => {
  if (!categories || categories.length === 0) {
    return <span className="small muted">—</span>;
  }
  return (
    <div className="chip-list chip-list--plain">
      {categories.map((categoryId) => (
        <span key={categoryId} className="chip">
          {categoryNames.get(categoryId) ?? categoryId}
        </span>
      ))}
    </div>
  );
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

const renderSubscriptionEvents = (
  events: ClientSubscriptionEvent[],
  categoryNames: Map<string, string>,
) => {
  if (events.length === 0) {
    return <p className="muted">Aucun changement de souscription enregistré.</p>;
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Plan</th>
            <th>Catégories</th>
            <th>Prend effet</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td>{formatDateTime(event.createdAt)}</td>
              <td>{formatEventType(event.eventType)}</td>
              <td>
                {formatPlan(event.fromPlanKey)} → {formatPlan(event.toPlanKey)}
              </td>
              <td>
                <div className="small muted">Avant</div>
                {formatCategories(event.fromCategoryIds, categoryNames)}
                <div className="small muted">Après</div>
                {formatCategories(event.toCategoryIds, categoryNames)}
              </td>
              <td>{formatDate(event.effectiveAt)}</td>
              <td>{event.source ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const ClientDetailModal = ({ isOpen, client, nafCategories, regions, onClose }: Props) => {
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
    };
  }, [isOpen, onClose]);

  const active = useMemo(() => (client ? isClientActive(client) : false), [client]);
  const categoryNames = useMemo(() => {
    const map = new Map<string, string>();
    (nafCategories ?? []).forEach((category) => {
      map.set(category.id, category.name);
    });
    return map;
  }, [nafCategories]);

  const departmentGroups = useMemo(() => {
    if (!client) {
      return [];
    }
    const regionNameById = new Map((regions ?? []).map((region) => [region.id, region.name]));
    const grouped = new Map<string, string[]>();
    client.departments.forEach((department) => {
      const regionName = regionNameById.get(department.regionId) ?? "Région";
      const list = grouped.get(regionName) ?? [];
      list.push(`${department.code} · ${department.name}`);
      grouped.set(regionName, list);
    });
    return Array.from(grouped.entries()).map(([name, entries]) => ({
      name,
      entries,
    }));
  }, [client, regions]);

  if (!isOpen || !client) {
    return null;
  }

  const currentStripe = client.stripeSubscriptions[0] ?? null;
  const listingStatuses = client.listingStatuses.length
    ? client.listingStatuses.map((status) => LISTING_STATUS_LABELS[status] ?? status)
    : ["Tous les statuts"];

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <div>
            <h2>Détails client</h2>
            <p className="muted small">{client.name}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Fermer
          </button>
        </header>

        <div className="modal-content">
          <section>
            <h3>Résumé</h3>
            <dl className="data-grid">
              <dt>Statut</dt>
              <dd>
                <span className={`badge status-${active ? "success" : "error"}`}>
                  {active ? "Actif" : "Inactif"}
                </span>
              </dd>
              <dt>Activation</dt>
              <dd>
                {formatDate(client.startDate)} → {client.endDate ? formatDate(client.endDate) : "Aucune fin"}
              </dd>
              <dt>Créé le</dt>
              <dd>{formatDate(client.createdAt)}</dd>
              <dt>Mis à jour le</dt>
              <dd>{formatDate(client.updatedAt)}</dd>
              <dt>E-mails envoyés</dt>
              <dd>{formatNumber(client.emailsSentCount)}</dd>
              <dt>Dernier envoi</dt>
              <dd>{formatDateTime(client.lastEmailSentAt)}</dd>
              <dt>Plan Stripe actuel</dt>
              <dd>
                {currentStripe
                  ? `${currentStripe.planKey ?? "—"} · ${currentStripe.status ?? "—"}`
                  : "—"}
              </dd>
              <dt>Admins en copie</dt>
              <dd>{client.includeAdminsInClientAlerts ? "Oui" : "Non"}</dd>
              <dt>Catégorie dans les alertes</dt>
              <dd>
                {client.useSubcategoryLabelInClientAlerts
                  ? "Sous-catégorie (code NAF)"
                  : "Catégorie"}
              </dd>
            </dl>
          </section>

          <section>
            <h3>Destinataires</h3>
            {client.recipients.length === 0 ? (
              <p className="muted">Aucun destinataire.</p>
            ) : (
              <div className="chip-list chip-list--plain">
                {client.recipients.map((recipient) => (
                  <span key={recipient.id} className="chip">
                    {recipient.email}
                  </span>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3>Abonnements NAF</h3>
            {client.subscriptions.length === 0 ? (
              <p className="muted">Aucun code NAF sélectionné.</p>
            ) : (
              <div className="chip-list chip-list--plain">
                {client.subscriptions.map((subscription) => (
                  <span key={subscription.subcategoryId} className="chip">
                    {subscription.subcategory.nafCode} · {subscription.subcategory.name}
                  </span>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3>Départements</h3>
            {client.departments.length === 0 ? (
              <p className="muted">Toute la France.</p>
            ) : (
              <div className="region-detail-grid">
                {departmentGroups.map((group) => (
                  <div key={group.name} className="region-detail-card">
                    <strong>{group.name}</strong>
                    <div className="chip-list chip-list--plain">
                      {group.entries.map((entry) => (
                        <span key={entry} className="chip">
                          {entry}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3>Statuts Google</h3>
            <div className="chip-list chip-list--plain">
              {listingStatuses.map((status) => (
                <span key={status} className="chip">
                  {status}
                </span>
              ))}
            </div>
          </section>

          <section>
            <h3>Historique Stripe</h3>
            {client.stripeSubscriptions.length === 0 ? (
              <p className="muted">Aucun historique Stripe.</p>
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Plan</th>
                      <th>Statut</th>
                      <th>Période</th>
                      <th>Achat</th>
                      <th>Parrain</th>
                    </tr>
                  </thead>
                  <tbody>
                    {client.stripeSubscriptions.map((subscription) => (
                      <tr key={subscription.id}>
                        <td>{subscription.planKey ?? "—"}</td>
                        <td>{subscription.status ?? "—"}</td>
                        <td>
                          {formatDate(subscription.currentPeriodStart)} →
                          {" "}
                          {formatDate(subscription.currentPeriodEnd)}
                        </td>
                        <td>{formatDateTime(subscription.purchasedAt)}</td>
                        <td>{subscription.referrerName ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <h3>Historique des changements</h3>
            {renderSubscriptionEvents(client.subscriptionEvents, categoryNames)}
          </section>
        </div>
      </div>
    </div>
  );
};

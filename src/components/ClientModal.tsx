import { FormEvent, useEffect, useMemo, useState } from "react";

import { Client, ListingStatus, NafCategory, Region } from "../types";
import { formatNumber, formatDateTime } from "../utils/format";
import { DEFAULT_LISTING_STATUSES, LISTING_STATUS_OPTIONS } from "../constants/listingStatuses";

type FormState = {
  name: string;
  startDate: string;
  endDate: string;
  listingStatuses: ListingStatus[];
  recipientsText: string;
  subscriptionIds: string[];
  regionIds: string[];
};

type SubmitPayload = {
  name: string;
  startDate: string;
  endDate: string | null;
  listingStatuses: ListingStatus[];
  recipients: string[];
  subscriptionIds: string[];
  regionIds: string[];
};

type Props = {
  isOpen: boolean;
  mode: "create" | "edit";
  client: Client | null;
  nafCategories: NafCategory[] | undefined;
  isLoadingNafCategories: boolean;
  regions: Region[] | undefined;
  isLoadingRegions: boolean;
  onSubmit: (payload: SubmitPayload) => void;
  onCancel: () => void;
  isProcessing: boolean;
};

const EMPTY_STATE: FormState = {
  name: "",
  startDate: "",
  endDate: "",
  listingStatuses: DEFAULT_LISTING_STATUSES,
  recipientsText: "",
  subscriptionIds: [],
  regionIds: [],
};

const splitRecipients = (value: string): string[] => {
  const normalized = value
    .split(/[\n,;]/)
    .map((entry) => entry.trim().toLowerCase())
    .filter((entry) => entry.length > 0);
  return Array.from(new Set(normalized));
};

export const ClientModal = ({
  isOpen,
  mode,
  client,
  nafCategories,
  isLoadingNafCategories,
  regions,
  isLoadingRegions,
  onSubmit,
  onCancel,
  isProcessing,
}: Props) => {
  const [formState, setFormState] = useState<FormState>(EMPTY_STATE);

  useEffect(() => {
    if (!isOpen) {
      setFormState(EMPTY_STATE);
      return;
    }
    if (client && mode === "edit") {
      const regionIds = client.regions.length
        ? client.regions.map((region) => region.id)
        : regions?.map((region) => region.id) ?? [];
      setFormState({
        name: client.name,
        startDate: client.startDate,
        endDate: client.endDate ?? "",
        listingStatuses: client.listingStatuses?.length ? client.listingStatuses : DEFAULT_LISTING_STATUSES,
        recipientsText: client.recipients.map((recipient) => recipient.email).join("\n"),
        subscriptionIds: client.subscriptions.map((subscription) => subscription.subcategoryId),
        regionIds,
      });
    } else {
      setFormState(EMPTY_STATE);
    }
  }, [client, isOpen, mode, regions]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    if (mode !== "create") {
      return;
    }
    if (!regions || regions.length === 0) {
      return;
    }
    setFormState((current) => {
      if (current.regionIds.length > 0) {
        return current;
      }
      return { ...current, regionIds: regions.map((region) => region.id) };
    });
  }, [isOpen, mode, regions]);

  const isValid = useMemo(() => {
    const hasRegions = regions && regions.length > 0 ? formState.regionIds.length > 0 : true;
    return Boolean(
      formState.name.trim()
        && formState.startDate
        && formState.listingStatuses.length > 0
        && hasRegions
    );
  }, [formState.name, formState.startDate, formState.listingStatuses.length, formState.regionIds.length, regions]);

  const handleChange = (field: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormState((current) => ({ ...current, [field]: event.target.value }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isValid) {
      return;
    }
    const payload: SubmitPayload = {
      name: formState.name.trim(),
      startDate: formState.startDate,
      endDate: formState.endDate ? formState.endDate : null,
      listingStatuses: formState.listingStatuses,
      recipients: splitRecipients(formState.recipientsText),
      subscriptionIds: formState.subscriptionIds,
      regionIds: formState.regionIds,
    };
    onSubmit(payload);
  };

  const handleToggleSubscription = (subcategoryId: string) => () => {
    setFormState((current) => {
      const exists = current.subscriptionIds.includes(subcategoryId);
      if (exists) {
        return { ...current, subscriptionIds: current.subscriptionIds.filter((id) => id !== subcategoryId) };
      }
      return { ...current, subscriptionIds: [...current.subscriptionIds, subcategoryId] };
    });
  };

  const handleToggleListingStatus = (status: ListingStatus) => () => {
    setFormState((current) => {
      const exists = current.listingStatuses.includes(status);
      if (exists) {
        const next = current.listingStatuses.filter((item) => item !== status);
        if (next.length === 0) {
          return current;
        }
        return { ...current, listingStatuses: next };
      }
      return { ...current, listingStatuses: [...current.listingStatuses, status] };
    });
  };

  const handleSelectAllStatuses = () => {
    setFormState((current) => ({ ...current, listingStatuses: [...DEFAULT_LISTING_STATUSES] }));
  };

  const handleToggleRegion = (regionId: string) => () => {
    setFormState((current) => {
      const exists = current.regionIds.includes(regionId);
      if (exists) {
        return { ...current, regionIds: current.regionIds.filter((id) => id !== regionId) };
      }
      return { ...current, regionIds: [...current.regionIds, regionId] };
    });
  };

  const handleToggleAllRegions = () => {
    if (!regions) {
      return;
    }
    const allIds = regions.map((region) => region.id);
    setFormState((current) => {
      const hasAll = allIds.length > 0 && allIds.every((id) => current.regionIds.includes(id));
      if (hasAll) {
        return { ...current, regionIds: [] };
      }
      return { ...current, regionIds: allIds };
    });
  };

  const handleToggleCategory = (categoryId: string) => () => {
    if (!nafCategories) {
      return;
    }
    const category = nafCategories.find((entry) => entry.id === categoryId);
    if (!category) {
      return;
    }
    const selectableIds = category.subcategories.filter((sub) => sub.isActive).map((sub) => sub.id);
    if (selectableIds.length === 0) {
      return;
    }
    setFormState((current) => {
      const hasAll = selectableIds.every((id) => current.subscriptionIds.includes(id));
      if (hasAll) {
        return {
          ...current,
          subscriptionIds: current.subscriptionIds.filter((id) => !selectableIds.includes(id)),
        };
      }
      const merged = new Set(current.subscriptionIds);
      selectableIds.forEach((id) => merged.add(id));
      return { ...current, subscriptionIds: Array.from(merged) };
    });
  };

  if (!isOpen) {
    return null;
  }

  const allRegionIds = (regions ?? []).map((region) => region.id);
  const selectedRegionsCount = formState.regionIds.length;
  const isAllRegionsSelected = allRegionIds.length > 0 && allRegionIds.every((id) => formState.regionIds.includes(id));
  const isRegionIndeterminate = selectedRegionsCount > 0 && !isAllRegionsSelected;
  const regionSelectionLabel = () => {
    if (isLoadingRegions) {
      return "Chargement des régions…";
    }
    if (!regions || regions.length === 0) {
      return "Aucune région";
    }
    if (isAllRegionsSelected) {
      return "Toute la France";
    }
    if (selectedRegionsCount === 1) {
      const region = regions.find((item) => formState.regionIds.includes(item.id));
      return region ? region.name : "1 région";
    }
    return `${selectedRegionsCount} sélectionnées`;
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal">
        <header className="modal-header">
          <h2>{mode === "create" ? "Nouveau client" : `Modifier ${client?.name ?? "le client"}`}</h2>
          <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
            Fermer
          </button>
        </header>
        <form className="modal-content" onSubmit={handleSubmit}>
          <section>
            <h3>Informations principales</h3>
            <div className="form-grid">
              <div className="form-field">
                <span className="input-label">Nom du client</span>
                <input
                  type="text"
                  value={formState.name}
                  onChange={handleChange("name")}
                  placeholder="Ex : Franchise Île-de-France"
                  required
                />
              </div>
              <div className="form-field">
                <span className="input-label">Date de début</span>
                <input type="date" value={formState.startDate} onChange={handleChange("startDate")} required />
              </div>
              <div className="form-field">
                <span className="input-label">Date de fin (optionnelle)</span>
                <input type="date" value={formState.endDate} onChange={handleChange("endDate")} />
              </div>
            </div>
          </section>

          <section>
            <h3>Destinataires</h3>
            <p className="muted small">
              Une adresse par ligne ou séparée par des virgules. Les adresses seront dédupliquées et converties en
              minuscules.
            </p>
            <div className="form-field">
              <textarea
                rows={6}
                value={formState.recipientsText}
                onChange={handleChange("recipientsText")}
                placeholder="client@example.com"
              />
            </div>
          </section>

          <section>
            <h3>Statuts des fiches Google</h3>
            <p className="muted small">Sélectionnez les statuts qui déclenchent des alertes pour ce client.</p>
            <div className="listing-status-grid">
              {LISTING_STATUS_OPTIONS.map((option) => {
                const checked = formState.listingStatuses.includes(option.value);
                return (
                  <label key={option.value} className="listing-status-option">
                    <input type="checkbox" checked={checked} onChange={handleToggleListingStatus(option.value)} />
                    <div>
                      <strong>{option.label}</strong>
                      <div className="muted small">{option.description}</div>
                    </div>
                  </label>
                );
              })}
            </div>
            <div className="card-actions" style={{ justifyContent: "flex-start", marginTop: "0.5rem" }}>
              <button type="button" className="ghost" onClick={handleSelectAllStatuses}>
                Tout sélectionner
              </button>
            </div>
          </section>

          <section>
            <h3>Abonnements NAF</h3>
            {isLoadingNafCategories ? <p>Chargement des catégories…</p> : null}
            {!isLoadingNafCategories && (!nafCategories || nafCategories.length === 0) ? (
              <p className="muted small">
                Aucune sous-catégorie configurée. Rendez-vous dans le sous-menu « Config NAF » pour en ajouter.
              </p>
            ) : null}
            {nafCategories && nafCategories.length > 0 ? (
              <div className="naf-subscription-grid">
                {nafCategories.map((category) => {
                  const activeSubcategories = category.subcategories.filter((sub) => sub.isActive);
                  const activeIds = activeSubcategories.map((sub) => sub.id);
                  const selectedCount = activeIds.filter((id) => formState.subscriptionIds.includes(id)).length;
                  const isCategoryChecked = activeIds.length > 0 && selectedCount === activeIds.length;
                  const isCategoryIndeterminate = selectedCount > 0 && selectedCount < activeIds.length;

                  return (
                    <article key={category.id}>
                      <div className="naf-category-header">
                        <strong>{category.name}</strong>
                        <label className="category-select-toggle">
                          <input
                            type="checkbox"
                            ref={(input) => {
                              if (input) {
                                input.indeterminate = isCategoryIndeterminate;
                              }
                            }}
                            checked={isCategoryChecked}
                            disabled={activeIds.length === 0}
                            onChange={handleToggleCategory(category.id)}
                          />
                          <span>Tout sélectionner</span>
                        </label>
                      </div>
                      {category.subcategories.length === 0 ? (
                        <p className="small muted">Aucune sous-catégorie.</p>
                      ) : (
                        <ul className="naf-subscription-list">
                          {category.subcategories.map((subcategory) => {
                            const checked = formState.subscriptionIds.includes(subcategory.id);
                            return (
                              <li key={subcategory.id}>
                                <label>
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={handleToggleSubscription(subcategory.id)}
                                    disabled={!subcategory.isActive}
                                  />
                                  <span>
                                    {subcategory.nafCode} · {subcategory.name}
                                    {!subcategory.isActive ? " (inactif)" : ""}
                                  </span>
                                </label>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : null}
          </section>

          <section>
            <h3>Régions surveillées</h3>
            <p className="muted small">
              Choisissez les régions géographiques couvertes par ce client. Par défaut, toutes les régions sont
              sélectionnées.
            </p>
            <div className="region-selection">
              <details className="region-multiselect">
                <summary className="muted small">Régions : {regionSelectionLabel()}</summary>
                <div className="region-multiselect-panel">
                  {isLoadingRegions ? <p className="muted small">Chargement des régions…</p> : null}
                  {!isLoadingRegions && (!regions || regions.length === 0) ? (
                    <p className="muted small">Aucune région disponible.</p>
                  ) : null}
                  {regions && regions.length > 0 ? (
                    <div className="region-multiselect-options">
                      <label className="region-multiselect-option">
                        <input
                          type="checkbox"
                          ref={(input) => {
                            if (input) {
                              input.indeterminate = isRegionIndeterminate;
                            }
                          }}
                          checked={isAllRegionsSelected}
                          onChange={handleToggleAllRegions}
                        />
                        <span>Toute la France</span>
                      </label>
                      {regions.map((region) => {
                        const checked = formState.regionIds.includes(region.id);
                        return (
                          <label key={region.id} className="region-multiselect-option">
                            <input type="checkbox" checked={checked} onChange={handleToggleRegion(region.id)} />
                            <span>{region.name}</span>
                          </label>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              </details>
            </div>
            {!isLoadingRegions && regions && regions.length > 0 && formState.regionIds.length === 0 ? (
              <p className="small error">Sélectionnez au moins une région.</p>
            ) : null}
          </section>

          {mode === "edit" && client ? (
            <section>
              <h3>Historique</h3>
              <p className="small muted">
                E-mails envoyés : {formatNumber(client.emailsSentCount)}
                <br />
                Dernier envoi : {formatDateTime(client.lastEmailSentAt)}
              </p>
            </section>
          ) : null}

          <section className="card-actions">
            <button type="button" className="ghost" onClick={onCancel} disabled={isProcessing}>
              Annuler
            </button>
            <button type="submit" className="primary" disabled={!isValid || isProcessing}>
              {isProcessing ? "Enregistrement…" : "Enregistrer"}
            </button>
          </section>
        </form>
      </div>
    </div>
  );
};

export type { SubmitPayload as ClientFormSubmitPayload };

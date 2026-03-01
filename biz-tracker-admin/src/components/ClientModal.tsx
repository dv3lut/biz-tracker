import { FormEvent, useEffect, useMemo, useState } from "react";

import { Client, ListingStatus, NafCategory, Region } from "../types";
import { RegionDepartmentPanel } from "./RegionDepartmentPanel";
import { formatNumber, formatDateTime } from "../utils/format";
import { DEFAULT_LISTING_STATUSES, LISTING_STATUS_OPTIONS } from "../constants/listingStatuses";

type FormState = {
  name: string;
  startDate: string;
  endDate: string;
  listingStatuses: ListingStatus[];
  includeAdminsInClientAlerts: boolean;
  useSubcategoryLabelInClientAlerts: boolean;
  recipientsText: string;
  subscriptionIds: string[];
  departmentCodes: string[];
};

type SubmitPayload = {
  name: string;
  startDate: string;
  endDate: string | null;
  listingStatuses: ListingStatus[];
  includeAdminsInClientAlerts: boolean;
  useSubcategoryLabelInClientAlerts: boolean;
  recipients: string[];
  subscriptionIds: string[];
  departmentIds: string[];
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
  includeAdminsInClientAlerts: false,
  useSubcategoryLabelInClientAlerts: false,
  recipientsText: "",
  subscriptionIds: [],
  departmentCodes: [],
};

const splitRecipients = (value: string): string[] => {
  const normalized = value
    .split(/[\n,;]/)
    .map((entry) => entry.trim().toLowerCase())
    .filter((entry) => entry.length > 0);
  return Array.from(new Set(normalized));
};

const resolveDepartmentIds = (codes: string[], regions: Region[] | undefined): string[] => {
  if (!regions || regions.length === 0) {
    return [];
  }
  const map = new Map<string, string>();
  regions.forEach((region) => {
    region.departments.forEach((department) => {
      map.set(department.code, department.id);
    });
  });
  return codes
    .map((code) => map.get(code))
    .filter((value): value is string => Boolean(value));
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
      const departmentCodes = client.departments.length
        ? client.departments.map((department) => department.code)
        : regions?.flatMap((region) => region.departments.map((department) => department.code)) ?? [];
      setFormState({
        name: client.name,
        startDate: client.startDate,
        endDate: client.endDate ?? "",
        listingStatuses: client.listingStatuses?.length ? client.listingStatuses : DEFAULT_LISTING_STATUSES,
        includeAdminsInClientAlerts: client.includeAdminsInClientAlerts ?? false,
        useSubcategoryLabelInClientAlerts: client.useSubcategoryLabelInClientAlerts ?? false,
        recipientsText: client.recipients.map((recipient) => recipient.email).join("\n"),
        subscriptionIds: client.subscriptions.map((subscription) => subscription.subcategoryId),
        departmentCodes,
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
      if (current.departmentCodes.length > 0) {
        return current;
      }
      return {
        ...current,
        departmentCodes: regions.flatMap((region) =>
          region.departments.map((department) => department.code),
        ),
      };
    });
  }, [isOpen, mode, regions]);

  const isValid = useMemo(() => {
    const hasRegions = regions && regions.length > 0 ? formState.departmentCodes.length > 0 : true;
    return Boolean(
      formState.name.trim()
        && formState.startDate
        && formState.listingStatuses.length > 0
        && hasRegions
    );
  }, [formState.name, formState.startDate, formState.listingStatuses.length, formState.departmentCodes.length, regions]);

  const handleChange = (field: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormState((current) => ({ ...current, [field]: event.target.value }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isValid) {
      return;
    }
    const departmentIds = resolveDepartmentIds(formState.departmentCodes, regions);
    const payload: SubmitPayload = {
      name: formState.name.trim(),
      startDate: formState.startDate,
      endDate: formState.endDate ? formState.endDate : null,
      listingStatuses: formState.listingStatuses,
      includeAdminsInClientAlerts: formState.includeAdminsInClientAlerts,
      useSubcategoryLabelInClientAlerts: formState.useSubcategoryLabelInClientAlerts,
      recipients: splitRecipients(formState.recipientsText),
      subscriptionIds: formState.subscriptionIds,
      departmentIds,
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

  const handleToggleAdminCopy = () => {
    setFormState((current) => ({
      ...current,
      includeAdminsInClientAlerts: !current.includeAdminsInClientAlerts,
    }));
  };

  const handleToggleSubcategoryLabel = () => {
    setFormState((current) => ({
      ...current,
      useSubcategoryLabelInClientAlerts: !current.useSubcategoryLabelInClientAlerts,
    }));
  };

  const handleDepartmentCodesChange = (codes: string[]) => {
    setFormState((current) => ({ ...current, departmentCodes: codes }));
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

  const allDepartmentCodes = regions
    ? regions.flatMap((region) => region.departments.map((department) => department.code))
    : [];
  const selectedDepartmentsCount = formState.departmentCodes.length;
  const isAllDepartmentsSelected =
    allDepartmentCodes.length > 0 && allDepartmentCodes.every((code) => formState.departmentCodes.includes(code));

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
            <label className="form-checkbox">
              <input
                type="checkbox"
                checked={formState.includeAdminsInClientAlerts}
                onChange={handleToggleAdminCopy}
              />
              <span>Mettre les admins en copie des alertes client</span>
            </label>
            <label className="form-checkbox">
              <input
                type="checkbox"
                checked={formState.useSubcategoryLabelInClientAlerts}
                onChange={handleToggleSubcategoryLabel}
              />
              <span>Afficher la sous-catégorie (code NAF) dans les alertes client</span>
            </label>
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
                            onChange={handleToggleCategory(category.id)}
                          />
                          <span className="muted small">Tout sélectionner</span>
                        </label>
                      </div>
                      <ul className="naf-subscription-list">
                        {activeSubcategories.map((subcategory) => {
                          const checked = formState.subscriptionIds.includes(subcategory.id);
                          return (
                            <li key={subcategory.id} className="naf-subscription-item">
                              <label>
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={handleToggleSubscription(subcategory.id)}
                                />
                                <span>
                                  {subcategory.nafCode} · {subcategory.name}
                                </span>
                              </label>
                            </li>
                          );
                        })}
                      </ul>
                    </article>
                  );
                })}
              </div>
            ) : null}
          </section>

          <section>
            <h3>Départements</h3>
            <RegionDepartmentPanel
              regions={regions}
              isLoading={isLoadingRegions}
              selectedDepartmentCodes={formState.departmentCodes}
              onSelectionChange={handleDepartmentCodesChange}
              helperText="Sélectionnez une région pour inclure tous ses départements, ou choisissez au détail."
            />
            {isAllDepartmentsSelected ? (
              <p className="muted small">Toute la France est couverte.</p>
            ) : (
              <p className="muted small">{selectedDepartmentsCount} départements sélectionnés.</p>
            )}
            {!isLoadingRegions && regions && regions.length > 0 && formState.departmentCodes.length === 0 ? (
              <p className="small error">Sélectionnez au moins un département.</p>
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

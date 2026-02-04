import { Fragment, useMemo, useState } from "react";

import type { NafCategory, NafSubCategory, Region } from "../types";
import { formatCurrency, formatNumber } from "../utils/format";

const truncateText = (text: string, maxLength: number): string => {
  return text.length > maxLength ? `${text.substring(0, maxLength)}…` : text;
};

type Props = {
  categories?: NafCategory[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onRefresh: () => void;
  regions?: Region[];
  onCreateCategory: () => void;
  onEditCategory: (category: NafCategory) => void;
  onDeleteCategory: (category: NafCategory) => void;
  onCreateSubCategory: (categoryId?: string) => void;
  onEditSubCategory: (subcategory: NafSubCategory) => void;
  onDeleteSubCategory: (subcategory: NafSubCategory) => void;
  deletingCategoryId: string | null;
  deletingSubCategoryId: string | null;
};

export const NafCategoriesSection = ({
  categories,
  isLoading,
  isRefreshing,
  error,
  feedbackMessage,
  errorMessage,
  onRefresh,
  regions,
  onCreateCategory,
  onEditCategory,
  onDeleteCategory,
  onCreateSubCategory,
  onEditSubCategory,
  onDeleteSubCategory,
  deletingCategoryId,
  deletingSubCategoryId,
}: Props) => {
  const [activeSubcategory, setActiveSubcategory] = useState<NafSubCategory | null>(null);

  const regionIndex = useMemo(() => {
    const map = new Map<string, Region>();
    (regions ?? []).forEach((region) => {
      map.set(region.id, region);
    });
    return map;
  }, [regions]);

  const handleDeleteCategory = (category: NafCategory) => {
    if (
      window.confirm(
        `Supprimer la catégorie "${category.name}" ainsi que ses sous-catégories ? Cette action est irréversible.`,
      )
    ) {
      onDeleteCategory(category);
    }
  };

  const handleDeleteSubCategory = (subcategory: NafSubCategory) => {
    if (
      window.confirm(
        `Supprimer la sous-catégorie "${subcategory.name}" (${subcategory.nafCode}) ?`,
      )
    ) {
      onDeleteSubCategory(subcategory);
    }
  };

  const handleOpenSubcategoryDetails = (subcategory: NafSubCategory) => {
    setActiveSubcategory(subcategory);
  };

  const handleCloseSubcategoryDetails = () => {
    setActiveSubcategory(null);
  };

  const groupedDepartments = useMemo(() => {
    if (!activeSubcategory) {
      return [];
    }
    const grouping = new Map<
      string,
      { region: Region | null; departments: NafSubCategory["googleDepartments"] }
    >();
    activeSubcategory.googleDepartments.forEach((department) => {
      const region = regionIndex.get(department.regionId) ?? null;
      const key = region?.id ?? department.regionId;
      if (!grouping.has(key)) {
        grouping.set(key, { region, departments: [] });
      }
      grouping.get(key)?.departments.push(department);
    });
    return Array.from(grouping.values()).sort((a, b) => {
      const orderA = a.region?.orderIndex ?? Number.MAX_SAFE_INTEGER;
      const orderB = b.region?.orderIndex ?? Number.MAX_SAFE_INTEGER;
      if (orderA !== orderB) {
        return orderA - orderB;
      }
      const nameA = a.region?.name ?? "";
      const nameB = b.region?.name ?? "";
      return nameA.localeCompare(nameB);
    });
  }, [activeSubcategory, regionIndex]);

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Configuration NAF</h2>
          <p className="muted">
            Catégories, codes NAF surveillés et tarification des abonnements clients.
          </p>
        </div>
        <div className="card-actions">
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Rafraîchir
          </button>
          <button type="button" className="ghost" onClick={() => onCreateSubCategory()} disabled={isLoading}>
            Nouvelle sous-catégorie
          </button>
          <button type="button" className="primary" onClick={onCreateCategory}>
            Nouvelle catégorie
          </button>
        </div>
      </header>

      {feedbackMessage ? <p className="feedback success">{feedbackMessage}</p> : null}
      {errorMessage ? <p className="feedback error">{errorMessage}</p> : null}

      {isLoading && <p>Chargement des catégories…</p>}
      {isRefreshing && !isLoading && <p className="refresh-indicator">Actualisation en cours…</p>}
      {error && <p className="error">{error.message}</p>}

      {!isLoading && !error && categories && categories.length === 0 && (
        <p className="muted">Aucune catégorie NAF n'a encore été créée.</p>
      )}

      {!isLoading && !error && categories && categories.length > 0 && (
        <div className="category-list">
          {categories.map((category) => (
            <article key={category.id} className="category-card">
              <header className="category-card-header">
                <div>
                  <strong>{category.name}</strong>
                  {category.description ? <p className="small muted">{category.description}</p> : null}
                  {category.keywords && category.keywords.length > 0 ? (
                    <p className="small muted">
                      Mots-clés : {category.keywords.join(", ")}
                    </p>
                  ) : null}
                </div>
                <div className="card-actions">
                  <button type="button" className="ghost" onClick={() => onCreateSubCategory(category.id)}>
                    Ajouter une sous-catégorie
                  </button>
                  <button type="button" className="ghost" onClick={() => onEditCategory(category)}>
                    Modifier
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => handleDeleteCategory(category)}
                    disabled={deletingCategoryId === category.id}
                  >
                    {deletingCategoryId === category.id ? "Suppression…" : "Supprimer"}
                  </button>
                </div>
              </header>

              {category.subcategories.length === 0 ? (
                <p className="muted small">Aucune sous-catégorie.</p>
              ) : (
                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th style={{ width: "auto" }}>Nom</th>
                        <th style={{ width: "120px", whiteSpace: "nowrap" }}>Code NAF</th>
                        <th style={{ width: "110px", whiteSpace: "nowrap" }}>Tarif</th>
                        <th style={{ width: "100px", whiteSpace: "nowrap" }}>Statut</th>
                        <th style={{ width: "150px", whiteSpace: "nowrap" }}>Départements Google</th>
                        <th style={{ width: "110px", whiteSpace: "nowrap" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {category.subcategories.map((subcategory) => (
                        <Fragment key={subcategory.id}>
                          <tr>
                            <td>
                              <div style={{ minWidth: "200px" }}>
                                <button
                                  type="button"
                                  className="naf-subcategory-toggle"
                                  onClick={() => handleOpenSubcategoryDetails(subcategory)}
                                >
                                  <strong>{subcategory.name}</strong>
                                  <span className="muted small">Voir détails</span>
                                </button>
                                {subcategory.description ? (
                                  <p className="small muted" title={subcategory.description}>
                                    {truncateText(subcategory.description, 150)}
                                  </p>
                                ) : null}
                              </div>
                            </td>
                            <td style={{ whiteSpace: "nowrap" }}>
                              <span className="badge">{subcategory.nafCode}</span>
                            </td>
                            <td style={{ whiteSpace: "nowrap" }}>{formatCurrency(subcategory.priceEur)}</td>
                            <td style={{ whiteSpace: "nowrap" }}>
                              <span className={`badge status-${subcategory.isActive ? "success" : "error"}`}>
                                {subcategory.isActive ? "Active" : "Inactive"}
                              </span>
                            </td>
                            <td style={{ whiteSpace: "nowrap" }}>
                              <div className="naf-department-count">
                                <span className="badge">{formatNumber(subcategory.googleDepartmentCount)}</span>
                                {subcategory.googleDepartmentAll ? <span className="muted small">Tous</span> : null}
                              </div>
                            </td>
                            <td style={{ whiteSpace: "nowrap" }}>
                              <div className="card-actions">
                                <button type="button" className="ghost" onClick={() => onEditSubCategory(subcategory)}>
                                  Modifier
                                </button>
                                <button
                                  type="button"
                                  className="danger"
                                  onClick={() => handleDeleteSubCategory(subcategory)}
                                  disabled={deletingSubCategoryId === subcategory.id}
                                >
                                  {deletingSubCategoryId === subcategory.id ? "Suppression…" : "Supprimer"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      {activeSubcategory ? (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal naf-department-modal">
            <header className="modal-header">
              <div>
                <h3>{activeSubcategory.name}</h3>
                <p className="muted small">
                  Code NAF {activeSubcategory.nafCode} · {formatNumber(activeSubcategory.googleDepartmentCount)}
                  {activeSubcategory.googleDepartmentAll ? " départements (tous)" : " départements"}
                </p>
              </div>
              <button type="button" className="ghost" onClick={handleCloseSubcategoryDetails}>
                Fermer
              </button>
            </header>
            <div className="modal-content">
              {activeSubcategory.googleDepartmentCount === 0 ? (
                <p className="muted">Aucun département activé pour ce NAF.</p>
              ) : activeSubcategory.googleDepartmentAll ? (
                <p className="muted">Tous les départements sont couverts.</p>
              ) : (
                <div className="naf-region-stair">
                  {groupedDepartments.map((group) => (
                    <div key={group.region?.id ?? group.departments[0]?.regionId} className="naf-region-step">
                      <div className="naf-region-label">
                        <strong>{group.region?.name ?? "Région inconnue"}</strong>
                        {group.region?.code ? <span className="muted small">{group.region.code}</span> : null}
                      </div>
                      <div className="naf-region-departments">
                        {group.departments.map((department) => (
                          <span key={department.id} className="naf-department-chip">
                            {department.code} · {department.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
};

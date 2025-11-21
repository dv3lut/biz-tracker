import type { NafCategory, NafSubCategory } from "../types";
import { formatCurrency } from "../utils/format";

type Props = {
  categories?: NafCategory[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: Error | null;
  feedbackMessage: string | null;
  errorMessage: string | null;
  onRefresh: () => void;
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
  onCreateCategory,
  onEditCategory,
  onDeleteCategory,
  onCreateSubCategory,
  onEditSubCategory,
  onDeleteSubCategory,
  deletingCategoryId,
  deletingSubCategoryId,
}: Props) => {
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
                        <th>Nom</th>
                        <th>Code NAF</th>
                        <th>Tarif</th>
                        <th>Statut</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {category.subcategories.map((subcategory) => (
                        <tr key={subcategory.id}>
                          <td>
                            <strong>{subcategory.name}</strong>
                          </td>
                          <td>
                            <span className="badge">{subcategory.nafCode}</span>
                          </td>
                          <td>{formatCurrency(subcategory.priceEur)}</td>
                          <td>
                            <span className={`badge status-${subcategory.isActive ? "success" : "error"}`}>
                              {subcategory.isActive ? "Active" : "Inactive"}
                            </span>
                          </td>
                          <td>
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
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

import { Fragment } from "react";

import { NafCategoryStat, NafSubCategoryStat } from "../types";
import { formatNumber } from "../utils/format";

const GOOGLE_STATUS_COLUMNS: Array<{
  key: StatusMetricKey;
  label: string;
  tone: StatusTone;
}> = [
  { key: "googleFound", label: "Fiches trouvées", tone: "success" },
  { key: "googleNotFound", label: "Sans résultat", tone: "warning" },
  { key: "googleInsufficient", label: "Identité insuffisante", tone: "danger" },
  { key: "googlePending", label: "En attente", tone: "pending" },
  { key: "googleTypeMismatch", label: "Type mismatch", tone: "danger" },
  { key: "googleOther", label: "Autres statuts", tone: "muted" },
];

const LISTING_STATUS_COLUMNS: Array<{
  key: ListingMetricKey;
  label: string;
  tone: StatusTone;
}> = [
  { key: "listingRecent", label: "Création récente", tone: "success" },
  { key: "listingNotRecent", label: "Création ancienne", tone: "warning" },
  { key: "listingUnknown", label: "Ancienneté inconnue", tone: "muted" },
];

type StatusMetricKey =
  | "googleFound"
  | "googleNotFound"
  | "googleInsufficient"
  | "googlePending"
  | "googleTypeMismatch"
  | "googleOther";

type ListingMetricKey = "listingRecent" | "listingNotRecent" | "listingUnknown";

type StatusTone = "success" | "warning" | "danger" | "pending" | "muted";

type NumericMetricKey = StatusMetricKey | ListingMetricKey | "establishmentCount";

type Props = {
  categories: NafCategoryStat[];
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
  isRefreshing: boolean;
};

const sumMetric = (entries: NafSubCategoryStat[], key: NumericMetricKey): number => {
  return entries.reduce((acc, entry) => acc + (entry[key] ?? 0), 0);
};

const buildCategoryTotals = (category: NafCategoryStat) => {
  return {
    establishmentCount: sumMetric(category.subcategories, "establishmentCount"),
    googleFound: sumMetric(category.subcategories, "googleFound"),
    googleNotFound: sumMetric(category.subcategories, "googleNotFound"),
    googleInsufficient: sumMetric(category.subcategories, "googleInsufficient"),
    googlePending: sumMetric(category.subcategories, "googlePending"),
    googleTypeMismatch: sumMetric(category.subcategories, "googleTypeMismatch"),
    googleOther: sumMetric(category.subcategories, "googleOther"),
    listingRecent: sumMetric(category.subcategories, "listingRecent"),
    listingNotRecent: sumMetric(category.subcategories, "listingNotRecent"),
    listingUnknown: sumMetric(category.subcategories, "listingUnknown"),
  };
};

export const StatisticsPanel = ({ categories, isLoading, error, onRefresh, isRefreshing }: Props) => {
  const visibleCategories = categories.filter((category) => category.subcategories.length > 0);
  const columnCount = GOOGLE_STATUS_COLUMNS.length + LISTING_STATUS_COLUMNS.length + 2;

  return (
    <section className="card statistics-card">
      <header className="card-header">
        <div>
          <h2>Statistiques</h2>
          <p className="muted">Tableau plein écran des statuts Google par sous-catégorie.</p>
        </div>
        <div className="card-actions">
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Rafraîchir
          </button>
        </div>
      </header>

      {isRefreshing && !isLoading ? <p className="refresh-indicator">Actualisation en cours…</p> : null}
      {isLoading ? <p>Chargement...</p> : null}
      {error ? <p className="error">{error.message}</p> : null}

      {!isLoading && !error ? (
        visibleCategories.length === 0 ? (
          <p className="muted">Aucune sous-catégorie active configurée pour l'instant.</p>
        ) : (
          <div className="statistics-table-wrapper">
            <table className="statistics-table">
              <thead>
                <tr>
                  <th rowSpan={2}>Sous-catégorie</th>
                  <th rowSpan={2}>Établissements suivis</th>
                  <th colSpan={GOOGLE_STATUS_COLUMNS.length}>Statuts Google</th>
                  <th colSpan={LISTING_STATUS_COLUMNS.length}>Ancienneté des fiches</th>
                </tr>
                <tr>
                  {GOOGLE_STATUS_COLUMNS.map((column) => (
                    <th key={`google-header-${column.key}`}>{column.label}</th>
                  ))}
                  {LISTING_STATUS_COLUMNS.map((column) => (
                    <th key={`listing-header-${column.key}`}>{column.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleCategories.map((category) => {
                  const totals = buildCategoryTotals(category);
                  return (
                    <Fragment key={category.categoryId}>
                      <tr className="statistics-table-category">
                        <td colSpan={columnCount}>
                          <div className="statistics-category-header">
                            <div>
                              <span className="statistics-category-label">{category.name}</span>
                              <p className="muted small">NAF suivies : {category.subcategories.length}</p>
                            </div>
                            <strong>{formatNumber(category.totalEstablishments)} établissements</strong>
                          </div>
                        </td>
                      </tr>
                      {category.subcategories.map((sub) => (
                        <tr key={sub.subcategoryId}>
                          <td>
                            <div className="statistics-subcategory">
                              <strong>{sub.name}</strong>
                              <span className="muted small">{sub.nafCode}</span>
                            </div>
                          </td>
                          <td className="statistics-cell-number">{formatNumber(sub.establishmentCount)}</td>
                          {GOOGLE_STATUS_COLUMNS.map((column) => (
                            <td key={`${sub.subcategoryId}-${column.key}`} className="statistics-cell-number">
                              <span className={`status-pill status-pill--${column.tone}`}>
                                {formatNumber(sub[column.key])}
                              </span>
                            </td>
                          ))}
                          {LISTING_STATUS_COLUMNS.map((column) => (
                            <td key={`${sub.subcategoryId}-${column.key}`} className="statistics-cell-number">
                              <span className={`status-pill status-pill--${column.tone}`}>
                                {formatNumber(sub[column.key])}
                              </span>
                            </td>
                          ))}
                        </tr>
                      ))}
                      <tr className="statistics-table-total-row">
                        <td>Total {category.name}</td>
                        <td className="statistics-cell-number">{formatNumber(totals.establishmentCount)}</td>
                        {GOOGLE_STATUS_COLUMNS.map((column) => (
                          <td key={`${category.categoryId}-${column.key}`} className="statistics-cell-number">
                            {formatNumber(totals[column.key])}
                          </td>
                        ))}
                        {LISTING_STATUS_COLUMNS.map((column) => (
                          <td key={`${category.categoryId}-${column.key}`} className="statistics-cell-number">
                            {formatNumber(totals[column.key])}
                          </td>
                        ))}
                      </tr>
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )
      ) : null}
    </section>
  );
};

import { NafCategoryStat, NafSubCategoryStat } from "../types";
import { formatNumber } from "../utils/format";

const METRIC_COLUMNS: Array<{ key: MetricKey; label: string }> = [
  { key: "establishmentCount", label: "Total suivis" },
  { key: "googleFound", label: "Fiches trouvées" },
  { key: "googleNotFound", label: "Sans résultat" },
  { key: "googleInsufficient", label: "Identité insuffisante" },
  { key: "googlePending", label: "En attente" },
  { key: "googleOther", label: "Autres statuts" },
  { key: "listingRecent", label: "Création récente" },
  { key: "listingNotRecent", label: "Création ancienne" },
  { key: "listingUnknown", label: "Ancienneté inconnue" },
];

type MetricKey =
  | "establishmentCount"
  | "googleFound"
  | "googleNotFound"
  | "googleInsufficient"
  | "googlePending"
  | "googleOther"
  | "listingRecent"
  | "listingNotRecent"
  | "listingUnknown";

type Props = {
  categories: NafCategoryStat[];
};

const sumMetric = (subcategories: NafSubCategoryStat[], key: MetricKey): number => {
  return subcategories.reduce((acc, entry) => acc + (entry[key] ?? 0), 0);
};

export const CategoryBreakdownTable = ({ categories }: Props) => {
  if (categories.length === 0) {
    return <p className="muted">Aucune catégorie configurée.</p>;
  }

  return (
    <div className="category-table-stack">
      {categories.map((category) => {
        const totals: Record<MetricKey, number> = METRIC_COLUMNS.reduce(
          (acc, column) => ({
            ...acc,
            [column.key]: sumMetric(category.subcategories, column.key),
          }),
          {
            establishmentCount: 0,
            googleFound: 0,
            googleNotFound: 0,
            googleInsufficient: 0,
            googlePending: 0,
            googleOther: 0,
            listingRecent: 0,
            listingNotRecent: 0,
            listingUnknown: 0,
          },
        );

        return (
          <div key={category.categoryId} className="category-table-block">
            <div className="category-panel-header">
              <strong>{category.name}</strong>
              <span className="muted small">{formatNumber(category.totalEstablishments)} établissements</span>
            </div>
            {category.subcategories.length === 0 ? (
              <p className="muted small">Aucune sous-catégorie active.</p>
            ) : (
              <div className="table-wrapper">
                <table className="subcategory-table">
                  <thead>
                    <tr>
                      <th>Sous-catégorie</th>
                      {METRIC_COLUMNS.map((column) => (
                        <th key={column.key}>{column.label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {category.subcategories.map((sub) => (
                      <tr key={sub.subcategoryId}>
                        <td>
                          <div className="subcategory-name">
                            <strong>{sub.name}</strong>
                            <span className="muted small">{sub.nafCode}</span>
                          </div>
                        </td>
                        {METRIC_COLUMNS.map((column) => (
                          <td key={`${sub.subcategoryId}-${column.key}`}>
                            {formatNumber(sub[column.key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                    <tr className="category-table-total">
                      <td>Total {category.name}</td>
                      {METRIC_COLUMNS.map((column) => (
                        <td key={`${category.categoryId}-total-${column.key}`}>
                          {formatNumber(totals[column.key])}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

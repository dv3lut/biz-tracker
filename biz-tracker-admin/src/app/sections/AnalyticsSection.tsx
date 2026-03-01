import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import { analyticsApi, ApiError } from "../../api";
import { formatNumber } from "../../utils/format";
import type {
  NafAnalyticsAggregation,
  NafAnalyticsGranularity,
  NafAnalyticsResponse,
  NafAnalyticsTimePoint,
} from "../../types";

type Props = {
  onUnauthorized: () => void;
};

const GRANULARITY_OPTIONS: { value: NafAnalyticsGranularity; label: string }[] = [
  { value: "day", label: "Par jour" },
  { value: "week", label: "Par semaine" },
  { value: "month", label: "Par mois" },
];

const AGGREGATION_OPTIONS: { value: NafAnalyticsAggregation; label: string }[] = [
  { value: "category", label: "Par catégorie" },
  { value: "subcategory", label: "Par sous-catégorie" },
];

const DATE_RANGE_PRESETS = [
  { label: "7 derniers jours", days: 7 },
  { label: "30 derniers jours", days: 30 },
  { label: "90 derniers jours", days: 90 },
  { label: "6 mois", days: 180 },
];

const formatDate = (date: Date) => date.toISOString().slice(0, 10);

const getDefaultDateRange = () => {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  return { start: formatDate(start), end: formatDate(end) };
};

const COLORS = [
  "#2563eb",
  "#16a34a",
  "#dc2626",
  "#f97316",
  "#8b5cf6",
  "#ec4899",
  "#0891b2",
  "#ca8a04",
  "#6366f1",
  "#14b8a6",
];

const ProportionsTooltip = ({ active, payload, label }: TooltipProps<ValueType, NameType>) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  return (
    <div className="chart-tooltip">
      <span className="chart-tooltip-label">{label}</span>
      {payload.map((entry) => (
        <span key={String(entry.name)} className="chart-tooltip-row">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <strong>{formatNumber(Number(entry.value ?? 0))}</strong>
        </span>
      ))}
    </div>
  );
};

const computeProportions = (point: NafAnalyticsTimePoint) => {
  const searchable = point.totalFetched - point.nonDiffusible - point.insufficientInfo;
  const googleTracked = point.googleFound + point.googleNotFound + point.googlePending;
  const total = point.totalFetched || 1;
  return {
    nonDiffusiblePct: Math.round((point.nonDiffusible / total) * 100),
    insufficientPct: Math.round((point.insufficientInfo / total) * 100),
    googleFoundPct: googleTracked > 0 ? Math.round((point.googleFound / googleTracked) * 100) : 0,
    googleNotFoundPct: googleTracked > 0 ? Math.round((point.googleNotFound / googleTracked) * 100) : 0,
    listingRecentPct: point.googleFound > 0 ? Math.round((point.listingRecent / point.googleFound) * 100) : 0,
    listingRecentMissingContactPct:
      point.googleFound > 0 ? Math.round((point.listingRecentMissingContact / point.googleFound) * 100) : 0,
    linkedinFoundPct: searchable > 0 ? Math.round((point.linkedinFound / searchable) * 100) : 0,
    alertsPct: searchable > 0 ? Math.round((point.alertsCreated / searchable) * 100) : 0,
    googleWithWebsitePct: point.googleFound > 0 ? Math.round((point.websiteWithWebsite / point.googleFound) * 100) : 0,
    websiteScrapedPct: point.websiteWithWebsite > 0 ? Math.round((point.websiteScraped / point.websiteWithWebsite) * 100) : 0,
    websiteScrapedWithInfoPct:
      point.websiteScraped > 0
        ? Math.round((point.websiteScrapedWithInfo / point.websiteScraped) * 100)
        : 0,
  };
};

export const AnalyticsSection = ({ onUnauthorized }: Props) => {
  const defaultRange = useMemo(getDefaultDateRange, []);
  const [startDate, setStartDate] = useState(defaultRange.start);
  const [endDate, setEndDate] = useState(defaultRange.end);
  const [granularity, setGranularity] = useState<NafAnalyticsGranularity>("week");
  const [aggregation, setAggregation] = useState<NafAnalyticsAggregation>("subcategory");
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery<NafAnalyticsResponse>({
    queryKey: ["naf-analytics", startDate, endDate, granularity, aggregation],
    queryFn: () =>
      analyticsApi.fetchNafAnalytics({
        startDate,
        endDate,
        granularity,
        aggregation,
      }),
  });

  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
      }
    },
    [onUnauthorized],
  );

  if (error) {
    handleError(error);
  }

  const applyPreset = (days: number) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    setStartDate(formatDate(start));
    setEndDate(formatDate(end));
  };

  const selectedItem = useMemo(() => {
    if (!data || !selectedItemId) return null;
    return data.items.find((item) => item.id === selectedItemId) ?? null;
  }, [data, selectedItemId]);

  // Prepare data for the time series chart
  const timeSeriesData = useMemo(() => {
    const source = selectedItem ? selectedItem.timeSeries : [];
    return source.map((point) => ({
      period: point.period,
      totalFetched: point.totalFetched,
      nonDiffusible: point.nonDiffusible,
      insufficientInfo: point.insufficientInfo,
      googleFound: point.googleFound,
      googleNotFound: point.googleNotFound,
      listingRecent: point.listingRecent,
      listingRecentMissingContact: point.listingRecentMissingContact,
      linkedinFound: point.linkedinFound,
      alertsCreated: point.alertsCreated,
    }));
  }, [selectedItem]);

  // Prepare data for the categories/NAF breakdown bar chart
  const breakdownData = useMemo(() => {
    if (!data) return [];
    return data.items
      .map((item) => ({
        id: item.id,
        name: item.name,
        code: item.code,
        totalFetched: item.totals.totalFetched,
        googleFound: item.totals.googleFound,
        linkedinFound: item.totals.linkedinFound,
        ...computeProportions(item.totals),
      }))
      .sort((a, b) => b.totalFetched - a.totalFetched)
      .slice(0, 15);
  }, [data]);

  const globalProportions = useMemo(() => {
    if (!data) return null;
    return computeProportions(data.globalTotals);
  }, [data]);

  const creationSeriesData = useMemo(() => {
    if (!data) return [];
    return data.creationSeries.map((point) => ({
      period: point.period,
      count: point.count,
    }));
  }, [data]);

  const selectedCreationSeriesData = useMemo(() => {
    if (!selectedItem) return [];
    return selectedItem.creationSeries.map((point) => ({
      period: point.period,
      count: point.count,
    }));
  }, [selectedItem]);

  return (
    <section className="section">
      <header className="section-header">
        <div>
          <h1>Statistiques par NAF</h1>
          <p className="muted">
            Analysez les proportions de conversion depuis l'API SIRENE vers Google, LinkedIn et alertes.
          </p>
        </div>
        <div className="section-actions">
          <button type="button" className="ghost" onClick={() => refetch()} disabled={isLoading}>
            Rafraîchir
          </button>
        </div>
      </header>

      {/* Filtres */}
      <div className="card">
        <header className="card-header">
          <h2>Filtres</h2>
        </header>
        <div className="analytics-filters">
          <div className="filter-group">
            <label>Période</label>
            <div className="date-range-inputs">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
              <span>à</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <div className="date-presets">
              {DATE_RANGE_PRESETS.map((preset) => (
                <button
                  key={preset.days}
                  type="button"
                  className="ghost small"
                  onClick={() => applyPreset(preset.days)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <label>Granularité</label>
            <select
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as NafAnalyticsGranularity)}
            >
              {GRANULARITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label>Agrégation</label>
            <select
              value={aggregation}
              onChange={(e) => {
                setAggregation(e.target.value as NafAnalyticsAggregation);
                setSelectedItemId(null);
              }}
            >
              {AGGREGATION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {isLoading && <p className="loading-indicator">Chargement...</p>}
      {error && <p className="error">Erreur lors du chargement des données.</p>}

      {data && (
        <>
          {/* Global Summary */}
          <div className="card">
            <header className="card-header">
              <h2>Résumé global</h2>
              <span className="muted">
                Du {data.startDate} au {data.endDate}
              </span>
            </header>
            <div className="analytics-summary-grid">
              <div className="summary-stat">
                <span className="stat-value">{formatNumber(data.globalTotals.totalFetched)}</span>
                <span className="stat-label">Établissements récupérés</span>
              </div>
              <div className="summary-stat">
                <span className="stat-value">{formatNumber(data.globalTotals.insufficientInfo)}</span>
                <span className="stat-label">Infos insuffisantes</span>
                {globalProportions && (
                  <span className="stat-pct muted">({globalProportions.insufficientPct}%)</span>
                )}
              </div>
              <div className="summary-stat">
                <span className="stat-value">{formatNumber(data.globalTotals.googleFound)}</span>
                <span className="stat-label">Google trouvés</span>
                {globalProportions && (
                  <span className="stat-pct muted">({globalProportions.googleFoundPct}% des cherchables)</span>
                )}
              </div>
              <div className="summary-stat">
                <span className="stat-value">{formatNumber(data.globalTotals.listingRecent)}</span>
                <span className="stat-label">Création récente</span>
                {globalProportions && (
                  <span className="stat-pct muted">({globalProportions.listingRecentPct}% des Google)</span>
                )}
              </div>
              <div className="summary-stat">
                <span className="stat-value">{formatNumber(data.globalTotals.linkedinFound)}</span>
                <span className="stat-label">LinkedIn trouvés</span>
                {globalProportions && (
                  <span className="stat-pct muted">({globalProportions.linkedinFoundPct}%)</span>
                )}
              </div>
              <div className="summary-stat">
                <span className="stat-value">{formatNumber(data.globalTotals.alertsCreated)}</span>
                <span className="stat-label">Alertes générées</span>
                {globalProportions && (
                  <span className="stat-pct muted">({globalProportions.alertsPct}%)</span>
                )}
              </div>
              <div className="summary-stat">
                <span className="stat-value">{formatNumber(data.globalTotals.websiteWithWebsite)}</span>
                <span className="stat-label">Fiches Google avec site</span>
                {globalProportions && (
                  <span className="stat-pct muted">({globalProportions.googleWithWebsitePct}% des Google)</span>
                )}
              </div>
              <div className="summary-stat">
                <span className="stat-value">{formatNumber(data.globalTotals.websiteScraped)}</span>
                <span className="stat-label">Sites scrapés</span>
                {globalProportions && (
                  <span className="stat-pct muted">({globalProportions.websiteScrapedPct}% des sites)</span>
                )}
              </div>
            </div>
          </div>

          {/* Breakdown chart */}
          <div className="card">
            <header className="card-header">
              <h2>
                Répartition par {aggregation === "category" ? "catégorie" : "sous-catégorie"}
              </h2>
              <span className="muted">Cliquez sur une barre pour voir le détail temporel</span>
            </header>
            {breakdownData.length > 0 ? (
              <div className="chart-wrapper">
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart
                    data={breakdownData}
                    layout="vertical"
                    margin={{ top: 20, right: 30, left: 150, bottom: 5 }}
                  >
                    <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" horizontal={true} vertical={false} />
                    <XAxis type="number" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 11, fill: "#475467" }}
                      width={140}
                    />
                    <Tooltip
                      content={<ProportionsTooltip />}
                      cursor={{ fill: "rgba(148, 163, 184, 0.08)" }}
                    />
                    <Legend />
                    <Bar
                      dataKey="totalFetched"
                      name="Total récupérés"
                      stackId="a"
                      fill="#64748b"
                      onClick={(data) => setSelectedItemId(data.id)}
                      style={{ cursor: "pointer" }}
                    >
                      {breakdownData.map((entry) => (
                        <Cell
                          key={entry.id}
                          fill={selectedItemId === entry.id ? "#475569" : "#64748b"}
                        />
                      ))}
                    </Bar>
                    <Bar
                      dataKey="googleFound"
                      name="Google trouvés"
                      stackId="b"
                      fill="#22c55e"
                      onClick={(data) => setSelectedItemId(data.id)}
                      style={{ cursor: "pointer" }}
                    />
                    <Bar
                      dataKey="linkedinFound"
                      name="LinkedIn trouvés"
                      stackId="c"
                      fill="#6366f1"
                      onClick={(data) => setSelectedItemId(data.id)}
                      style={{ cursor: "pointer" }}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="muted">Aucune donnée disponible.</p>
            )}
          </div>

          {/* Creation date chart */}
          <div className="card">
            <header className="card-header">
              <h2>Créations d'établissements (date de création)</h2>
              <span className="muted">Granularité : {GRANULARITY_OPTIONS.find((opt) => opt.value === granularity)?.label}</span>
            </header>
            {creationSeriesData.length > 0 ? (
              <div className="chart-wrapper">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={creationSeriesData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                    <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                    <XAxis dataKey="period" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "#475467" }} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} allowDecimals={false} />
                    <Tooltip content={<ProportionsTooltip />} />
                    <Legend />
                    <Bar dataKey="count" name="Créations" fill="#0ea5e9" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="muted">Aucune donnée disponible.</p>
            )}
          </div>

          {/* Time series for selected item */}
          {selectedItem && (
            <div className="card">
              <header className="card-header">
                <h2>
                  Évolution : {selectedItem.name}
                  {selectedItem.code && <span className="muted"> ({selectedItem.code})</span>}
                </h2>
                <button
                  type="button"
                  className="ghost small"
                  onClick={() => setSelectedItemId(null)}
                >
                  Fermer
                </button>
              </header>

              {/* Summary for selected item */}
              <div className="analytics-summary-grid small">
                <div className="summary-stat">
                  <span className="stat-value">{formatNumber(selectedItem.totals.totalFetched)}</span>
                  <span className="stat-label">Récupérés</span>
                </div>
                <div className="summary-stat">
                  <span className="stat-value">{formatNumber(selectedItem.totals.googleFound)}</span>
                  <span className="stat-label">Google</span>
                  <span className="stat-pct muted">({computeProportions(selectedItem.totals).googleFoundPct}%)</span>
                </div>
                <div className="summary-stat">
                  <span className="stat-value">{formatNumber(selectedItem.totals.listingRecent)}</span>
                  <span className="stat-label">Récent</span>
                </div>
                <div className="summary-stat">
                  <span className="stat-value">{formatNumber(selectedItem.totals.linkedinFound)}</span>
                  <span className="stat-label">LinkedIn</span>
                </div>
              </div>

              {timeSeriesData.length > 0 ? (
                <div className="chart-wrapper">
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={timeSeriesData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                      <defs>
                        <linearGradient id="colorFetched" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.8} />
                          <stop offset="95%" stopColor="#94a3b8" stopOpacity={0.1} />
                        </linearGradient>
                        <linearGradient id="colorGoogle" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#16a34a" stopOpacity={0.8} />
                          <stop offset="95%" stopColor="#16a34a" stopOpacity={0.1} />
                        </linearGradient>
                        <linearGradient id="colorLinkedin" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.8} />
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0.1} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                      <XAxis
                        dataKey="period"
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 11, fill: "#475467" }}
                      />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 12, fill: "#475467" }}
                        allowDecimals={false}
                      />
                      <Tooltip content={<ProportionsTooltip />} />
                      <Legend />
                      <Area
                        type="linear"
                        dataKey="totalFetched"
                        name="Récupérés"
                        stroke="#64748b"
                        fill="url(#colorFetched)"
                      />
                      <Area
                        type="linear"
                        dataKey="googleFound"
                        name="Google"
                        stroke="#16a34a"
                        fill="url(#colorGoogle)"
                      />
                      <Area
                        type="linear"
                        dataKey="linkedinFound"
                        name="LinkedIn"
                        stroke="#6366f1"
                        fill="url(#colorLinkedin)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="muted">Aucune donnée temporelle disponible.</p>
              )}

              {selectedCreationSeriesData.length > 0 ? (
                <div className="chart-wrapper" style={{ marginTop: 24 }}>
                  <h3 className="muted">Créations d'établissements (date de création)</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={selectedCreationSeriesData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                      <XAxis
                        dataKey="period"
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 11, fill: "#475467" }}
                      />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 12, fill: "#475467" }}
                        allowDecimals={false}
                      />
                      <Tooltip content={<ProportionsTooltip />} />
                      <Legend />
                      <Bar dataKey="count" name="Créations" fill="#0ea5e9" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : null}
            </div>
          )}

          {/* Detailed table */}
          <div className="card">
            <header className="card-header">
              <h2>Détail des proportions</h2>
            </header>
            <div className="table-container">
              <table className="data-table analytics-table">
                <thead>
                  <tr>
                    <th>Nom</th>
                    <th>Code</th>
                    <th className="num">Récupérés</th>
                    <th className="num">% EI</th>
                    <th className="num">Insuff.</th>
                    <th className="num">Google</th>
                    <th className="num">Récent</th>
                    <th className="num">Sans contact</th>
                    <th className="num">LinkedIn</th>
                    <th className="num">Dirigeants ND</th>
                    <th className="num">Google avec site</th>
                    <th className="num">Sites scrapés</th>
                    <th className="num">Scrape avec infos</th>
                    <th className="num">Alertes</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items
                    .sort((a, b) => b.totals.totalFetched - a.totals.totalFetched)
                    .map((item) => {
                      const pct = computeProportions(item.totals);
                      const individualPct = item.totals.totalFetched > 0
                        ? Math.round((item.totals.individualCount / item.totals.totalFetched) * 100)
                        : 0;
                      const nonDiffusibleDirectorsPct = item.totals.linkedinTotalDirectors > 0
                        ? Math.round((item.totals.linkedinSkippedNd / item.totals.linkedinTotalDirectors) * 100)
                        : 0;
                      return (
                        <tr
                          key={item.id}
                          className={selectedItemId === item.id ? "selected" : ""}
                          onClick={() => setSelectedItemId(item.id)}
                          style={{ cursor: "pointer" }}
                        >
                          <td>{item.name}</td>
                          <td className="code">{item.code}</td>
                          <td className="num">{formatNumber(item.totals.totalFetched)}</td>
                          <td className="num">
                            {formatNumber(item.totals.individualCount)}
                            <span className="pct muted"> ({individualPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.insufficientInfo)}
                            <span className="pct muted"> ({pct.insufficientPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.googleFound)}
                            <span className="pct muted"> ({pct.googleFoundPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.listingRecent)}
                            <span className="pct muted"> ({pct.listingRecentPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.listingRecentMissingContact)}
                            <span className="pct muted"> ({pct.listingRecentMissingContactPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.linkedinFound)}
                            <span className="pct muted"> ({pct.linkedinFoundPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.linkedinSkippedNd)}
                            <span className="pct muted"> ({nonDiffusibleDirectorsPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.websiteWithWebsite)}
                            <span className="pct muted"> ({pct.googleWithWebsitePct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.websiteScraped)}
                            <span className="pct muted"> ({pct.websiteScrapedPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.websiteScrapedWithInfo)}
                            <span className="pct muted"> ({pct.websiteScrapedWithInfoPct}%)</span>
                          </td>
                          <td className="num">
                            {formatNumber(item.totals.alertsCreated)}
                            <span className="pct muted"> ({pct.alertsPct}%)</span>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  );
};

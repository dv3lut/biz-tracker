import {
  ResponsiveContainer,
  ComposedChart,
  Bar as RechartsBar,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  BarChart as RechartsBarChart,
  Cell,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import { DashboardMetrics } from "../types";
import { formatDateTime, formatNumber } from "../utils/format";

type DashboardInsightsProps = {
  metrics?: DashboardMetrics;
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
  isRefreshing: boolean;
  days: number;
  onSelectDay?: (isoDate: string) => void;
  selectedDay?: string | null;
};

type TooltipEntry = NonNullable<TooltipProps<ValueType, NameType>["payload"]>[number];

const shortDate = (value: string): string => {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
  }).format(date);
};

const pluralizeRuns = (value: number): string => {
  if (value === 0) {
    return "0 run";
  }
  return value === 1 ? "1 run" : `${value} runs`;
};

export const DashboardInsights = ({
  metrics,
  isLoading,
  error,
  onRefresh,
  isRefreshing,
  days,
  onSelectDay,
  selectedDay,
}: DashboardInsightsProps) => {
  const windowSize = Math.min(days, 30);

  const runOutcomeSeries = metrics ? metrics.dailyRunOutcomes.slice(-windowSize) : [];
  const apiVolumeSeries = metrics ? metrics.dailyApiCalls.slice(-windowSize) : [];
  const alertSeries = metrics ? metrics.dailyAlerts.slice(-windowSize) : [];
  const googleStatusSeries = metrics ? metrics.dailyGoogleStatuses.slice(-windowSize) : [];

  const runOutcomeChartData = runOutcomeSeries.map((item) => ({
    key: item.date,
    label: shortDate(item.date),
    created: item.createdRecords,
    updated: item.updatedRecords,
  }));

  const apiActivityChartData = apiVolumeSeries.map((item) => ({
    key: item.date,
    label: shortDate(item.date),
    apiCalls: item.value,
    googleApiCalls: item.googleApiCallCount,
    runCount: item.runCount,
  }));

  const alertsChartData = alertSeries.map((item) => ({
    key: item.date,
    label: shortDate(item.date),
    sent: item.sent,
    pending: Math.max(item.created - item.sent, 0),
  }));

  const googleStatusChartData = googleStatusSeries.map((item) => ({
    key: item.date,
    label: shortDate(item.date),
    immediate: item.immediateMatches,
    late: item.lateMatches,
    notFound: item.notFound,
    insufficient: item.insufficient,
    pending: item.pending,
    other: item.other,
  }));

  const hasRunOutcomeData = runOutcomeChartData.some((item) => item.created > 0 || item.updated > 0);
  const hasApiData = apiActivityChartData.some((item) => item.apiCalls > 0 || item.googleApiCalls > 0);
  const hasAlertsData = alertsChartData.some((item) => item.sent > 0 || item.pending > 0);
  const hasGoogleStatusData = googleStatusChartData.some(
    (item) => item.immediate + item.late + item.notFound + item.insufficient + item.pending + item.other > 0,
  );

  const handleChartDayClick = (
    event: { activePayload?: Array<{ payload?: { key?: string } }> } | undefined,
  ) => {
    if (!onSelectDay) {
      return;
    }
    const payload = event?.activePayload?.[0]?.payload;
    if (payload && typeof payload.key === "string") {
      onSelectDay(payload.key);
    }
  };

  const makeLineDot =
    (stroke: string) =>
    ({
      cx,
      cy,
      payload,
    }: {
      cx?: number;
      cy?: number;
      payload?: { key?: string };
    }) => {
      if (typeof cx !== "number" || typeof cy !== "number" || !payload) {
        return <g />;
      }
      const isSelected = selectedDay ? payload.key === selectedDay : false;
      const radius = isSelected ? 5 : 3;
      return (
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          stroke={stroke}
          strokeWidth={isSelected ? 2 : 1.5}
          fill="#ffffff"
        />
      );
    };

  const runLineDot = makeLineDot("#0f766e");
  const apiLineDot = makeLineDot("#f97316");

  const renderRunOutcomesTooltip = ({
    active,
    label,
    payload,
  }: TooltipProps<ValueType, NameType>) => {
    if (!active || !payload || payload.length === 0 || typeof label !== "string") {
      return null;
    }
    const total = payload.reduce((acc, entry) => acc + Number(entry.value ?? 0), 0);
    return (
      <div className="chart-tooltip">
        <span className="chart-tooltip-label">{label}</span>
        <span className="chart-tooltip-row">
          <span>Total mouvements</span>
          <strong>{formatNumber(total)}</strong>
        </span>
        {payload.map((entry: TooltipEntry) => (
          <span key={`${label}-${String(entry.name)}`} className="chart-tooltip-row">
            <span>{entry.name}</span>
            <strong>{formatNumber(Number(entry.value ?? 0))}</strong>
          </span>
        ))}
      </div>
    );
  };

  const renderApiTooltip = ({ active, label, payload }: TooltipProps<ValueType, NameType>) => {
    if (!active || !payload || payload.length === 0 || typeof label !== "string") {
      return null;
    }
    const raw = (payload[0]?.payload ?? {}) as { runCount?: number };
    return (
      <div className="chart-tooltip">
        <span className="chart-tooltip-label">{label}</span>
        {payload.map((entry: TooltipEntry) => (
          <span key={`${label}-${String(entry.name)}`} className="chart-tooltip-row">
            <span>{entry.name}</span>
            <strong>{formatNumber(Number(entry.value ?? 0))}</strong>
          </span>
        ))}
        {typeof raw.runCount === "number" ? (
          <span className="chart-tooltip-row">
            <span>Runs termines</span>
            <strong>{formatNumber(raw.runCount)}</strong>
          </span>
        ) : null}
      </div>
    );
  };

  const renderAlertsTooltip = ({ active, label, payload }: TooltipProps<ValueType, NameType>) => {
    if (!active || !payload || payload.length === 0 || typeof label !== "string") {
      return null;
    }
    const sent = payload.find((item: TooltipEntry) => item.name === "Envoyees");
    const pending = payload.find((item: TooltipEntry) => item.name === "En attente");
    const total = Number(sent?.value ?? 0) + Number(pending?.value ?? 0);
    return (
      <div className="chart-tooltip">
        <span className="chart-tooltip-label">{label}</span>
        <span className="chart-tooltip-row">
          <span>Total creees</span>
          <strong>{formatNumber(total)}</strong>
        </span>
        {sent ? (
          <span className="chart-tooltip-row">
            <span>Envoyees</span>
            <strong>{formatNumber(Number(sent.value ?? 0))}</strong>
          </span>
        ) : null}
        {pending ? (
          <span className="chart-tooltip-row">
            <span>En attente</span>
            <strong>{formatNumber(Number(pending.value ?? 0))}</strong>
          </span>
        ) : null}
      </div>
    );
  };

  const renderGoogleStatusTooltip = ({
    active,
    label,
    payload,
  }: TooltipProps<ValueType, NameType>) => {
    if (!active || !payload || payload.length === 0 || typeof label !== "string") {
      return null;
    }
    const total = payload.reduce((acc, entry) => acc + Number(entry.value ?? 0), 0);
    return (
      <div className="chart-tooltip">
        <span className="chart-tooltip-label">{label}</span>
        <span className="chart-tooltip-row">
          <span>Total suivis</span>
          <strong>{formatNumber(total)}</strong>
        </span>
        {payload.map((entry: TooltipEntry) => (
          <span key={`${label}-${String(entry.name)}`} className="chart-tooltip-row">
            <span>{entry.name}</span>
            <strong>{formatNumber(Number(entry.value ?? 0))}</strong>
          </span>
        ))}
      </div>
    );
  };

  const isSelectedDay = (key: string) => (selectedDay ? selectedDay === key : false);

  return (
    <section className="card">
      <header className="card-header">
        <div>
          <h2>Monitoring quotidien</h2>
          <p className="muted">Vue synthetique des synchronisations, des appels API et des alertes recents.</p>
        </div>
        <div className="card-actions">
          <button type="button" className="ghost" onClick={onRefresh} disabled={isLoading}>
            Rafraichir
          </button>
        </div>
      </header>

      {isRefreshing && !isLoading ? <p className="refresh-indicator">Actualisation en cours…</p> : null}
      {isLoading ? <p>Chargement...</p> : null}
      {error ? <p className="error">{error.message}</p> : null}

      {metrics && !isLoading && !error ? (
        <>
          <div className="insight-grid">
            <article className="insight-card">
              <h3>Dernier run</h3>
              {metrics.latestRun && metrics.latestRunBreakdown ? (
                <>
                  <p className="muted small">Demarre le {formatDateTime(metrics.latestRun.startedAt)}</p>
                  <ul className="metric-list">
                    <li>
                      <strong>{formatNumber(metrics.latestRunBreakdown.createdRecords)}</strong> nouveaux etablissements
                    </li>
                    <li>
                      <strong>{formatNumber(metrics.latestRunBreakdown.updatedRecords)}</strong> etablissements mis a jour
                    </li>
                    <li>
                      <strong>{formatNumber(metrics.latestRunBreakdown.apiCallCount)}</strong> appels API
                    </li>
                    <li>
                      <strong>{formatNumber(metrics.latestRunBreakdown.googleApiCallCount)}</strong> appels Google
                    </li>
                    <li>
                      <strong>{formatNumber(metrics.latestRunBreakdown.alertsSent)}</strong> alertes envoyees
                    </li>
                  </ul>
                </>
              ) : (
                <p className="muted">Aucun run termine a ce jour.</p>
              )}
            </article>

            <article className="insight-card">
              <h3>Google (dernier run)</h3>
              {metrics.latestRunBreakdown ? (
                <ul className="metric-list">
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.googleApiCallCount)}</strong> appels API
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.googleFound)}</strong> fiches trouvees (immediate)
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.googleFoundLate)}</strong> fiches trouvees (rattrapage)
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.googleNotFound)}</strong> sans resultat
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.googleInsufficient)}</strong> identite insuffisante
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.googlePending)}</strong> en attente
                  </li>
                  {metrics.latestRunBreakdown.googleOther > 0 ? (
                    <li>
                      <strong>{formatNumber(metrics.latestRunBreakdown.googleOther)}</strong> autres statuts
                    </li>
                  ) : null}
                </ul>
              ) : (
                <p className="muted">Aucun enrichissement recense.</p>
              )}
            </article>

            <article className="insight-card">
              <h3>Anciennete des fiches (dernier run)</h3>
              {metrics.latestRunBreakdown ? (
                <ul className="metric-list">
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.listingRecent)}</strong> creation recente
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.listingRecentMissingContact)}</strong> creation recente sans contact
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.listingNotRecent)}</strong> creation ancienne
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.latestRunBreakdown.listingUnknown)}</strong> statut inconnu
                  </li>
                </ul>
              ) : (
                <p className="muted">Aucun enrichissement recense.</p>
              )}
            </article>

            <article className="insight-card">
              <h3>Google (global)</h3>
              <ul className="metric-list">
                <li>
                  <strong>{formatNumber(metrics.googleStatusBreakdown.found)}</strong> fiches trouvees
                </li>
                <li>
                  <strong>{formatNumber(metrics.googleStatusBreakdown.notFound)}</strong> sans resultat
                </li>
                <li>
                  <strong>{formatNumber(metrics.googleStatusBreakdown.insufficient)}</strong> identite insuffisante
                </li>
                <li>
                  <strong>{formatNumber(metrics.googleStatusBreakdown.pending)}</strong> en attente
                </li>
                {metrics.googleStatusBreakdown.other > 0 ? (
                  <li>
                    <strong>{formatNumber(metrics.googleStatusBreakdown.other)}</strong> autres statuts
                  </li>
                ) : null}
              </ul>
            </article>

            <article className="insight-card">
              <h3>Anciennete des fiches Google</h3>
              {metrics.listingAgeBreakdown ? (
                <ul className="metric-list">
                  <li>
                    <strong>{formatNumber(metrics.listingAgeBreakdown.recentCreation)}</strong> creation recente
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.listingAgeBreakdown.recentCreationMissingContact)}</strong> creation recente sans contact
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.listingAgeBreakdown.notRecentCreation)}</strong> creation ancienne
                  </li>
                  <li>
                    <strong>{formatNumber(metrics.listingAgeBreakdown.unknown)}</strong> statut inconnu
                  </li>
                </ul>
              ) : (
                <p className="muted">Aucune donnee disponible.</p>
              )}
            </article>

            <article className="insight-card">
              <h3>Statuts etablissements</h3>
              {Object.keys(metrics.establishmentStatusBreakdown).length > 0 ? (
                <ul className="metric-list">
                  {Object.entries(metrics.establishmentStatusBreakdown)
                    .sort((a, b) => a[0].localeCompare(b[0]))
                    .map(([status, count]) => (
                      <li key={status}>
                        <strong>{formatNumber(count)}</strong> statut {status}
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="muted">Aucun etablissements enregistre.</p>
              )}
            </article>

          </div>

          <div className="charts-grid">
            <article className="insight-card">
              <h3>Creations et mises a jour quotidiennes</h3>
              {hasRunOutcomeData ? (
                <div className="chart-wrapper">
                  <ResponsiveContainer width="100%" height={240}>
                    <ComposedChart
                      data={runOutcomeChartData}
                      margin={{ top: 24, right: 16, left: 12, bottom: 12 }}
                      onClick={handleChartDayClick}
                    >
                      <defs>
                        <linearGradient id="runCreatedGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#2563eb" stopOpacity={0.9} />
                          <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.9} />
                        </linearGradient>
                        <linearGradient id="runCreatedGradientHighlight" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.95} />
                          <stop offset="100%" stopColor="#0284c7" stopOpacity={0.95} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} dy={6} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} allowDecimals={false} width={60} />
                      <Tooltip content={renderRunOutcomesTooltip} cursor={{ fill: "rgba(37, 99, 235, 0.08)" }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                      <RechartsBar dataKey="created" name="Creations" radius={[10, 10, 0, 0]} maxBarSize={48}>
                        {runOutcomeChartData.map((item) => (
                          <Cell
                            key={`created-${item.key}`}
                            fill={isSelectedDay(item.key) ? "url(#runCreatedGradientHighlight)" : "url(#runCreatedGradient)"}
                          />
                        ))}
                      </RechartsBar>
                      <Line
                        type="monotone"
                        dataKey="updated"
                        name="Mises a jour"
                        stroke="#0f766e"
                        strokeWidth={2}
                        dot={runLineDot}
                        activeDot={{ r: 6 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="muted">Pas encore de donnees.</p>
              )}
            </article>

            <article className="insight-card">
              <h3>Volume d'appels API</h3>
              {hasApiData ? (
                <div className="chart-wrapper">
                  <ResponsiveContainer width="100%" height={240}>
                    <ComposedChart
                      data={apiActivityChartData}
                      margin={{ top: 24, right: 16, left: 12, bottom: 12 }}
                      onClick={handleChartDayClick}
                    >
                      <defs>
                        <linearGradient id="apiVolumeGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#2563eb" stopOpacity={0.9} />
                          <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.9} />
                        </linearGradient>
                        <linearGradient id="apiVolumeGradientHighlight" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.95} />
                          <stop offset="100%" stopColor="#0284c7" stopOpacity={0.95} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} dy={6} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} allowDecimals={false} width={60} />
                      <Tooltip content={renderApiTooltip} cursor={{ fill: "rgba(37, 99, 235, 0.08)" }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                      <RechartsBar dataKey="apiCalls" name="Appels API (total)" radius={[10, 10, 0, 0]} maxBarSize={48}>
                        {apiActivityChartData.map((item) => (
                          <Cell
                            key={`api-${item.key}`}
                            fill={isSelectedDay(item.key) ? "url(#apiVolumeGradientHighlight)" : "url(#apiVolumeGradient)"}
                          />
                        ))}
                      </RechartsBar>
                      <Line
                        type="monotone"
                        dataKey="googleApiCalls"
                        name="Appels Google"
                        stroke="#f97316"
                        strokeWidth={2}
                        dot={apiLineDot}
                        activeDot={{ r: 6 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                  <div className="chart-footnotes">
                    {apiActivityChartData.map((item) => (
                      <span key={`${item.key}-footnote`} className="chart-footnote">
                        {pluralizeRuns(item.runCount)}
                      </span>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="muted">Pas encore de donnees.</p>
              )}
            </article>
          </div>

          <div className="charts-grid">
            <article className="insight-card">
              <h3>Resultats Google par run</h3>
              {hasGoogleStatusData ? (
                <div className="chart-wrapper">
                  <ResponsiveContainer width="100%" height={240}>
                    <RechartsBarChart
                      data={googleStatusChartData}
                      margin={{ top: 24, right: 16, left: 12, bottom: 12 }}
                      onClick={handleChartDayClick}
                    >
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} dy={6} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} allowDecimals={false} width={60} />
                      <Tooltip content={renderGoogleStatusTooltip} cursor={{ fill: "rgba(59, 130, 246, 0.08)" }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                      <RechartsBar dataKey="immediate" stackId="google" name="Trouvees immediates" radius={[10, 10, 0, 0]}>
                        {googleStatusChartData.map((item) => (
                          <Cell key={`google-immediate-${item.key}`} fill={isSelectedDay(item.key) ? "#0284c7" : "#0ea5e9"} />
                        ))}
                      </RechartsBar>
                      <RechartsBar dataKey="late" stackId="google" name="Trouvees (rattrapage)">
                        {googleStatusChartData.map((item) => (
                          <Cell key={`google-late-${item.key}`} fill={isSelectedDay(item.key) ? "#4f46e5" : "#6366f1"} />
                        ))}
                      </RechartsBar>
                      <RechartsBar dataKey="notFound" stackId="google" name="Sans resultat">
                        {googleStatusChartData.map((item) => (
                          <Cell key={`google-not-found-${item.key}`} fill={isSelectedDay(item.key) ? "#ea580c" : "#f97316"} />
                        ))}
                      </RechartsBar>
                      <RechartsBar dataKey="insufficient" stackId="google" name="Identite insuffisante">
                        {googleStatusChartData.map((item) => (
                          <Cell key={`google-insufficient-${item.key}`} fill={isSelectedDay(item.key) ? "#dc2626" : "#ef4444"} />
                        ))}
                      </RechartsBar>
                      <RechartsBar dataKey="pending" stackId="google" name="En attente">
                        {googleStatusChartData.map((item) => (
                          <Cell key={`google-pending-${item.key}`} fill={isSelectedDay(item.key) ? "#ca8a04" : "#eab308"} />
                        ))}
                      </RechartsBar>
                      <RechartsBar dataKey="other" stackId="google" name="Autres statuts">
                        {googleStatusChartData.map((item) => (
                          <Cell key={`google-other-${item.key}`} fill={isSelectedDay(item.key) ? "#64748b" : "#94a3b8"} />
                        ))}
                      </RechartsBar>
                    </RechartsBarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="muted">Pas encore de donnees.</p>
              )}
            </article>

            <article className="insight-card">
              <h3>Alertes quotidiennes</h3>
              {hasAlertsData ? (
                <div className="chart-wrapper">
                  <ResponsiveContainer width="100%" height={240}>
                    <RechartsBarChart
                      data={alertsChartData}
                      margin={{ top: 24, right: 16, left: 12, bottom: 12 }}
                      onClick={handleChartDayClick}
                    >
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} dy={6} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} allowDecimals={false} width={60} />
                      <Tooltip content={renderAlertsTooltip} cursor={{ fill: "rgba(14, 165, 233, 0.08)" }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                      <RechartsBar dataKey="sent" stackId="alerts" name="Envoyees" radius={[10, 10, 0, 0]}>
                        {alertsChartData.map((item) => (
                          <Cell key={`alerts-sent-${item.key}`} fill={isSelectedDay(item.key) ? "#0f766e" : "#14b8a6"} />
                        ))}
                      </RechartsBar>
                      <RechartsBar dataKey="pending" stackId="alerts" name="En attente">
                        {alertsChartData.map((item) => (
                          <Cell key={`alerts-pending-${item.key}`} fill={isSelectedDay(item.key) ? "#ea580c" : "#f97316"} />
                        ))}
                      </RechartsBar>
                    </RechartsBarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="muted">Aucune alerte recense sur la periode.</p>
              )}
            </article>
          </div>
        </>
      ) : null}
    </section>
  );
};

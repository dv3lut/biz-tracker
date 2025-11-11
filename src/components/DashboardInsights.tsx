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
import { BarChart } from "./BarChart";

type DashboardInsightsProps = {
  metrics?: DashboardMetrics;
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
  isRefreshing: boolean;
  days: number;
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

export const DashboardInsights = ({ metrics, isLoading, error, onRefresh, isRefreshing, days }: DashboardInsightsProps) => {
  const recentNewBusinesses = metrics ? metrics.dailyNewBusinesses.slice(-Math.min(days, 14)) : [];
  const recentApiCalls = metrics ? metrics.dailyApiCalls.slice(-Math.min(days, 14)) : [];
  const recentAlerts = metrics ? metrics.dailyAlerts.slice(-Math.min(days, 14)) : [];

  const newBusinessChartData = recentNewBusinesses.map((item) => ({
    key: item.date,
    label: shortDate(item.date),
    value: item.value,
  }));

  const apiActivityChartData = recentApiCalls.map((item) => ({
    key: item.date,
    label: shortDate(item.date),
    value: item.value,
    runCount: item.runCount,
  }));

  const alertsChartData = recentAlerts.map((item) => ({
    key: item.date,
    label: shortDate(item.date),
    sent: item.sent,
    pending: Math.max(item.created - item.sent, 0),
  }));

  const hasAlertsData = alertsChartData.some((item) => item.sent > 0 || item.pending > 0);

  const renderApiTooltip = ({ active, label, payload }: TooltipProps<ValueType, NameType>) => {
    if (!active || !payload || payload.length === 0 || typeof label !== "string") {
      return null;
    }
    return (
      <div className="chart-tooltip">
        <span className="chart-tooltip-label">{label}</span>
  {payload.map((entry: TooltipEntry) => (
          <span key={`${label}-${String(entry.name)}`} className="chart-tooltip-row">
            <span>{entry.name}</span>
            <strong>{formatNumber(Number(entry.value ?? 0))}</strong>
          </span>
        ))}
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
              <h3>Nouveaux etablissements par jour</h3>
              <BarChart data={newBusinessChartData} highlightLast />
            </article>

            <article className="insight-card">
              <h3>Appels API et runs</h3>
              {apiActivityChartData.length > 0 ? (
                <div className="chart-wrapper">
                  <ResponsiveContainer width="100%" height={220}>
                    <ComposedChart data={apiActivityChartData} margin={{ top: 24, right: 16, left: 12, bottom: 12 }}>
                      <defs>
                        <linearGradient id="apiBarGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#2563eb" stopOpacity={0.9} />
                          <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.9} />
                        </linearGradient>
                        <linearGradient id="apiBarGradientHighlight" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.95} />
                          <stop offset="100%" stopColor="#0284c7" stopOpacity={0.95} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} dy={6} />
                      <YAxis
                        yAxisId="api"
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 12, fill: "#475467" }}
                        allowDecimals={false}
                        width={60}
                      />
                      <YAxis
                        yAxisId="runs"
                        orientation="right"
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 12, fill: "#475467" }}
                        allowDecimals={false}
                        width={50}
                      />
                      <Tooltip content={renderApiTooltip} cursor={{ fill: "rgba(37, 99, 235, 0.08)" }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                      <RechartsBar yAxisId="api" dataKey="value" name="Appels API" radius={[10, 10, 0, 0]} maxBarSize={42}>
                        {apiActivityChartData.map((item, index) => (
                          <Cell
                            key={item.key}
                            fill={index === apiActivityChartData.length - 1 ? "url(#apiBarGradientHighlight)" : "url(#apiBarGradient)"}
                          />
                        ))}
                      </RechartsBar>
                      <Line yAxisId="runs" type="monotone" dataKey="runCount" name="Runs termines" stroke="#0f766e" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
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

          <article className="insight-card">
            <h3>Alertes quotidiennes</h3>
            {hasAlertsData ? (
              <div className="chart-wrapper">
                <ResponsiveContainer width="100%" height={220}>
                  <RechartsBarChart data={alertsChartData} margin={{ top: 24, right: 16, left: 12, bottom: 12 }}>
                    <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} dy={6} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} allowDecimals={false} width={60} />
                    <Tooltip content={renderAlertsTooltip} cursor={{ fill: "rgba(14, 165, 233, 0.08)" }} />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    <RechartsBar dataKey="sent" stackId="alerts" name="Envoyees" radius={[10, 10, 0, 0]} fill="#14b8a6" />
                    <RechartsBar dataKey="pending" stackId="alerts" name="En attente" radius={[0, 0, 0, 0]} fill="#f97316" />
                  </RechartsBarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="muted">Aucune alerte recense sur la periode.</p>
            )}
          </article>
        </>
      ) : null}
    </section>
  );
};

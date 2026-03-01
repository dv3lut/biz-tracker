import {
  Bar as RechartsBar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import { formatNumber } from "../../utils/format";
import { ApiActivityChartEntry } from "./useDashboardChartData";

type ApiVolumeChartCardProps = {
  data: ApiActivityChartEntry[];
  hasData: boolean;
  selectedDay?: string | null;
  onSelectDay?: (isoDate: string) => void;
};

type TooltipEntry = NonNullable<TooltipProps<ValueType, NameType>["payload"]>[number];

type ActivePayload = { payload?: { key?: string } };

type LineDotProps = {
  cx?: number;
  cy?: number;
  payload?: { key?: string };
};

const pluralizeRuns = (value: number): string => {
  if (value === 0) {
    return "0 run";
  }
  return value === 1 ? "1 run" : `${value} runs`;
};

const handleChartDayClick = (event: { activePayload?: ActivePayload[] } | undefined, onSelectDay?: (isoDate: string) => void) => {
  if (!onSelectDay) {
    return;
  }
  const payload = event?.activePayload?.[0]?.payload;
  if (payload && typeof payload.key === "string") {
    onSelectDay(payload.key);
  }
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

export const ApiVolumeChartCard = ({ data, hasData, onSelectDay, selectedDay }: ApiVolumeChartCardProps) => {
  const isSelectedDay = (key: string) => (selectedDay ? selectedDay === key : false);

  const makeLineDot = (stroke: string) => ({ cx, cy, payload }: LineDotProps) => {
    if (typeof cx !== "number" || typeof cy !== "number" || !payload) {
      return <g />;
    }
    const isSelected = payload.key ? isSelectedDay(payload.key) : false;
    const radius = isSelected ? 5 : 3;
    return <circle cx={cx} cy={cy} r={radius} stroke={stroke} strokeWidth={isSelected ? 2 : 1.5} fill="#ffffff" />;
  };

  const apiLineDot = makeLineDot("#f97316");

  return (
    <article className="insight-card">
      <h3>Volume d'appels API</h3>
      {hasData ? (
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart
              data={data}
              margin={{ top: 24, right: 16, left: 12, bottom: 12 }}
              onClick={(event) => handleChartDayClick(event, onSelectDay)}
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
                {data.map((item) => (
                  <Cell
                    key={`api-${item.key}`}
                    fill={isSelectedDay(item.key) ? "url(#apiVolumeGradientHighlight)" : "url(#apiVolumeGradient)"}
                  />
                ))}
              </RechartsBar>
              <Line type="monotone" dataKey="googleApiCalls" name="Appels Google" stroke="#f97316" strokeWidth={2} dot={apiLineDot} activeDot={{ r: 6 }} />
            </ComposedChart>
          </ResponsiveContainer>
          <div className="chart-footnotes">
            {data.map((item) => (
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
  );
};

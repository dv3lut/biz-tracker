import {
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Bar as RechartsBar,
} from "recharts";
import type { TooltipProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import { formatNumber } from "../../utils/format";
import { RunOutcomeChartEntry } from "./useDashboardChartData";

type RunOutcomesChartCardProps = {
  data: RunOutcomeChartEntry[];
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

const handleChartDayClick = (event: { activePayload?: ActivePayload[] } | undefined, onSelectDay?: (isoDate: string) => void) => {
  if (!onSelectDay) {
    return;
  }
  const payload = event?.activePayload?.[0]?.payload;
  if (payload && typeof payload.key === "string") {
    onSelectDay(payload.key);
  }
};

const renderRunOutcomesTooltip = ({ active, label, payload }: TooltipProps<ValueType, NameType>) => {
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

export const RunOutcomesChartCard = ({ data, hasData, onSelectDay, selectedDay }: RunOutcomesChartCardProps) => {
  const isSelectedDay = (key: string) => (selectedDay ? selectedDay === key : false);

  const makeLineDot = (stroke: string) => ({ cx, cy, payload }: LineDotProps) => {
    if (typeof cx !== "number" || typeof cy !== "number" || !payload) {
      return <g />;
    }
    const isSelected = payload.key ? isSelectedDay(payload.key) : false;
    const radius = isSelected ? 5 : 3;
    return <circle cx={cx} cy={cy} r={radius} stroke={stroke} strokeWidth={isSelected ? 2 : 1.5} fill="#ffffff" />;
  };

  const runLineDot = makeLineDot("#0f766e");

  return (
    <article className="insight-card">
      <h3>Creations et mises a jour quotidiennes</h3>
      {hasData ? (
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart
              data={data}
              margin={{ top: 24, right: 16, left: 12, bottom: 12 }}
              onClick={(event) => handleChartDayClick(event, onSelectDay)}
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
                {data.map((item) => (
                  <Cell
                    key={`created-${item.key}`}
                    fill={isSelectedDay(item.key) ? "url(#runCreatedGradientHighlight)" : "url(#runCreatedGradient)"}
                  />
                ))}
              </RechartsBar>
              <Line type="monotone" dataKey="updated" name="Mises a jour" stroke="#0f766e" strokeWidth={2} dot={runLineDot} activeDot={{ r: 6 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="muted">Pas encore de donnees.</p>
      )}
    </article>
  );
};

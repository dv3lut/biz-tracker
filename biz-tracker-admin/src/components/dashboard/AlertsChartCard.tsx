import {
  Bar as RechartsBar,
  BarChart as RechartsBarChart,
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

import { formatNumber } from "../../utils/format";
import { AlertsChartEntry } from "./useDashboardChartData";

type AlertsChartCardProps = {
  data: AlertsChartEntry[];
  hasData: boolean;
  selectedDay?: string | null;
  onSelectDay?: (isoDate: string) => void;
};

type TooltipEntry = NonNullable<TooltipProps<ValueType, NameType>["payload"]>[number];

type ActivePayload = { payload?: { key?: string } };

const handleChartDayClick = (event: { activePayload?: ActivePayload[] } | undefined, onSelectDay?: (isoDate: string) => void) => {
  if (!onSelectDay) {
    return;
  }
  const payload = event?.activePayload?.[0]?.payload;
  if (payload && typeof payload.key === "string") {
    onSelectDay(payload.key);
  }
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

export const AlertsChartCard = ({ data, hasData, onSelectDay, selectedDay }: AlertsChartCardProps) => {
  const isSelectedDay = (key: string) => (selectedDay ? selectedDay === key : false);

  return (
    <article className="insight-card">
      <h3>Alertes quotidiennes</h3>
      {hasData ? (
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={240}>
            <RechartsBarChart
              data={data}
              margin={{ top: 24, right: 16, left: 12, bottom: 12 }}
              onClick={(event) => handleChartDayClick(event, onSelectDay)}
            >
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} dy={6} />
              <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} allowDecimals={false} width={60} />
              <Tooltip content={renderAlertsTooltip} cursor={{ fill: "rgba(14, 165, 233, 0.08)" }} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
              <RechartsBar dataKey="sent" stackId="alerts" name="Envoyees" radius={[10, 10, 0, 0]}>
                {data.map((item) => (
                  <Cell key={`alerts-sent-${item.key}`} fill={isSelectedDay(item.key) ? "#0f766e" : "#14b8a6"} />
                ))}
              </RechartsBar>
              <RechartsBar dataKey="pending" stackId="alerts" name="En attente">
                {data.map((item) => (
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
  );
};

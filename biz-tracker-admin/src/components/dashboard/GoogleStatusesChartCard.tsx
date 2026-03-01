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
import { GoogleStatusChartEntry } from "./useDashboardChartData";

type GoogleStatusesChartCardProps = {
  data: GoogleStatusChartEntry[];
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

const renderGoogleStatusTooltip = ({ active, label, payload }: TooltipProps<ValueType, NameType>) => {
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

export const GoogleStatusesChartCard = ({ data, hasData, onSelectDay, selectedDay }: GoogleStatusesChartCardProps) => {
  const isSelectedDay = (key: string) => (selectedDay ? selectedDay === key : false);

  return (
    <article className="insight-card">
      <h3>Resultats Google par run</h3>
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
              <Tooltip content={renderGoogleStatusTooltip} cursor={{ fill: "rgba(59, 130, 246, 0.08)" }} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
              <RechartsBar dataKey="immediate" stackId="google" name="Trouvees immediates" radius={[10, 10, 0, 0]}>
                {data.map((item) => (
                  <Cell key={`google-immediate-${item.key}`} fill={isSelectedDay(item.key) ? "#0284c7" : "#0ea5e9"} />
                ))}
              </RechartsBar>
              <RechartsBar dataKey="late" stackId="google" name="Trouvees (rattrapage)">
                {data.map((item) => (
                  <Cell key={`google-late-${item.key}`} fill={isSelectedDay(item.key) ? "#4f46e5" : "#6366f1"} />
                ))}
              </RechartsBar>
              <RechartsBar dataKey="notFound" stackId="google" name="Sans resultat">
                {data.map((item) => (
                  <Cell key={`google-not-found-${item.key}`} fill={isSelectedDay(item.key) ? "#ea580c" : "#f97316"} />
                ))}
              </RechartsBar>
              <RechartsBar dataKey="insufficient" stackId="google" name="Identite insuffisante">
                {data.map((item) => (
                  <Cell key={`google-insufficient-${item.key}`} fill={isSelectedDay(item.key) ? "#dc2626" : "#ef4444"} />
                ))}
              </RechartsBar>
              <RechartsBar dataKey="pending" stackId="google" name="En attente">
                {data.map((item) => (
                  <Cell key={`google-pending-${item.key}`} fill={isSelectedDay(item.key) ? "#ca8a04" : "#eab308"} />
                ))}
              </RechartsBar>
              <RechartsBar dataKey="other" stackId="google" name="Autres statuts">
                {data.map((item) => (
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
  );
};

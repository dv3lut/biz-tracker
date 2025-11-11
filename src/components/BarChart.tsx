import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { LabelProps, TooltipProps } from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";

import { formatNumber } from "../utils/format";

type BarChartDatum = {
  key: string;
  label: string;
  value: number;
  footnote?: string | null;
};

type BarChartProps = {
  data: BarChartDatum[];
  height?: number;
  highlightLast?: boolean;
};

const ValueLabel = ({ x, y, value }: LabelProps) => {
  if (typeof x !== "number" || typeof y !== "number" || typeof value !== "number") {
    return null;
  }
  return (
    <text x={x} y={y - 6} textAnchor="middle" fontSize={12} fontWeight={600} fill="#1e293b">
      {formatNumber(value)}
    </text>
  );
};

const ChartTooltip = ({ active, payload, label }: TooltipProps<ValueType, NameType>) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const [{ value, payload: datum }] = payload;
  return (
    <div className="chart-tooltip">
      <span className="chart-tooltip-label">{label}</span>
      <strong className="chart-tooltip-value">{formatNumber(Number(value))}</strong>
      {typeof datum?.footnote === "string" && datum.footnote.length > 0 ? (
        <span className="chart-tooltip-footnote">{datum.footnote}</span>
      ) : null}
    </div>
  );
};

export const BarChart = ({ data, height = 220, highlightLast = false }: BarChartProps) => {
  if (data.length === 0) {
    return <p className="muted">Pas encore de donnees.</p>;
  }

  return (
    <div className="chart-wrapper">
      <ResponsiveContainer width="100%" height={height}>
        <RechartsBarChart data={data} margin={{ top: 24, right: 12, left: 12, bottom: 8 }}>
          <defs>
            <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" stopOpacity={0.9} />
              <stop offset="100%" stopColor="#1d4ed8" stopOpacity={0.9} />
            </linearGradient>
            <linearGradient id="barGradientHighlight" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.95} />
              <stop offset="100%" stopColor="#0284c7" stopOpacity={0.95} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="4 4" vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} interval={0} angle={0} dy={6} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#475467" }} allowDecimals={false} width={60} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(37, 99, 235, 0.08)" }} />
          <Bar dataKey="value" radius={[10, 10, 0, 0]} maxBarSize={48} isAnimationActive>
            {data.map((item, index) => (
              <Cell
                key={item.key}
                fill={highlightLast && index === data.length - 1 ? "url(#barGradientHighlight)" : "url(#barGradient)"}
              />
            ))}
            <LabelList dataKey="value" content={<ValueLabel />} />
          </Bar>
        </RechartsBarChart>
      </ResponsiveContainer>

      {data.some((item) => item.footnote) ? (
        <div className="chart-footnotes">
          {data.map((item) => (
            <span key={`${item.key}-footnote`} className="chart-footnote">
              {item.footnote ?? ""}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

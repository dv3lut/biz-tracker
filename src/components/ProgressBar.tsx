import { type ReactNode } from "react";

import { formatPercent } from "../utils/format";

const clamp = (value: number): number => {
  if (Number.isNaN(value)) {
    return 0;
  }
  return Math.min(Math.max(value, 0), 1);
};

interface ProgressBarProps {
  label: string;
  value: number | null | undefined;
  tone?: "primary" | "success";
  details?: ReactNode;
}

export const ProgressBar = ({ label, value, tone = "primary", details }: ProgressBarProps) => {
  const normalizedValue = typeof value === "number" ? clamp(value) : null;
  const percentLabel = normalizedValue !== null ? formatPercent(normalizedValue) : "—";
  const trackClass = normalizedValue === null ? "progress-bar-track progress-bar-track--indeterminate" : "progress-bar-track";
  const ariaValueNow = normalizedValue !== null ? Math.round(normalizedValue * 100) : undefined;

  return (
    <div className={`progress-bar progress-bar--${tone}`}>
      <div className="progress-bar-header">
        <span className="progress-bar-label">{label}</span>
        <span className="progress-bar-value">{percentLabel}</span>
      </div>
      <div
        className={trackClass}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={ariaValueNow}
        aria-label={label}
      >
        {normalizedValue !== null ? <div className="progress-bar-fill" style={{ width: `${normalizedValue * 100}%` }} /> : null}
      </div>
      {details ? <div className="progress-bar-details">{details}</div> : null}
    </div>
  );
};

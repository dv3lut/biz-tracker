const locale = "fr-FR";

export const formatDate = (value: string | null | undefined): string => {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
  }).format(date);
};

export const formatDateTime = (value: string | null | undefined): string => {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(date);
};

export const formatNumber = (value: number | null | undefined): string => {
  if (value === null || value === undefined) {
    return "—";
  }
  return new Intl.NumberFormat(locale).format(value);
};

export const formatPercent = (value: number | null | undefined): string => {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${Math.round(value * 100)} %`;
};

export const formatDuration = (value: number | null | undefined): string => {
  if (value === null || value === undefined) {
    return "—";
  }
  if (value < 60) {
    return `${value.toFixed(1)} s`;
  }
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  if (minutes < 60) {
    return `${minutes} min ${seconds} s`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours} h ${remainingMinutes} min`;
};

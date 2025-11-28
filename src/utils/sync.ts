import { SyncMode } from "../types";

export const describeSyncMode = (mode: SyncMode): string => {
  switch (mode) {
    case "sirene_only":
      return "Sirene uniquement";
    case "google_pending":
      return "Google — nouveaux uniquement";
    case "google_refresh":
      return "Google — rafraîchir toutes les fiches";
    case "day_replay":
      return "Rejouer une journée";
    case "full":
    default:
      return "Complet";
  }
};

export const syncModeSupportsSirene = (mode: SyncMode): boolean => {
  return mode === "full" || mode === "sirene_only" || mode === "day_replay";
};

export const syncModeIsGoogleOnly = (mode: SyncMode): boolean => {
  return mode === "google_pending" || mode === "google_refresh";
};

export const syncModeSendsAlerts = (mode: SyncMode): boolean => {
  return mode === "full" || mode === "google_pending";
};

export const syncModeRequiresReplayDate = (mode: SyncMode): boolean => {
  return mode === "day_replay";
};

export const MAX_TARGET_NAF_CODES = 25;

export const normalizeNafCode = (raw: string | null | undefined): string | null => {
  if (!raw) {
    return null;
  }
  const cleaned = raw.replace(/[.\s]/g, "").toUpperCase();
  if (/^\d{4}$/.test(cleaned)) {
    return cleaned;
  }
  if (/^\d{4}[A-Z]$/.test(cleaned)) {
    return cleaned;
  }
  return null;
};

export const sanitizeNafCodes = (values: Array<string | null | undefined>): string[] => {
  const normalized: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const code = normalizeNafCode(value);
    if (!code || seen.has(code)) {
      continue;
    }
    seen.add(code);
    normalized.push(code);
    if (normalized.length >= MAX_TARGET_NAF_CODES) {
      break;
    }
  }
  return normalized;
};

export const parseNafInput = (value: string): string[] => {
  if (!value) {
    return [];
  }
  return value
    .split(/[;,\s]+/)
    .map((item) => normalizeNafCode(item))
    .filter((code): code is string => Boolean(code));
};

export const formatNafCodesPreview = (codes?: string[] | null, limit = 5): string => {
  if (!codes || codes.length === 0) {
    return "—";
  }
  if (codes.length <= limit) {
    return codes.join(", ");
  }
  const remaining = codes.length - limit;
  return `${codes.slice(0, limit).join(", ")} +${remaining}`;
};

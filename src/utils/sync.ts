import { DayReplayReference, SyncMode } from "../types";

export const describeSyncMode = (mode: SyncMode): string => {
  switch (mode) {
    case "sirene_only":
      return "Sirene uniquement";
    case "google_pending":
      return "Google — nouveaux uniquement";
    case "google_refresh":
      return "Google — relancer sur tous";
    case "linkedin_pending":
      return "LinkedIn — nouveaux uniquement";
    case "linkedin_refresh":
      return "LinkedIn";
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

export const syncModeIsLinkedInOnly = (mode: SyncMode): boolean => {
  return mode === "linkedin_pending" || mode === "linkedin_refresh";
};

export const syncModeIsEnrichmentOnly = (mode: SyncMode): boolean => {
  return syncModeIsGoogleOnly(mode) || syncModeIsLinkedInOnly(mode);
};

export const syncModeSendsAlerts = (mode: SyncMode): boolean => {
  return mode === "full" || mode === "google_pending" || mode === "linkedin_pending";
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

const formatNormalized = (code: string): string => {
  if (code.length < 4) {
    return code;
  }
  const digits = code.slice(0, 4);
  const suffix = code.slice(4);
  const withDot = `${digits.slice(0, 2)}.${digits.slice(2)}`;
  return suffix ? `${withDot}${suffix}` : withDot;
};

export const denormalizeNafCode = (code: string): string => {
  return formatNormalized(code);
};

export const canonicalizeNafCode = (value: string | null | undefined): string | null => {
  const normalized = normalizeNafCode(value);
  if (!normalized) {
    return null;
  }
  return formatNormalized(normalized);
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
  const canonical = codes
    .map((code) => canonicalizeNafCode(code) ?? code)
    .filter((value): value is string => Boolean(value));
  if (canonical.length === 0) {
    return "—";
  }
  if (canonical.length <= limit) {
    return canonical.join(", ");
  }
  const remaining = canonical.length - limit;
  return `${canonical.slice(0, limit).join(", ")} +${remaining}`;
};

export const describeDayReplayReference = (reference: DayReplayReference): string => {
  switch (reference) {
    case "insertion_date":
      return "Insertion dans Business tracker";
    case "creation_date":
    default:
      return "Date de création Sirene";
  }
};

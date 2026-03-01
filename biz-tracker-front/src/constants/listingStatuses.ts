import type { ListingStatus } from "../types";

export interface ListingStatusOption {
  value: ListingStatus;
  label: string;
  description: string;
}

export const LISTING_STATUS_OPTIONS: readonly ListingStatusOption[] = [
  {
    value: "recent_creation",
    label: "Création récente",
    description: "Fiches détectées en même temps que la création Sirene.",
  },
  {
    value: "recent_creation_missing_contact",
    label: "Création récente (contact manquant)",
    description: "Fiches récentes sans canal de contact exploitable.",
  },
  {
    value: "not_recent_creation",
    label: "Création ancienne",
    description: "Fiches correspondant à des établissements plus anciens / reprises.",
  },
];

export const LISTING_STATUS_LABELS: Record<ListingStatus, string> = LISTING_STATUS_OPTIONS.reduce(
  (acc, option) => {
    acc[option.value] = option.label;
    return acc;
  },
  {} as Record<ListingStatus, string>,
);

export const DEFAULT_LISTING_STATUSES: ListingStatus[] = LISTING_STATUS_OPTIONS.map((option) => option.value);

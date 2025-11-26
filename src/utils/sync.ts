import { SyncMode } from "../types";

export const describeSyncMode = (mode: SyncMode): string => {
  switch (mode) {
    case "sirene_only":
      return "Sirene uniquement";
    case "google_pending":
      return "Google — nouveaux uniquement";
    case "google_refresh":
      return "Google — rafraîchir toutes les fiches";
    case "full":
    default:
      return "Complet";
  }
};

export const syncModeSupportsSirene = (mode: SyncMode): boolean => {
  return mode === "full" || mode === "sirene_only";
};

export const syncModeIsGoogleOnly = (mode: SyncMode): boolean => {
  return mode === "google_pending" || mode === "google_refresh";
};

export const syncModeSendsAlerts = (mode: SyncMode): boolean => {
  return mode === "full" || mode === "google_pending";
};

import type { Director, EstablishmentDetail } from "../types";

type MinimalEstablishment = Pick<EstablishmentDetail, "name" | "enseigne1" | "legalUnitName">;

type MinimalDirector = Pick<Director, "firstNames" | "lastName" | "typeDirigeant">;

const normalizeValue = (value: string | null | undefined): string => {
  if (!value) {
    return "";
  }
  return value.trim();
};

const resolveCompanyName = (establishment: MinimalEstablishment): string => {
  return (
    normalizeValue(establishment.name) ||
    normalizeValue(establishment.enseigne1) ||
    normalizeValue(establishment.legalUnitName)
  );
};

const resolveFirstName = (firstNames: string | null | undefined): string => {
  const normalized = normalizeValue(firstNames);
  if (!normalized) {
    return "";
  }
  return normalized.split(" ")[0] ?? "";
};

export const buildLinkedInSearchQuery = (
  establishment: MinimalEstablishment,
  director: MinimalDirector,
): string => {
  if (director.typeDirigeant !== "personne physique") {
    return "";
  }
  const firstName = resolveFirstName(director.firstNames);
  const lastName = normalizeValue(director.lastName);
  if (!firstName || !lastName) {
    return "";
  }
  const company = resolveCompanyName(establishment);
  return [firstName, lastName, company].filter(Boolean).join(" ");
};

export const openLinkedInSearchForDirector = (
  establishment: MinimalEstablishment,
  director: MinimalDirector,
): boolean => {
  const query = buildLinkedInSearchQuery(establishment, director);
  if (!query) {
    return false;
  }
  const url = `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(query)}`;
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
};

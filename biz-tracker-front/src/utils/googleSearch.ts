type MinimalEstablishmentForSearch = {
  name?: string | null;
  libelleCommune?: string | null;
  libelleCommuneEtranger?: string | null;
  codePostal?: string | null;
};

const PLACEHOLDER_TOKENS = new Set(["ND"]);

const sanitizePlaceholder = (value: string | null | undefined): string => {
  if (!value) {
    return "";
  }
  const cleaned = value.trim();
  if (!cleaned) {
    return "";
  }
  const normalized = cleaned
    .toUpperCase()
    .split("")
    .filter((ch) => /[A-Z0-9]/.test(ch))
    .join("");
  if (!normalized) {
    return "";
  }
  if (PLACEHOLDER_TOKENS.has(normalized)) {
    return "";
  }

  // Pattern utilisé côté backend: NDNDND...
  if (normalized.length % 2 === 0) {
    let onlyNdPairs = true;
    for (let i = 0; i < normalized.length; i += 2) {
      if (normalized.slice(i, i + 2) !== "ND") {
        onlyNdPairs = false;
        break;
      }
    }
    if (onlyNdPairs) {
      return "";
    }
  }
  return cleaned;
};

export const buildGoogleSearchQuery = (establishment: MinimalEstablishmentForSearch): string => {
  const commune = sanitizePlaceholder(establishment.libelleCommune);
  const communeEtranger = sanitizePlaceholder(establishment.libelleCommuneEtranger);

  const parts = [
    sanitizePlaceholder(establishment.name),
    commune || communeEtranger,
    sanitizePlaceholder(establishment.codePostal),
  ].filter(Boolean);

  return parts.join(" ");
};

export const openGoogleSearchForEstablishment = (establishment: MinimalEstablishmentForSearch): boolean => {
  const query = buildGoogleSearchQuery(establishment);
  if (!query) {
    return false;
  }
  const url = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
};

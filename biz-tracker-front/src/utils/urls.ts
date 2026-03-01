export const buildAnnuaireEtablissementUrl = (siret: string): string => {
  const normalized = siret.replace(/\s+/g, "");
  return `https://annuaire-entreprises.data.gouv.fr/etablissement/${encodeURIComponent(normalized)}`;
};

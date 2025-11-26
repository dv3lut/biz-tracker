import { Establishment, EstablishmentDetail } from "../types";
import { request } from "./http";

export interface EstablishmentResponse {
  siret: string;
  siren: string;
  name: string;
  naf_code: string | null;
  naf_libelle: string | null;
  etat_administratif: string | null;
  code_postal: string | null;
  libelle_commune: string | null;
  date_creation: string | null;
  date_debut_activite: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  updated_at: string | null;
  created_run_id: string | null;
  last_run_id: string | null;
  google_place_id: string | null;
  google_place_url: string | null;
  google_match_confidence: number | null;
  google_last_checked_at: string | null;
  google_last_found_at: string | null;
  google_listing_origin_at: string | null;
  google_listing_origin_source: string | null;
  google_listing_age_status: string | null;
  google_check_status: string;
  google_contact_phone: string | null;
  google_contact_email: string | null;
  google_contact_website: string | null;
  is_sole_proprietorship: boolean;
}

export interface EstablishmentDetailResponse extends EstablishmentResponse {
  nic: string | null;
  denomination_unite_legale: string | null;
  denomination_usuelle_unite_legale: string | null;
  denomination_usuelle_etablissement: string | null;
  enseigne1: string | null;
  enseigne2: string | null;
  enseigne3: string | null;
  categorie_juridique: string | null;
  categorie_entreprise: string | null;
  tranche_effectifs: string | null;
  annee_effectifs: number | null;
  nom_usage: string | null;
  nom: string | null;
  prenom1: string | null;
  prenom2: string | null;
  prenom3: string | null;
  prenom4: string | null;
  prenom_usuel: string | null;
  pseudonyme: string | null;
  sexe: string | null;
  date_dernier_traitement_etablissement: string | null;
  date_dernier_traitement_unite_legale: string | null;
  complement_adresse: string | null;
  numero_voie: string | null;
  indice_repetition: string | null;
  type_voie: string | null;
  libelle_voie: string | null;
  distribution_speciale: string | null;
  libelle_commune_etranger: string | null;
  code_commune: string | null;
  code_cedex: string | null;
  libelle_cedex: string | null;
  code_pays: string | null;
  libelle_pays: string | null;
}

export const mapEstablishment = (payload: EstablishmentResponse): Establishment => ({
  siret: payload.siret,
  siren: payload.siren,
  name: payload.name,
  nafCode: payload.naf_code,
  nafLibelle: payload.naf_libelle,
  etatAdministratif: payload.etat_administratif,
  codePostal: payload.code_postal,
  libelleCommune: payload.libelle_commune,
  dateCreation: payload.date_creation,
  dateDebutActivite: payload.date_debut_activite,
  firstSeenAt: payload.first_seen_at,
  lastSeenAt: payload.last_seen_at,
  updatedAt: payload.updated_at,
  createdRunId: payload.created_run_id,
  lastRunId: payload.last_run_id,
  googlePlaceId: payload.google_place_id,
  googlePlaceUrl: payload.google_place_url,
  googleMatchConfidence: payload.google_match_confidence,
  googleLastCheckedAt: payload.google_last_checked_at,
  googleLastFoundAt: payload.google_last_found_at,
  googleListingOriginAt: payload.google_listing_origin_at,
  googleListingOriginSource: payload.google_listing_origin_source,
  googleListingAgeStatus: payload.google_listing_age_status,
  googleCheckStatus: payload.google_check_status,
  googleContactPhone: payload.google_contact_phone,
  googleContactEmail: payload.google_contact_email,
  googleContactWebsite: payload.google_contact_website,
  isSoleProprietorship: payload.is_sole_proprietorship,
});

export const mapEstablishmentDetail = (payload: EstablishmentDetailResponse): EstablishmentDetail => ({
  ...mapEstablishment(payload),
  nic: payload.nic,
  denominationUniteLegale: payload.denomination_unite_legale,
  denominationUsuelleUniteLegale: payload.denomination_usuelle_unite_legale,
  denominationUsuelleEtablissement: payload.denomination_usuelle_etablissement,
  enseigne1: payload.enseigne1,
  enseigne2: payload.enseigne2,
  enseigne3: payload.enseigne3,
  categorieJuridique: payload.categorie_juridique,
  categorieEntreprise: payload.categorie_entreprise,
  trancheEffectifs: payload.tranche_effectifs,
  anneeEffectifs: payload.annee_effectifs,
  nomUsage: payload.nom_usage,
  nom: payload.nom,
  prenom1: payload.prenom1,
  prenom2: payload.prenom2,
  prenom3: payload.prenom3,
  prenom4: payload.prenom4,
  prenomUsuel: payload.prenom_usuel,
  pseudonyme: payload.pseudonyme,
  sexe: payload.sexe,
  dateDernierTraitementEtablissement: payload.date_dernier_traitement_etablissement,
  dateDernierTraitementUniteLegale: payload.date_dernier_traitement_unite_legale,
  complementAdresse: payload.complement_adresse,
  numeroVoie: payload.numero_voie,
  indiceRepetition: payload.indice_repetition,
  typeVoie: payload.type_voie,
  libelleVoie: payload.libelle_voie,
  distributionSpeciale: payload.distribution_speciale,
  libelleCommuneEtranger: payload.libelle_commune_etranger,
  codeCommune: payload.code_commune,
  codeCedex: payload.code_cedex,
  libelleCedex: payload.libelle_cedex,
  codePays: payload.code_pays,
  libellePays: payload.libelle_pays,
});

interface ListEstablishmentsParams {
  limit?: number;
  offset?: number;
  q?: string;
  isIndividual?: boolean;
}

export const establishmentsApi = {
  async fetchMany(params: ListEstablishmentsParams = {}): Promise<Establishment[]> {
    const query = new URLSearchParams();
    if (typeof params.limit === "number") {
      query.set("limit", String(params.limit));
    }
    if (typeof params.offset === "number") {
      query.set("offset", String(params.offset));
    }
    if (params.q) {
      query.set("q", params.q);
    }
    if (typeof params.isIndividual === "boolean") {
      query.set("is_individual", String(params.isIndividual));
    }
    const queryString = query.toString();
    const path = `/admin/establishments${queryString ? `?${queryString}` : ""}`;
    const { data } = await request<EstablishmentResponse[]>(path);
    return data.map(mapEstablishment);
  },

  async fetchOne(siret: string): Promise<EstablishmentDetail> {
    const { data } = await request<EstablishmentDetailResponse>(
      `/admin/establishments/${encodeURIComponent(siret)}`,
    );
    return mapEstablishmentDetail(data);
  },

  async deleteOne(siret: string): Promise<void> {
    await request(`/admin/establishments/${encodeURIComponent(siret)}`, {
      method: "DELETE",
    });
  },
};

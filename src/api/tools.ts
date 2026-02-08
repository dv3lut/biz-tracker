import { request } from "./http";
import type {
  AnnuaireDebugResult,
  SireneNewBusiness,
  SireneNewBusinessDirector,
  SireneNewBusinessesResult,
} from "../types";

export interface SireneNewBusinessesPayload {
  startDate: string;
  endDate?: string;
  nafCodes: string[];
  limit?: number;
  departmentCodes?: string[];
  enrichAnnuaire?: boolean;
}

interface SireneNewBusinessDirectorResponse {
  type_dirigeant: string;
  first_names: string | null;
  last_name: string | null;
  quality: string | null;
  birth_month: number | null;
  birth_year: number | null;
  siren: string | null;
  denomination: string | null;
  nationality: string | null;
}

interface SireneNewBusinessResponse {
  siret: string;
  siren: string | null;
  nic: string | null;
  name: string | null;
  naf_code: string | null;
  naf_label: string | null;
  date_creation: string | null;
  is_individual: boolean;
  leader_name: string | null;
  denomination_unite_legale: string | null;
  denomination_usuelle_unite_legale: string | null;
  denomination_usuelle_etablissement: string | null;
  enseigne1: string | null;
  enseigne2: string | null;
  enseigne3: string | null;
  complement_adresse: string | null;
  numero_voie: string | null;
  indice_repetition: string | null;
  type_voie: string | null;
  libelle_voie: string | null;
  code_postal: string | null;
  libelle_commune: string | null;
  libelle_commune_etranger: string | null;
  legal_unit_name: string | null;
  directors: SireneNewBusinessDirectorResponse[];
}

interface SireneNewBusinessesResponse {
  total: number;
  returned: number;
  establishments: SireneNewBusinessResponse[];
}

interface AnnuaireDebugResponse {
  siret: string;
  siren: string;
  success: boolean;
  status_code: number | null;
  duration_ms: number | null;
  error: string | null;
  payload: Record<string, unknown> | null;
}

const mapSireneDirector = (payload: SireneNewBusinessDirectorResponse): SireneNewBusinessDirector => ({
  typeDirigeant: payload.type_dirigeant,
  firstNames: payload.first_names ?? null,
  lastName: payload.last_name ?? null,
  quality: payload.quality ?? null,
  birthMonth: payload.birth_month ?? null,
  birthYear: payload.birth_year ?? null,
  siren: payload.siren ?? null,
  denomination: payload.denomination ?? null,
  nationality: payload.nationality ?? null,
});

const mapSireneNewBusiness = (payload: SireneNewBusinessResponse): SireneNewBusiness => ({
  siret: payload.siret,
  siren: payload.siren ?? null,
  nic: payload.nic ?? null,
  name: payload.name ?? null,
  nafCode: payload.naf_code ?? null,
  nafLabel: payload.naf_label ?? null,
  dateCreation: payload.date_creation ?? null,
  isIndividual: payload.is_individual,
  leaderName: payload.leader_name ?? null,
  denominationUniteLegale: payload.denomination_unite_legale ?? null,
  denominationUsuelleUniteLegale: payload.denomination_usuelle_unite_legale ?? null,
  denominationUsuelleEtablissement: payload.denomination_usuelle_etablissement ?? null,
  enseigne1: payload.enseigne1 ?? null,
  enseigne2: payload.enseigne2 ?? null,
  enseigne3: payload.enseigne3 ?? null,
  complementAdresse: payload.complement_adresse ?? null,
  numeroVoie: payload.numero_voie ?? null,
  indiceRepetition: payload.indice_repetition ?? null,
  typeVoie: payload.type_voie ?? null,
  libelleVoie: payload.libelle_voie ?? null,
  codePostal: payload.code_postal ?? null,
  libelleCommune: payload.libelle_commune ?? null,
  libelleCommuneEtranger: payload.libelle_commune_etranger ?? null,
  legalUnitName: payload.legal_unit_name ?? null,
  directors: (payload.directors ?? []).map(mapSireneDirector),
});

export const toolsApi = {
  fetchSireneNewBusinesses: async (
    payload: SireneNewBusinessesPayload,
  ): Promise<SireneNewBusinessesResult> => {
    const response = await request<SireneNewBusinessesResponse>("/admin/tools/sirene/new-establishments", {
      method: "POST",
      body: JSON.stringify({
        start_date: payload.startDate,
        end_date: payload.endDate ?? null,
        naf_codes: payload.nafCodes,
        limit: payload.limit ?? 100,
        department_codes: payload.departmentCodes && payload.departmentCodes.length > 0 ? payload.departmentCodes : null,
        enrich_annuaire: payload.enrichAnnuaire ?? false,
      }),
    });

    return {
      total: response.data.total,
      returned: response.data.returned,
      establishments: response.data.establishments.map(mapSireneNewBusiness),
    };
  },
  fetchAnnuaireDebug: async (siret: string): Promise<AnnuaireDebugResult> => {
    const response = await request<AnnuaireDebugResponse>(
      `/admin/tools/annuaire/debug?siret=${encodeURIComponent(siret)}`,
    );

    return {
      siret: response.data.siret,
      siren: response.data.siren,
      success: response.data.success,
      statusCode: response.data.status_code,
      durationMs: response.data.duration_ms,
      error: response.data.error ?? null,
      payload: response.data.payload ?? null,
    };
  },
};

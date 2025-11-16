import {
  SyncRequestPayload,
  SyncRun,
  SyncState,
  Alert,
  StatsSummary,
  Establishment,
  EstablishmentDetail,
  EmailTestPayload,
  EmailTestResult,
  GoogleCheckResult,
  DashboardMetrics,
  DailyMetricPoint,
  DailyApiMetricPoint,
  DailyAlertMetricPoint,
  DailyGoogleStatusPoint,
  DailyRunOutcomePoint,
  GoogleStatusBreakdown,
  DashboardRunBreakdown,
  RunSummary,
  RunSummaryEstablishment,
  RunSummaryUpdatedEstablishment,
} from "../types";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

interface SyncRunResponse {
  id: string;
  scope_key: string;
  run_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  api_call_count: number;
  google_api_call_count: number;
  fetched_records: number;
  created_records: number;
  updated_records: number;
  google_queue_count: number;
  google_eligible_count: number;
  google_matched_count: number;
  google_pending_count: number;
  google_immediate_matched_count: number;
  google_late_matched_count: number;
  last_cursor: string | null;
  query_checksum: string | null;
  resumed_from_run_id: string | null;
  notes: string | null;
  total_expected_records: number | null;
  progress: number | null;
  estimated_remaining_seconds: number | null;
  estimated_completion_at: string | null;
  summary: RunSummaryResponse | null;
}

interface RunSummaryResponse {
  run: RunSummaryMetaResponse;
  stats: RunSummaryStatsResponse;
  samples: RunSummarySamplesResponse;
  email?: RunEmailSummaryResponse | null;
}

interface RunSummaryMetaResponse {
  id: string;
  scope_key: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number;
  page_count: number;
}

interface RunSummaryStatsResponse {
  fetched_records: number;
  created_records: number;
  updated_records: number;
  api_call_count: number;
  google: RunSummaryGoogleStatsResponse;
  alerts: RunSummaryAlertsStatsResponse;
}

interface RunSummaryGoogleStatsResponse {
  api_call_count: number;
  queue_count: number;
  eligible_count: number;
  matched_count: number;
  immediate_matches: number;
  late_matches: number;
  pending_count: number;
}

interface RunSummaryAlertsStatsResponse {
  created: number;
  sent: number;
}

interface RunSummarySamplesResponse {
  new_establishments?: RunSummaryEstablishmentResponse[];
  updated_establishments?: RunSummaryUpdatedEstablishmentResponse[];
  google_late_matches?: RunSummaryEstablishmentResponse[];
  google_immediate_matches?: RunSummaryEstablishmentResponse[];
}

interface RunSummaryEstablishmentResponse {
  siret: string;
  name: string | null;
  code_postal: string | null;
  libelle_commune: string | null;
  naf_code: string | null;
  google_status: string | null;
  google_place_url: string | null;
  google_place_id: string | null;
  created_run_id: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
}

interface RunSummaryUpdatedEstablishmentResponse extends RunSummaryEstablishmentResponse {
  changed_fields?: string[];
}

interface RunEmailSummaryResponse {
  sent: boolean;
  recipients?: string[];
  subject?: string | null;
  reason?: string | null;
}

interface SyncStateResponse {
  scope_key: string;
  last_successful_run_id: string | null;
  last_cursor: string | null;
  cursor_completed: boolean;
  last_synced_at: string | null;
  last_total: number | null;
  last_treated_max: string | null;
  query_checksum: string | null;
  updated_at: string;
}

interface AlertResponse {
  id: string;
  run_id: string;
  siret: string;
  recipients: string[];
  payload: Record<string, unknown>;
  created_at: string;
  sent_at: string | null;
}

interface StatsSummaryResponse {
  total_establishments: number;
  total_alerts: number;
  database_size_pretty?: string | null;
  last_run: SyncRunResponse | null;
  last_alert: AlertResponse | null;
}

interface DailyMetricPointResponse {
  date: string;
  value: number;
}

interface DailyApiMetricPointResponse extends DailyMetricPointResponse {
  run_count: number;
  google_api_call_count: number;
}

interface DailyAlertMetricPointResponse {
  date: string;
  created: number;
  sent: number;
}

interface DailyRunOutcomePointResponse {
  date: string;
  created_records: number;
  updated_records: number;
}

interface DailyGoogleStatusPointResponse {
  date: string;
  immediate_matches: number;
  late_matches: number;
  not_found: number;
  insufficient: number;
  pending: number;
  other: number;
}

interface GoogleStatusBreakdownResponse {
  found: number;
  not_found: number;
  insufficient: number;
  pending: number;
  other: number;
}

interface DashboardRunBreakdownResponse {
  run_id: string;
  started_at: string;
  created_records: number;
  updated_records: number;
  api_call_count: number;
  google_api_call_count: number;
  google_found: number;
  google_found_late: number;
  google_not_found: number;
  google_insufficient: number;
  google_pending: number;
  google_other: number;
  alerts_created: number;
  alerts_sent: number;
}

interface DashboardMetricsResponse {
  latest_run: SyncRunResponse | null;
  latest_run_breakdown: DashboardRunBreakdownResponse | null;
  daily_new_businesses: DailyMetricPointResponse[];
  daily_api_calls: DailyApiMetricPointResponse[];
  daily_alerts: DailyAlertMetricPointResponse[];
  daily_run_outcomes: DailyRunOutcomePointResponse[];
  daily_google_statuses: DailyGoogleStatusPointResponse[];
  google_status_breakdown: GoogleStatusBreakdownResponse;
  establishment_status_breakdown: Record<string, number>;
}

interface EstablishmentResponse {
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
  google_last_checked_at: string | null;
  google_last_found_at: string | null;
  google_check_status: string;
}

interface EstablishmentDetailResponse extends EstablishmentResponse {
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

interface ManualGoogleCheckResponse {
  found: boolean;
  email_sent: boolean;
  message: string;
  place_id: string | null;
  place_url: string | null;
  check_status: string;
  establishment: EstablishmentResponse;
}

interface EmailTestResponse {
  sent: boolean;
  provider: string;
  subject: string;
  recipients: string[];
}

export interface DeleteRunResponse {
  establishments_deleted: number;
  alerts_deleted: number;
  states_reset: number;
  runs_updated: number;
  sync_run_deleted: boolean;
}

interface RequestResult<T> {
  data: T;
  status: number;
}

const API_BASE_URL = import.meta.env.VITE_APP_API_BASE_URL ?? "http://localhost:8080";
const ADMIN_TOKEN_STORAGE_KEY = "admin-token";

const getSessionStorage = (): Storage | null => {
  if (typeof window === "undefined") {
    return null;
  }
  return window.sessionStorage;
};

export const getAdminToken = (): string | null => {
  return getSessionStorage()?.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? null;
};

export const setAdminToken = (token: string): void => {
  getSessionStorage()?.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
};

export const clearAdminToken = (): void => {
  getSessionStorage()?.removeItem(ADMIN_TOKEN_STORAGE_KEY);
};

const toRunSummaryEstablishment = (payload: RunSummaryEstablishmentResponse): RunSummaryEstablishment => ({
  siret: payload.siret,
  name: payload.name ?? null,
  codePostal: payload.code_postal ?? null,
  libelleCommune: payload.libelle_commune ?? null,
  nafCode: payload.naf_code ?? null,
  googleStatus: payload.google_status ?? null,
  googlePlaceUrl: payload.google_place_url ?? null,
  googlePlaceId: payload.google_place_id ?? null,
  createdRunId: payload.created_run_id ?? null,
  firstSeenAt: payload.first_seen_at ?? null,
  lastSeenAt: payload.last_seen_at ?? null,
});

const toRunSummaryUpdatedEstablishment = (
  payload: RunSummaryUpdatedEstablishmentResponse,
): RunSummaryUpdatedEstablishment => ({
  ...toRunSummaryEstablishment(payload),
  changedFields: payload.changed_fields ?? [],
});

const toRunSummary = (payload: RunSummaryResponse): RunSummary => ({
  run: {
    id: payload.run.id,
    scopeKey: payload.run.scope_key,
    status: payload.run.status,
    startedAt: payload.run.started_at,
    finishedAt: payload.run.finished_at,
    durationSeconds: payload.run.duration_seconds,
    pageCount: payload.run.page_count,
  },
  stats: {
    fetchedRecords: payload.stats.fetched_records,
    createdRecords: payload.stats.created_records,
    updatedRecords: payload.stats.updated_records,
    apiCallCount: payload.stats.api_call_count,
    google: {
      apiCallCount: payload.stats.google.api_call_count,
      queueCount: payload.stats.google.queue_count,
      eligibleCount: payload.stats.google.eligible_count,
      matchedCount: payload.stats.google.matched_count,
      immediateMatches: payload.stats.google.immediate_matches,
      lateMatches: payload.stats.google.late_matches,
      pendingCount: payload.stats.google.pending_count,
    },
    alerts: {
      created: payload.stats.alerts.created,
      sent: payload.stats.alerts.sent,
    },
  },
  samples: {
    newEstablishments: (payload.samples.new_establishments ?? []).map(toRunSummaryEstablishment),
    updatedEstablishments: (payload.samples.updated_establishments ?? []).map(toRunSummaryUpdatedEstablishment),
    googleLateMatches: (payload.samples.google_late_matches ?? []).map(toRunSummaryEstablishment),
    googleImmediateMatches: (payload.samples.google_immediate_matches ?? []).map(toRunSummaryEstablishment),
  },
  email: payload.email
    ? {
        sent: payload.email.sent,
        recipients: payload.email.recipients ?? [],
        subject: payload.email.subject ?? null,
        reason: payload.email.reason ?? null,
      }
    : undefined,
});

const toSyncRun = (payload: SyncRunResponse): SyncRun => ({
  id: payload.id,
  scopeKey: payload.scope_key,
  runType: payload.run_type,
  status: payload.status,
  startedAt: payload.started_at,
  finishedAt: payload.finished_at,
  apiCallCount: payload.api_call_count,
  googleApiCallCount: payload.google_api_call_count,
  fetchedRecords: payload.fetched_records,
  createdRecords: payload.created_records,
  updatedRecords: payload.updated_records,
  googleQueueCount: payload.google_queue_count,
  googleEligibleCount: payload.google_eligible_count,
  googleMatchedCount: payload.google_matched_count,
  googlePendingCount: payload.google_pending_count,
  googleImmediateMatchedCount: payload.google_immediate_matched_count,
  googleLateMatchedCount: payload.google_late_matched_count,
  lastCursor: payload.last_cursor,
  queryChecksum: payload.query_checksum,
  resumedFromRunId: payload.resumed_from_run_id,
  notes: payload.notes,
  totalExpectedRecords: payload.total_expected_records,
  progress: payload.progress,
  estimatedRemainingSeconds: payload.estimated_remaining_seconds,
  estimatedCompletionAt: payload.estimated_completion_at,
  summary: payload.summary ? toRunSummary(payload.summary) : null,
});

const toSyncState = (payload: SyncStateResponse): SyncState => ({
  scopeKey: payload.scope_key,
  lastSuccessfulRunId: payload.last_successful_run_id,
  lastCursor: payload.last_cursor,
  cursorCompleted: payload.cursor_completed,
  lastSyncedAt: payload.last_synced_at,
  lastTotal: payload.last_total,
  lastTreatedMax: payload.last_treated_max,
  queryChecksum: payload.query_checksum,
  updatedAt: payload.updated_at,
});

const toAlert = (payload: AlertResponse): Alert => ({
  id: payload.id,
  runId: payload.run_id,
  siret: payload.siret,
  recipients: payload.recipients,
  payload: payload.payload,
  createdAt: payload.created_at,
  sentAt: payload.sent_at,
});

const toStatsSummary = (payload: StatsSummaryResponse): StatsSummary => ({
  totalEstablishments: payload.total_establishments,
  totalAlerts: payload.total_alerts,
  databaseSizePretty: payload.database_size_pretty ?? null,
  lastRun: payload.last_run ? toSyncRun(payload.last_run) : null,
  lastAlert: payload.last_alert ? toAlert(payload.last_alert) : null,
});

const toDailyMetricPoint = (payload: DailyMetricPointResponse): DailyMetricPoint => ({
  date: payload.date,
  value: payload.value,
});

const toDailyApiMetricPoint = (payload: DailyApiMetricPointResponse): DailyApiMetricPoint => ({
  date: payload.date,
  value: payload.value,
  runCount: payload.run_count,
  googleApiCallCount: payload.google_api_call_count,
});

const toDailyAlertMetricPoint = (payload: DailyAlertMetricPointResponse): DailyAlertMetricPoint => ({
  date: payload.date,
  created: payload.created,
  sent: payload.sent,
});

const toDailyRunOutcomePoint = (payload: DailyRunOutcomePointResponse): DailyRunOutcomePoint => ({
  date: payload.date,
  createdRecords: payload.created_records,
  updatedRecords: payload.updated_records,
});

const toDailyGoogleStatusPoint = (payload: DailyGoogleStatusPointResponse): DailyGoogleStatusPoint => ({
  date: payload.date,
  immediateMatches: payload.immediate_matches,
  lateMatches: payload.late_matches,
  notFound: payload.not_found,
  insufficient: payload.insufficient,
  pending: payload.pending,
  other: payload.other,
});

const toGoogleStatusBreakdown = (payload: GoogleStatusBreakdownResponse): GoogleStatusBreakdown => ({
  found: payload.found,
  notFound: payload.not_found,
  insufficient: payload.insufficient,
  pending: payload.pending,
  other: payload.other,
});

const toDashboardRunBreakdown = (payload: DashboardRunBreakdownResponse): DashboardRunBreakdown => ({
  runId: payload.run_id,
  startedAt: payload.started_at,
  createdRecords: payload.created_records,
  updatedRecords: payload.updated_records,
  apiCallCount: payload.api_call_count,
  googleApiCallCount: payload.google_api_call_count,
  googleFound: payload.google_found,
  googleFoundLate: payload.google_found_late,
  googleNotFound: payload.google_not_found,
  googleInsufficient: payload.google_insufficient,
  googlePending: payload.google_pending,
  googleOther: payload.google_other,
  alertsCreated: payload.alerts_created,
  alertsSent: payload.alerts_sent,
});

const toDashboardMetrics = (payload: DashboardMetricsResponse): DashboardMetrics => ({
  latestRun: payload.latest_run ? toSyncRun(payload.latest_run) : null,
  latestRunBreakdown: payload.latest_run_breakdown ? toDashboardRunBreakdown(payload.latest_run_breakdown) : null,
  dailyNewBusinesses: payload.daily_new_businesses.map(toDailyMetricPoint),
  dailyApiCalls: payload.daily_api_calls.map(toDailyApiMetricPoint),
  dailyAlerts: payload.daily_alerts.map(toDailyAlertMetricPoint),
  dailyRunOutcomes: payload.daily_run_outcomes.map(toDailyRunOutcomePoint),
  dailyGoogleStatuses: payload.daily_google_statuses.map(toDailyGoogleStatusPoint),
  googleStatusBreakdown: toGoogleStatusBreakdown(payload.google_status_breakdown),
  establishmentStatusBreakdown: payload.establishment_status_breakdown,
});

const toEstablishment = (payload: EstablishmentResponse): Establishment => ({
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
  googleLastCheckedAt: payload.google_last_checked_at,
  googleLastFoundAt: payload.google_last_found_at,
  googleCheckStatus: payload.google_check_status,
});

const toEstablishmentDetail = (payload: EstablishmentDetailResponse): EstablishmentDetail => ({
  ...toEstablishment(payload),
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

const readPayload = async (response: Response): Promise<unknown> => {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};

const request = async <T>(path: string, init?: RequestInit): Promise<RequestResult<T>> => {
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const adminToken = getAdminToken();
  if (adminToken && !headers.has("X-Admin-Token")) {
    headers.set("X-Admin-Token", adminToken);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  const payload = (await readPayload(response)) as T;

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null && "detail" in (payload as Record<string, unknown>)
        ? String((payload as Record<string, unknown>).detail)
        : response.statusText || "Requête échouée";
    throw new ApiError(message, response.status, payload);
  }

  return { data: payload, status: response.status };
};

export interface TriggerSyncResult {
  run: SyncRun | null;
  status: number;
  detail?: string;
}

const isSyncRunResponse = (payload: unknown): payload is SyncRunResponse => {
  return Boolean(payload) && typeof payload === "object" && "id" in (payload as Record<string, unknown>);
};

export const adminApi = {
  async getStatsSummary(): Promise<StatsSummary> {
    const { data } = await request<StatsSummaryResponse>("/admin/stats/summary");
    return toStatsSummary(data);
  },

  async getDashboardMetrics(days = 30): Promise<DashboardMetrics> {
    const { data } = await request<DashboardMetricsResponse>(
      `/admin/stats/dashboard?days=${encodeURIComponent(days)}`
    );
    return toDashboardMetrics(data);
  },

  async getSyncRuns(limit = 20): Promise<SyncRun[]> {
    const { data } = await request<SyncRunResponse[]>(`/admin/sync-runs?limit=${encodeURIComponent(limit)}`);
    return data.map(toSyncRun);
  },

  async getSyncState(): Promise<SyncState[]> {
    const { data } = await request<SyncStateResponse[]>("/admin/sync-state");
    return data.map(toSyncState);
  },

  async getRecentAlerts(limit = 20): Promise<Alert[]> {
    const { data } = await request<AlertResponse[]>(`/admin/alerts/recent?limit=${encodeURIComponent(limit)}`);
    return data.map(toAlert);
  },

  async triggerSync(payload: SyncRequestPayload): Promise<TriggerSyncResult> {
    const requestBody: Record<string, unknown> = {};
    if (payload.checkForUpdates !== undefined) {
      requestBody.check_for_updates = payload.checkForUpdates;
    }
    const { data, status } = await request<SyncRunResponse | { detail?: string }>("/admin/sync", {
      method: "POST",
      body: JSON.stringify(requestBody),
    });
    if (isSyncRunResponse(data)) {
      return { run: toSyncRun(data), status };
    }
    const detail = typeof data === "object" && data !== null && "detail" in data ? String((data as { detail?: string }).detail) : undefined;
    return { run: null, status, detail };
  },

  async getEstablishments(params: { limit?: number; offset?: number; q?: string } = {}): Promise<Establishment[]> {
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
    const queryString = query.toString();
    const path = `/admin/establishments${queryString ? `?${queryString}` : ""}`;
    const { data } = await request<EstablishmentResponse[]>(path);
    return data.map(toEstablishment);
  },

  async getEstablishment(siret: string): Promise<EstablishmentDetail> {
    const { data } = await request<EstablishmentDetailResponse>(
      `/admin/establishments/${encodeURIComponent(siret)}`
    );
    return toEstablishmentDetail(data);
  },

  async deleteEstablishment(siret: string): Promise<void> {
    await request(`/admin/establishments/${encodeURIComponent(siret)}`, {
      method: "DELETE",
    });
  },

  async deleteRun(runId: string): Promise<DeleteRunResponse> {
    const { data } = await request<DeleteRunResponse>(`/admin/sync-runs/${encodeURIComponent(runId)}`, {
      method: "DELETE",
    });
    return data;
  },

  async checkGoogleForEstablishment(siret: string): Promise<GoogleCheckResult> {
    const { data } = await request<ManualGoogleCheckResponse>(`/admin/establishments/${encodeURIComponent(siret)}/google-check`, {
      method: "POST",
    });
    return {
      found: data.found,
      emailSent: data.email_sent,
      message: data.message,
      placeId: data.place_id,
      placeUrl: data.place_url,
      checkStatus: data.check_status,
      establishment: toEstablishment(data.establishment),
    };
  },

  async sendEmailTest(payload: EmailTestPayload): Promise<EmailTestResult> {
    const requestBody: Record<string, unknown> = {};
    if (payload.subject && payload.subject.trim()) {
      requestBody.subject = payload.subject.trim();
    }
    if (payload.body && payload.body.trim()) {
      requestBody.body = payload.body;
    }
    if (payload.recipients && payload.recipients.length > 0) {
      requestBody.recipients = payload.recipients;
    }

    const { data } = await request<EmailTestResponse>("/admin/email/test", {
      method: "POST",
      body: JSON.stringify(requestBody),
    });
    return {
      sent: data.sent,
      provider: data.provider,
      subject: data.subject,
      recipients: data.recipients,
    };
  },

  async exportGooglePlaces(params: { startDate: string; endDate: string }): Promise<Blob> {
    const headers = new Headers();
    headers.set("Accept", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");

    const adminToken = getAdminToken();
    if (adminToken) {
      headers.set("X-Admin-Token", adminToken);
    }

    const url = new URL("/admin/google/places-export", API_BASE_URL);
    url.searchParams.set("start_date", params.startDate);
    url.searchParams.set("end_date", params.endDate);

    const response = await fetch(url.toString(), { headers });
    if (!response.ok) {
      const payload = await readPayload(response);
      const message =
        typeof payload === "object" && payload !== null && "detail" in (payload as Record<string, unknown>)
          ? String((payload as Record<string, unknown>).detail)
          : response.statusText || "Export impossible";
      throw new ApiError(message, response.status, payload);
    }
    return await response.blob();
  },
};

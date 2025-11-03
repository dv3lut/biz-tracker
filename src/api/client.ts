import { SyncRequestPayload, SyncRun, SyncState, Alert, StatsSummary, Establishment } from "../types";

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
  fetched_records: number;
  created_records: number;
  last_cursor: string | null;
  query_checksum: string | null;
  resumed_from_run_id: string | null;
  notes: string | null;
  max_records: number | null;
  total_expected_records: number | null;
  progress: number | null;
  estimated_remaining_seconds: number | null;
  estimated_completion_at: string | null;
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
  last_full_run: SyncRunResponse | null;
  last_incremental_run: SyncRunResponse | null;
  last_alert: AlertResponse | null;
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";
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

const toSyncRun = (payload: SyncRunResponse): SyncRun => ({
  id: payload.id,
  scopeKey: payload.scope_key,
  runType: payload.run_type,
  status: payload.status,
  startedAt: payload.started_at,
  finishedAt: payload.finished_at,
  apiCallCount: payload.api_call_count,
  fetchedRecords: payload.fetched_records,
  createdRecords: payload.created_records,
  lastCursor: payload.last_cursor,
  queryChecksum: payload.query_checksum,
  resumedFromRunId: payload.resumed_from_run_id,
  notes: payload.notes,
  maxRecords: payload.max_records,
  totalExpectedRecords: payload.total_expected_records,
  progress: payload.progress,
  estimatedRemainingSeconds: payload.estimated_remaining_seconds,
  estimatedCompletionAt: payload.estimated_completion_at,
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
  lastFullRun: payload.last_full_run ? toSyncRun(payload.last_full_run) : null,
  lastIncrementalRun: payload.last_incremental_run ? toSyncRun(payload.last_incremental_run) : null,
  lastAlert: payload.last_alert ? toAlert(payload.last_alert) : null,
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

export const adminApi = {
  async getStatsSummary(): Promise<StatsSummary> {
    const { data } = await request<StatsSummaryResponse>("/admin/stats/summary");
    return toStatsSummary(data);
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

  async triggerFullSync(payload: SyncRequestPayload): Promise<TriggerSyncResult> {
    const { data, status } = await request<SyncRunResponse>("/admin/sync/full", {
      method: "POST",
      body: JSON.stringify({
        resume: payload.resume,
        max_records: payload.maxRecords,
      }),
    });
    return { run: toSyncRun(data), status };
  },

  async triggerIncrementalSync(): Promise<TriggerSyncResult> {
    const { data, status } = await request<SyncRunResponse | { detail?: string }>("/admin/sync/incremental", {
      method: "POST",
    });

    if (status === 202) {
      const detail =
        typeof data === "object" && data !== null && "detail" in data ? String((data as { detail?: string }).detail) : undefined;
      return { run: null, status, detail };
    }

    return { run: toSyncRun(data as SyncRunResponse), status };
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
};

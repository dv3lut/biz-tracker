import {
  RunSummary,
  RunSummaryEstablishment,
  RunSummaryUpdatedEstablishment,
  SyncRequestPayload,
  SyncRun,
  SyncState,
} from "../types";
import { request } from "./http";

export interface SyncRunResponse {
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

export interface RunSummaryResponse {
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

export interface SyncStateResponse {
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

export interface DeleteRunResponse {
  establishments_deleted: number;
  alerts_deleted: number;
  states_reset: number;
  runs_updated: number;
  sync_run_deleted: boolean;
}

const mapRunSummaryEstablishment = (
  payload: RunSummaryEstablishmentResponse,
): RunSummaryEstablishment => ({
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

const mapRunSummaryUpdatedEstablishment = (
  payload: RunSummaryUpdatedEstablishmentResponse,
): RunSummaryUpdatedEstablishment => ({
  ...mapRunSummaryEstablishment(payload),
  changedFields: payload.changed_fields ?? [],
});

const mapRunSummary = (payload: RunSummaryResponse): RunSummary => ({
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
    newEstablishments: (payload.samples.new_establishments ?? []).map(mapRunSummaryEstablishment),
    updatedEstablishments: (payload.samples.updated_establishments ?? []).map(
      mapRunSummaryUpdatedEstablishment,
    ),
    googleLateMatches: (payload.samples.google_late_matches ?? []).map(mapRunSummaryEstablishment),
    googleImmediateMatches: (payload.samples.google_immediate_matches ?? []).map(
      mapRunSummaryEstablishment,
    ),
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

export const mapSyncRun = (payload: SyncRunResponse): SyncRun => ({
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
  summary: payload.summary ? mapRunSummary(payload.summary) : null,
});

export const mapSyncState = (payload: SyncStateResponse): SyncState => ({
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

const isSyncRunResponse = (payload: unknown): payload is SyncRunResponse => {
  return Boolean(payload) && typeof payload === "object" && "id" in (payload as Record<string, unknown>);
};

export interface TriggerSyncResult {
  run: SyncRun | null;
  status: number;
  detail?: string;
}

export const syncApi = {
  async fetchRuns(limit = 20): Promise<SyncRun[]> {
    const { data } = await request<SyncRunResponse[]>(`/admin/sync-runs?limit=${encodeURIComponent(limit)}`);
    return data.map(mapSyncRun);
  },

  async fetchState(): Promise<SyncState[]> {
    const { data } = await request<SyncStateResponse[]>("/admin/sync-state");
    return data.map(mapSyncState);
  },

  async trigger(payload: SyncRequestPayload): Promise<TriggerSyncResult> {
    const body: Record<string, unknown> = {};
    if (payload.checkForUpdates !== undefined) {
      body.check_for_updates = payload.checkForUpdates;
    }
    const { data, status } = await request<SyncRunResponse | { detail?: string }>("/admin/sync", {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (isSyncRunResponse(data)) {
      return { run: mapSyncRun(data), status };
    }
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail?: string }).detail)
        : undefined;
    return { run: null, status, detail };
  },

  async deleteRun(runId: string): Promise<DeleteRunResponse> {
    const { data } = await request<DeleteRunResponse>(`/admin/sync-runs/${encodeURIComponent(runId)}`, {
      method: "DELETE",
    });
    return data;
  },
};

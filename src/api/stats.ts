import {
  DashboardMetrics,
  DailyAlertMetricPoint,
  DailyApiMetricPoint,
  DailyGoogleStatusPoint,
  DailyMetricPoint,
  DailyRunOutcomePoint,
  GoogleStatusBreakdown,
  NafCategoryStat,
  StatsSummary,
} from "../types";
import { request } from "./http";
import { AlertResponse, mapAlert } from "./alerts";
import { SyncRunResponse, mapSyncRun } from "./sync";

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

interface NafSubCategoryStatResponse {
  subcategory_id: string;
  naf_code: string;
  name: string;
  establishment_count: number;
}

interface NafCategoryStatResponse {
  category_id: string;
  name: string;
  total_establishments: number;
  subcategories: NafSubCategoryStatResponse[];
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
  naf_category_breakdown: NafCategoryStatResponse[];
}

const mapDailyMetricPoint = (payload: DailyMetricPointResponse): DailyMetricPoint => ({
  date: payload.date,
  value: payload.value,
});

const mapDailyApiMetricPoint = (payload: DailyApiMetricPointResponse): DailyApiMetricPoint => ({
  date: payload.date,
  value: payload.value,
  runCount: payload.run_count,
  googleApiCallCount: payload.google_api_call_count,
});

const mapDailyAlertMetricPoint = (
  payload: DailyAlertMetricPointResponse,
): DailyAlertMetricPoint => ({
  date: payload.date,
  created: payload.created,
  sent: payload.sent,
});

const mapDailyRunOutcomePoint = (
  payload: DailyRunOutcomePointResponse,
): DailyRunOutcomePoint => ({
  date: payload.date,
  createdRecords: payload.created_records,
  updatedRecords: payload.updated_records,
});

const mapDailyGoogleStatusPoint = (
  payload: DailyGoogleStatusPointResponse,
): DailyGoogleStatusPoint => ({
  date: payload.date,
  immediateMatches: payload.immediate_matches,
  lateMatches: payload.late_matches,
  notFound: payload.not_found,
  insufficient: payload.insufficient,
  pending: payload.pending,
  other: payload.other,
});

const mapGoogleStatusBreakdown = (
  payload: GoogleStatusBreakdownResponse,
): GoogleStatusBreakdown => ({
  found: payload.found,
  notFound: payload.not_found,
  insufficient: payload.insufficient,
  pending: payload.pending,
  other: payload.other,
});

const mapNafSubCategoryStat = (
  payload: NafSubCategoryStatResponse,
): NafCategoryStat["subcategories"][number] => ({
  subcategoryId: payload.subcategory_id,
  nafCode: payload.naf_code,
  name: payload.name,
  establishmentCount: payload.establishment_count,
});

const mapNafCategoryStat = (payload: NafCategoryStatResponse): NafCategoryStat => ({
  categoryId: payload.category_id,
  name: payload.name,
  totalEstablishments: payload.total_establishments,
  subcategories: payload.subcategories.map(mapNafSubCategoryStat),
});

const mapDashboardRunBreakdown = (
  payload: DashboardRunBreakdownResponse,
) => ({
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

const mapStatsSummary = (payload: StatsSummaryResponse): StatsSummary => ({
  totalEstablishments: payload.total_establishments,
  totalAlerts: payload.total_alerts,
  databaseSizePretty: payload.database_size_pretty ?? null,
  lastRun: payload.last_run ? mapSyncRun(payload.last_run) : null,
  lastAlert: payload.last_alert ? mapAlert(payload.last_alert) : null,
});

const mapDashboardMetrics = (payload: DashboardMetricsResponse): DashboardMetrics => ({
  latestRun: payload.latest_run ? mapSyncRun(payload.latest_run) : null,
  latestRunBreakdown: payload.latest_run_breakdown
    ? mapDashboardRunBreakdown(payload.latest_run_breakdown)
    : null,
  dailyNewBusinesses: payload.daily_new_businesses.map(mapDailyMetricPoint),
  dailyApiCalls: payload.daily_api_calls.map(mapDailyApiMetricPoint),
  dailyAlerts: payload.daily_alerts.map(mapDailyAlertMetricPoint),
  dailyRunOutcomes: payload.daily_run_outcomes.map(mapDailyRunOutcomePoint),
  dailyGoogleStatuses: payload.daily_google_statuses.map(mapDailyGoogleStatusPoint),
  googleStatusBreakdown: mapGoogleStatusBreakdown(payload.google_status_breakdown),
  establishmentStatusBreakdown: payload.establishment_status_breakdown,
  nafCategoryBreakdown: payload.naf_category_breakdown.map(mapNafCategoryStat),
});

export const statsApi = {
  async fetchSummary(): Promise<StatsSummary> {
    const { data } = await request<StatsSummaryResponse>("/admin/stats/summary");
    return mapStatsSummary(data);
  },

  async fetchDashboardMetrics(days = 30): Promise<DashboardMetrics> {
    const { data } = await request<DashboardMetricsResponse>(
      `/admin/stats/dashboard?days=${encodeURIComponent(days)}`,
    );
    return mapDashboardMetrics(data);
  },
};

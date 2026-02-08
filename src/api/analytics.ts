import type {
  NafAnalyticsAggregation,
  NafAnalyticsGranularity,
  NafAnalyticsResponse,
} from "../types";
import { request } from "./http";

interface NafAnalyticsTimePointResponse {
  period: string;
  total_fetched: number;
  non_diffusible: number;
  insufficient_info: number;
  google_found: number;
  google_not_found: number;
  google_pending: number;
  listing_recent: number;
  listing_recent_missing_contact: number;
  listing_not_recent: number;
  linkedin_found: number;
  linkedin_not_found: number;
  linkedin_pending: number;
  alerts_created: number;
}

interface NafAnalyticsItemResponse {
  id: string;
  code: string | null;
  name: string;
  totals: NafAnalyticsTimePointResponse;
  time_series: NafAnalyticsTimePointResponse[];
}

interface NafAnalyticsApiResponse {
  granularity: NafAnalyticsGranularity;
  start_date: string;
  end_date: string;
  aggregation: NafAnalyticsAggregation;
  items: NafAnalyticsItemResponse[];
  global_totals: NafAnalyticsTimePointResponse;
}

const mapTimePoint = (point: NafAnalyticsTimePointResponse) => ({
  period: point.period,
  totalFetched: point.total_fetched,
  nonDiffusible: point.non_diffusible,
  insufficientInfo: point.insufficient_info,
  googleFound: point.google_found,
  googleNotFound: point.google_not_found,
  googlePending: point.google_pending,
  listingRecent: point.listing_recent,
  listingRecentMissingContact: point.listing_recent_missing_contact,
  listingNotRecent: point.listing_not_recent,
  linkedinFound: point.linkedin_found,
  linkedinNotFound: point.linkedin_not_found,
  linkedinPending: point.linkedin_pending,
  alertsCreated: point.alerts_created,
});

const mapItem = (item: NafAnalyticsItemResponse) => ({
  id: item.id,
  code: item.code,
  name: item.name,
  totals: mapTimePoint(item.totals),
  timeSeries: item.time_series.map(mapTimePoint),
});

export interface NafAnalyticsParams {
  startDate?: string;
  endDate?: string;
  granularity?: NafAnalyticsGranularity;
  aggregation?: NafAnalyticsAggregation;
  categoryId?: string;
  nafCode?: string;
}

export const analyticsApi = {
  async fetchNafAnalytics(params: NafAnalyticsParams = {}): Promise<NafAnalyticsResponse> {
    const searchParams = new URLSearchParams();
    if (params.startDate) searchParams.set("start_date", params.startDate);
    if (params.endDate) searchParams.set("end_date", params.endDate);
    if (params.granularity) searchParams.set("granularity", params.granularity);
    if (params.aggregation) searchParams.set("aggregation", params.aggregation);
    if (params.categoryId) searchParams.set("category_id", params.categoryId);
    if (params.nafCode) searchParams.set("naf_code", params.nafCode);

    const queryString = searchParams.toString();
    const url = `/admin/stats/naf-analytics${queryString ? `?${queryString}` : ""}`;

    const { data } = await request<NafAnalyticsApiResponse>(url);

    return {
      granularity: data.granularity,
      startDate: data.start_date,
      endDate: data.end_date,
      aggregation: data.aggregation,
      items: data.items.map(mapItem),
      globalTotals: mapTimePoint(data.global_totals),
    };
  },
};

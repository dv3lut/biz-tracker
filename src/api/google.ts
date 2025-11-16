import { GoogleCheckResult, GoogleRetryConfig, GoogleRetryRule } from "../types";
import { getAdminToken } from "./auth";
import { ApiError, request } from "./http";
import { EstablishmentResponse, mapEstablishment } from "./establishments";

type GooglePlacesExportParams = {
  startDate: string;
  endDate: string;
};

interface ManualGoogleCheckResponse {
  found: boolean;
  email_sent: boolean;
  message: string;
  place_id: string | null;
  place_url: string | null;
  check_status: string;
  establishment: EstablishmentResponse;
}

interface GoogleRetryRuleResponse {
  max_age_days: number | null;
  frequency_days: number;
}

interface GoogleRetryConfigResponse {
  retry_weekdays: number[];
  default_rules: GoogleRetryRuleResponse[];
  micro_rules: GoogleRetryRuleResponse[];
}

const mapRetryRule = (rule: GoogleRetryRuleResponse): GoogleRetryRule => ({
  maxAgeDays: rule.max_age_days ?? null,
  frequencyDays: rule.frequency_days,
});

const mapRetryConfig = (payload: GoogleRetryConfigResponse): GoogleRetryConfig => ({
  retryWeekdays: payload.retry_weekdays ?? [],
  defaultRules: (payload.default_rules ?? []).map(mapRetryRule),
  microRules: (payload.micro_rules ?? []).map(mapRetryRule),
});

const serializeRule = (rule: GoogleRetryRule): GoogleRetryRuleResponse => ({
  max_age_days: rule.maxAgeDays,
  frequency_days: rule.frequencyDays,
});

const serializeConfig = (payload: GoogleRetryConfig): GoogleRetryConfigResponse => ({
  retry_weekdays: payload.retryWeekdays,
  default_rules: payload.defaultRules.map(serializeRule),
  micro_rules: payload.microRules.map(serializeRule),
});

export const googleApi = {
  async checkEstablishment(siret: string): Promise<GoogleCheckResult> {
    const { data } = await request<ManualGoogleCheckResponse>(
      `/admin/establishments/${encodeURIComponent(siret)}/google-check`,
      {
        method: "POST",
      },
    );
    return {
      found: data.found,
      emailSent: data.email_sent,
      message: data.message,
      placeId: data.place_id,
      placeUrl: data.place_url,
      checkStatus: data.check_status,
      establishment: mapEstablishment(data.establishment),
    };
  },

  async exportPlaces(params: GooglePlacesExportParams): Promise<Blob> {
    const headers = new Headers();
    headers.set(
      "Accept",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    );
    const adminToken = getAdminToken();
    if (adminToken) {
      headers.set("X-Admin-Token", adminToken);
    }

    const baseUrl = import.meta.env.VITE_APP_API_BASE_URL ?? "http://localhost:8080";
    const url = new URL("/admin/google/places-export", baseUrl);
    url.searchParams.set("start_date", params.startDate);
    url.searchParams.set("end_date", params.endDate);

    const response = await fetch(url.toString(), { headers });
    if (!response.ok) {
      const payload = await response.text();
      let detail: unknown = payload;
      try {
        detail = payload ? JSON.parse(payload) : null;
      } catch {
        // keep raw payload when parsing fails
      }
      const message =
        typeof detail === "object" && detail !== null && "detail" in (detail as Record<string, unknown>)
          ? String((detail as Record<string, unknown>).detail)
          : response.statusText || "Export impossible";
      throw new ApiError(message, response.status, detail);
    }
    return await response.blob();
  },

  async fetchRetryConfig(): Promise<GoogleRetryConfig> {
    const { data } = await request<GoogleRetryConfigResponse>("/admin/google/retry-config");
    return mapRetryConfig(data);
  },

  async updateRetryConfig(payload: GoogleRetryConfig): Promise<GoogleRetryConfig> {
    const body = JSON.stringify(serializeConfig(payload));
    const { data } = await request<GoogleRetryConfigResponse>("/admin/google/retry-config", {
      method: "PUT",
      body,
    });
    return mapRetryConfig(data);
  },
};

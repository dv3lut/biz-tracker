import { GoogleCheckResult } from "../types";
import { getAdminToken } from "./auth";
import { ApiError, request } from "./http";
import { EstablishmentResponse, mapEstablishment } from "./establishments";

interface ManualGoogleCheckResponse {
  found: boolean;
  email_sent: boolean;
  message: string;
  place_id: string | null;
  place_url: string | null;
  check_status: string;
  establishment: EstablishmentResponse;
}

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

  async exportPlaces(): Promise<Blob> {
    const headers = new Headers();
    headers.set(
      "Accept",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    );
    const adminToken = getAdminToken();
    if (adminToken) {
      headers.set("X-Admin-Token", adminToken);
    }

    const response = await fetch(
      `${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080"}/admin/google/places-export`,
      { headers },
    );
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
};

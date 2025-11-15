import { Alert } from "../types";
import { getAdminToken } from "./auth";
import { ApiError, request } from "./http";

export interface AlertResponse {
  id: string;
  run_id: string;
  siret: string;
  recipients: string[];
  payload: Record<string, unknown>;
  created_at: string;
  sent_at: string | null;
}

export const mapAlert = (payload: AlertResponse): Alert => ({
  id: payload.id,
  runId: payload.run_id,
  siret: payload.siret,
  recipients: payload.recipients,
  payload: payload.payload,
  createdAt: payload.created_at,
  sentAt: payload.sent_at,
});

export const alertsApi = {
  async fetchRecent(limit = 20): Promise<Alert[]> {
    const { data } = await request<AlertResponse[]>(`/admin/alerts/recent?limit=${encodeURIComponent(limit)}`);
    return data.map(mapAlert);
  },

  async exportByCreation(days: number): Promise<Blob> {
    const normalizedDays = Number.isFinite(days) ? Math.max(1, Math.min(Math.round(days), 365)) : 30;
    const headers = new Headers();
    headers.set("Accept", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    const adminToken = getAdminToken();
    if (adminToken) {
      headers.set("X-Admin-Token", adminToken);
    }

    const baseUrl = import.meta.env.VITE_APP_API_BASE_URL ?? "http://localhost:8080";
    const response = await fetch(`${baseUrl}/admin/alerts/export?days=${encodeURIComponent(normalizedDays)}`, {
      headers,
    });
    if (!response.ok) {
      const payloadText = await response.text();
      let detail: unknown = payloadText;
      try {
        detail = payloadText ? JSON.parse(payloadText) : null;
      } catch {
        // ignore JSON parsing errors, keep raw payload
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

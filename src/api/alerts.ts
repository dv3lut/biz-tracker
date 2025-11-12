import { Alert } from "../types";
import { request } from "./http";

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
};

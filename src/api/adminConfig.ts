import { AdminEmailConfig } from "../types";
import { request } from "./http";

export interface AdminEmailConfigPayload {
  recipients: string[];
}

export const adminConfigApi = {
  fetch: async (): Promise<AdminEmailConfig> => {
    const response = await request<AdminEmailConfig>("/admin/email/admin-recipients");
    return response.data;
  },
  update: async (payload: AdminEmailConfigPayload): Promise<AdminEmailConfig> => {
    const response = await request<AdminEmailConfig>("/admin/email/admin-recipients", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    return response.data;
  },
};

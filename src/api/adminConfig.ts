import { AdminEmailConfig } from "../types";
import { request } from "./http";

export interface AdminEmailConfigPayload {
  recipients: string[];
  includePreviousMonthDayAlerts: boolean;
}

interface AdminEmailConfigResponse {
  recipients: string[];
  include_previous_month_day_alerts: boolean;
}

const mapAdminEmailConfig = (response: AdminEmailConfigResponse): AdminEmailConfig => ({
  recipients: response.recipients,
  includePreviousMonthDayAlerts: response.include_previous_month_day_alerts,
});

const mapAdminEmailConfigPayload = (payload: AdminEmailConfigPayload): AdminEmailConfigResponse => ({
  recipients: payload.recipients,
  include_previous_month_day_alerts: payload.includePreviousMonthDayAlerts,
});

export const adminConfigApi = {
  fetch: async (): Promise<AdminEmailConfig> => {
    const response = await request<AdminEmailConfigResponse>("/admin/email/admin-recipients");
    return mapAdminEmailConfig(response.data);
  },
  update: async (payload: AdminEmailConfigPayload): Promise<AdminEmailConfig> => {
    const response = await request<AdminEmailConfigResponse>("/admin/email/admin-recipients", {
      method: "PUT",
      body: JSON.stringify(mapAdminEmailConfigPayload(payload)),
    });
    return mapAdminEmailConfig(response.data);
  },
};

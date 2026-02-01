import { request } from "./http";
import type { AdminStripeSettings, AdminStripeSettingsUpdatePayload, AdminStripeSettingsUpdateResult } from "../types";

type StripeSettingsResponse = {
  trial_period_days: number;
};

type StripeSettingsUpdateResponse = {
  trial_period_days: number;
  updated_trials?: number;
  failed_trials?: number;
};

const mapStripeSettings = (response: StripeSettingsResponse): AdminStripeSettings => ({
  trialPeriodDays: response.trial_period_days,
});

const mapStripeSettingsUpdate = (response: StripeSettingsUpdateResponse): AdminStripeSettingsUpdateResult => ({
  trialPeriodDays: response.trial_period_days,
  updatedTrials: response.updated_trials ?? 0,
  failedTrials: response.failed_trials ?? 0,
});

export const stripeSettingsApi = {
  fetch: async (): Promise<AdminStripeSettings> => {
    const response = await request<StripeSettingsResponse>("/admin/stripe/settings");
    return mapStripeSettings(response.data);
  },
  update: async (payload: AdminStripeSettingsUpdatePayload): Promise<AdminStripeSettingsUpdateResult> => {
    const response = await request<StripeSettingsUpdateResponse>("/admin/stripe/settings", {
      method: "PUT",
      body: JSON.stringify({
        trial_period_days: payload.trialPeriodDays,
        apply_to_existing_trials: payload.applyToExistingTrials,
      }),
    });
    return mapStripeSettingsUpdate(response.data);
  },
};

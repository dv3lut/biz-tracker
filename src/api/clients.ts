import type { Client, Department, ListingStatus } from "../types";
import { mapNafSubCategoryResponse, type NafSubCategoryResponse } from "./naf";
import { request } from "./http";

type ClientRecipientResponse = {
  id: string;
  email: string;
  created_at: string;
};

type ClientResponse = {
  id: string;
  name: string;
  start_date: string;
  end_date: string | null;
  listing_statuses: string[];
  include_admins_in_client_alerts: boolean;
  use_subcategory_label_in_client_alerts: boolean;
  emails_sent_count: number;
  last_email_sent_at: string | null;
  created_at: string;
  updated_at: string;
  recipients: ClientRecipientResponse[];
  subscriptions: ClientSubscriptionResponse[];
  departments: DepartmentResponse[];
  stripe_subscriptions: StripeSubscriptionResponse[];
  subscription_events: ClientSubscriptionEventResponse[];
};

type DepartmentResponse = {
  id: string;
  code: string;
  name: string;
  order_index: number;
  region_id: string;
};

type StripeSubscriptionResponse = {
  id: string;
  client_id: string;
  stripe_subscription_id: string;
  stripe_customer_id: string | null;
  status: string | null;
  plan_key: string | null;
  price_id: string | null;
  referrer_name: string | null;
  purchased_at: string | null;
  trial_start_at: string | null;
  trial_end_at: string | null;
  paid_start_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at: string | null;
  canceled_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
};

type ClientSubscriptionResponse = {
  client_id: string;
  subcategory_id: string;
  created_at: string;
  subcategory: NafSubCategoryResponse;
};

type ClientSubscriptionEventResponse = {
  id: string;
  client_id: string;
  stripe_subscription_id: string | null;
  event_type: string;
  from_plan_key: string | null;
  to_plan_key: string | null;
  from_category_ids: string[] | null;
  to_category_ids: string[] | null;
  effective_at: string | null;
  source: string | null;
  created_at: string;
};

export interface ClientCreatePayload {
  name: string;
  startDate: string;
  endDate?: string | null;
  listingStatuses: ListingStatus[];
  includeAdminsInClientAlerts: boolean;
  useSubcategoryLabelInClientAlerts: boolean;
  recipients: string[];
  subscriptionIds: string[];
  departmentIds: string[];
}

export interface ClientUpdatePayload {
  name?: string;
  startDate?: string;
  endDate?: string | null;
  listingStatuses?: ListingStatus[];
  includeAdminsInClientAlerts?: boolean;
  useSubcategoryLabelInClientAlerts?: boolean;
  recipients?: string[];
  subscriptionIds?: string[];
  departmentIds?: string[];
}

const mapDepartmentResponse = (department: DepartmentResponse): Department => ({
  id: department.id,
  code: department.code,
  name: department.name,
  orderIndex: department.order_index,
  regionId: department.region_id,
});

const mapClient = (client: ClientResponse): Client => {
  return {
    id: client.id,
    name: client.name,
    startDate: client.start_date,
    endDate: client.end_date,
    listingStatuses: (client.listing_statuses ?? []) as ListingStatus[],
    includeAdminsInClientAlerts: client.include_admins_in_client_alerts ?? false,
    useSubcategoryLabelInClientAlerts: client.use_subcategory_label_in_client_alerts ?? false,
    emailsSentCount: client.emails_sent_count,
    lastEmailSentAt: client.last_email_sent_at,
    createdAt: client.created_at,
    updatedAt: client.updated_at,
    recipients: client.recipients.map((recipient) => ({
      id: recipient.id,
      email: recipient.email,
      createdAt: recipient.created_at,
    })),
    subscriptions: (client.subscriptions || []).map((subscription) => ({
      clientId: subscription.client_id,
      subcategoryId: subscription.subcategory_id,
      createdAt: subscription.created_at,
      subcategory: mapNafSubCategoryResponse(subscription.subcategory),
    })),
    departments: (client.departments || []).map(mapDepartmentResponse),
    stripeSubscriptions: (client.stripe_subscriptions || []).map((subscription) => ({
      id: subscription.id,
      clientId: subscription.client_id,
      stripeSubscriptionId: subscription.stripe_subscription_id,
      stripeCustomerId: subscription.stripe_customer_id,
      status: subscription.status,
      planKey: subscription.plan_key,
      priceId: subscription.price_id,
      referrerName: subscription.referrer_name,
      purchasedAt: subscription.purchased_at,
      trialStartAt: subscription.trial_start_at,
      trialEndAt: subscription.trial_end_at,
      paidStartAt: subscription.paid_start_at,
      currentPeriodStart: subscription.current_period_start,
      currentPeriodEnd: subscription.current_period_end,
      cancelAt: subscription.cancel_at,
      canceledAt: subscription.canceled_at,
      endedAt: subscription.ended_at,
      createdAt: subscription.created_at,
      updatedAt: subscription.updated_at,
    })),
    subscriptionEvents: (client.subscription_events || []).map((event) => ({
      id: event.id,
      clientId: event.client_id,
      stripeSubscriptionId: event.stripe_subscription_id,
      eventType: event.event_type,
      fromPlanKey: event.from_plan_key,
      toPlanKey: event.to_plan_key,
      fromCategoryIds: event.from_category_ids,
      toCategoryIds: event.to_category_ids,
      effectiveAt: event.effective_at,
      source: event.source,
      createdAt: event.created_at,
    })),
  };
};

const serializeCreatePayload = (payload: ClientCreatePayload) => ({
  name: payload.name,
  start_date: payload.startDate,
  end_date: payload.endDate ?? null,
  listing_statuses: payload.listingStatuses,
  include_admins_in_client_alerts: payload.includeAdminsInClientAlerts,
  use_subcategory_label_in_client_alerts: payload.useSubcategoryLabelInClientAlerts,
  recipients: payload.recipients,
  subscription_ids: payload.subscriptionIds,
  department_ids: payload.departmentIds,
});

const serializeUpdatePayload = (payload: ClientUpdatePayload) => {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) {
    body.name = payload.name;
  }
  if (payload.startDate !== undefined) {
    body.start_date = payload.startDate;
  }
  if (payload.endDate !== undefined) {
    body.end_date = payload.endDate;
  }
  if (payload.listingStatuses !== undefined) {
    body.listing_statuses = payload.listingStatuses;
  }
  if (payload.includeAdminsInClientAlerts !== undefined) {
    body.include_admins_in_client_alerts = payload.includeAdminsInClientAlerts;
  }
  if (payload.useSubcategoryLabelInClientAlerts !== undefined) {
    body.use_subcategory_label_in_client_alerts = payload.useSubcategoryLabelInClientAlerts;
  }
  if (payload.recipients !== undefined) {
    body.recipients = payload.recipients;
  }
  if (payload.subscriptionIds !== undefined) {
    body.subscription_ids = payload.subscriptionIds;
  }
  if (payload.departmentIds !== undefined) {
    body.department_ids = payload.departmentIds;
  }
  return body;
};

export const clientsApi = {
  list: async (): Promise<Client[]> => {
    const response = await request<ClientResponse[]>("/admin/clients");
    return response.data.map(mapClient);
  },
  get: async (clientId: string): Promise<Client> => {
    const response = await request<ClientResponse>(`/admin/clients/${clientId}`);
    return mapClient(response.data);
  },
  create: async (payload: ClientCreatePayload): Promise<Client> => {
    const response = await request<ClientResponse>("/admin/clients", {
      method: "POST",
      body: JSON.stringify(serializeCreatePayload(payload)),
    });
    return mapClient(response.data);
  },
  update: async (clientId: string, payload: ClientUpdatePayload): Promise<Client> => {
    const response = await request<ClientResponse>(`/admin/clients/${clientId}`, {
      method: "PUT",
      body: JSON.stringify(serializeUpdatePayload(payload)),
    });
    return mapClient(response.data);
  },
  delete: async (clientId: string): Promise<void> => {
    await request<void>(`/admin/clients/${clientId}`, { method: "DELETE" });
  },
};

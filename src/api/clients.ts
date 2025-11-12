import type { Client } from "../types";
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
  emails_sent_count: number;
  last_email_sent_at: string | null;
  created_at: string;
  updated_at: string;
  recipients: ClientRecipientResponse[];
};

export interface ClientCreatePayload {
  name: string;
  startDate: string;
  endDate?: string | null;
  recipients: string[];
}

export interface ClientUpdatePayload {
  name?: string;
  startDate?: string;
  endDate?: string | null;
  recipients?: string[];
}

const mapClient = (client: ClientResponse): Client => {
  return {
    id: client.id,
    name: client.name,
    startDate: client.start_date,
    endDate: client.end_date,
    emailsSentCount: client.emails_sent_count,
    lastEmailSentAt: client.last_email_sent_at,
    createdAt: client.created_at,
    updatedAt: client.updated_at,
    recipients: client.recipients.map((recipient) => ({
      id: recipient.id,
      email: recipient.email,
      createdAt: recipient.created_at,
    })),
  };
};

const serializeCreatePayload = (payload: ClientCreatePayload) => ({
  name: payload.name,
  start_date: payload.startDate,
  end_date: payload.endDate ?? null,
  recipients: payload.recipients,
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
  if (payload.recipients !== undefined) {
    body.recipients = payload.recipients;
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

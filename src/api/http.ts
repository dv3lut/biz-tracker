import { getAdminToken } from "./auth";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export interface RequestResult<T> {
  data: T;
  status: number;
}

const API_BASE_URL = import.meta.env.VITE_APP_API_BASE_URL ?? "http://localhost:8080";

const readPayload = async (response: Response): Promise<unknown> => {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};

const applyDefaultHeaders = (inputHeaders?: HeadersInit, body?: BodyInit | null): Headers => {
  const headers = new Headers(inputHeaders ?? {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const adminToken = getAdminToken();
  if (adminToken && !headers.has("X-Admin-Token")) {
    headers.set("X-Admin-Token", adminToken);
  }
  return headers;
};

export const request = async <T>(path: string, init: RequestInit = {}): Promise<RequestResult<T>> => {
  const headers = applyDefaultHeaders(init.headers, init.body ?? null);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  const payload = (await readPayload(response)) as T;

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null && "detail" in (payload as Record<string, unknown>)
        ? String((payload as Record<string, unknown>).detail)
        : response.statusText || "Requête échouée";
    throw new ApiError(message, response.status, payload);
  }

  return { data: payload, status: response.status };
};

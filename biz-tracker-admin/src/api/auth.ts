const ADMIN_TOKEN_STORAGE_KEY = "admin-token";

const getSessionStorage = (): Storage | null => {
  if (typeof window === "undefined") {
    return null;
  }
  return window.sessionStorage;
};

export const getAdminToken = (): string | null => {
  return getSessionStorage()?.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? null;
};

export const setAdminToken = (token: string): void => {
  getSessionStorage()?.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
};

export const clearAdminToken = (): void => {
  getSessionStorage()?.removeItem(ADMIN_TOKEN_STORAGE_KEY);
};

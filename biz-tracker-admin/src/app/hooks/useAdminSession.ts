import { useCallback, useState } from "react";

import { clearAdminToken, getAdminToken, setAdminToken } from "../../api";

export const useAdminSession = () => {
  const [adminToken, setAdminTokenState] = useState<string | null>(() => getAdminToken());
  const [tokenError, setTokenError] = useState<string | null>(null);

  const handleTokenSubmit = useCallback((token: string) => {
    const trimmed = token.trim();
    if (!trimmed) {
      setTokenError("Le jeton ne peut pas être vide.");
      return;
    }
    setAdminToken(trimmed);
    setAdminTokenState(trimmed);
    setTokenError(null);
  }, []);

  const handleTokenReset = useCallback(() => {
    clearAdminToken();
    setAdminTokenState(null);
    setTokenError(null);
  }, []);

  const requestAdminToken = useCallback(() => {
    setTokenError("Merci de saisir un jeton administrateur.");
  }, []);

  const handleUnauthorized = useCallback(() => {
    clearAdminToken();
    setAdminTokenState(null);
    setTokenError("Jeton invalide. Merci de le ressaisir.");
  }, []);

  return {
    adminToken,
    tokenError,
    handleTokenSubmit,
    handleTokenReset,
    requestAdminToken,
    handleUnauthorized,
  } as const;
};

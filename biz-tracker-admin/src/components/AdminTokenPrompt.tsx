import { FormEvent, useState } from "react";

interface AdminTokenPromptProps {
  onSubmit: (token: string) => void;
  errorMessage?: string | null;
}

export const AdminTokenPrompt = ({ onSubmit, errorMessage }: AdminTokenPromptProps) => {
  const [token, setToken] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextToken = token.trim();
    if (!nextToken) {
      return;
    }
    onSubmit(nextToken);
  };

  return (
    <div className="token-prompt">
      <div className="token-card">
        <h2>Accès administrateur</h2>
        <p className="muted">Saisissez le jeton administrateur pour accéder au tableau de bord.</p>
        <form onSubmit={handleSubmit} className="token-form">
          <label>
            Jeton administrateur
            <input
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Ex: ************"
              autoFocus
            />
          </label>
          {errorMessage ? <p className="feedback error">{errorMessage}</p> : null}
          <button type="submit" className="primary" disabled={!token.trim()}>
            Continuer
          </button>
        </form>
      </div>
    </div>
  );
};

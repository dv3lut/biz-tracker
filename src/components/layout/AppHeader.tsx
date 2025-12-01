type Props = {
  onTokenReset: () => void;
};

export const AppHeader = ({ onTokenReset }: Props) => {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">Business tracker Admin</h1>
        <p className="topbar-subtitle">Pilotez les synchronisations, alertes et destinataires.</p>
      </div>
      <button type="button" className="ghost" onClick={onTokenReset}>
        Changer de jeton
      </button>
    </header>
  );
};

type Props = {
  onTokenReset: () => void;
  onOpenMenu: () => void;
};

export const AppHeader = ({ onTokenReset, onOpenMenu }: Props) => {
  return (
    <header className="topbar">
      <button
        type="button"
        className="topbar__menuButton"
        onClick={onOpenMenu}
        aria-label="Ouvrir le menu"
      >
        <span aria-hidden="true">☰</span>
      </button>
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

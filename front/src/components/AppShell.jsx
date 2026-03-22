export function AppShell({ loading, playerLabel, children }) {
  return (
    <div className="page-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">U</div>
          <div>
            <p className="topbar-label">LOCAL DB DASHBOARD</p>
            <h1>Urgot.GG</h1>
          </div>
        </div>

        <div className="topbar-player">
          <span className="player-chip">{playerLabel || "Aucun joueur chargé"}</span>
          <span className={`topbar-status ${loading ? "is-loading" : ""}`}>
            {loading ? "sync" : "local"}
          </span>
        </div>
      </header>

      <main className="page-content">{children}</main>
    </div>
  );
}

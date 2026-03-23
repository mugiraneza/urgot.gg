export function SearchPanel({ query, onQueryChange, onSubmit, onRefresh, loading }) {
  return (
    <section className="search-strip">
      <div className="search-copy">
        <p className="eyebrow">Recherche locale</p>
        <h2>Historique et statistiques en base</h2>
      </div>

      <div className="search-strip-controls">
        <div className="toggle-group">
          <button
            type="button"
            className={query.mode === "riot_name" ? "is-active" : ""}
            onClick={() => onQueryChange({ ...query, mode: "riot_name" })}
          >
            Riot ID
          </button>
          <button
            type="button"
            className={query.mode === "puuid" ? "is-active" : ""}
            onClick={() => onQueryChange({ ...query, mode: "puuid" })}
          >
            PUUID
          </button>
        </div>

        <input
          className="search-input"
          type="text"
          value={query.value}
          onInput={(event) => onQueryChange({ ...query, value: event.currentTarget.value })}
          placeholder={query.mode === "riot_name" ? "proctologue#urgot" : "PUUID local"}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onSubmit();
            }
          }}
        />

        <button type="button" className="primary-button" onClick={onSubmit} disabled={loading}>
          {loading ? "Chargement" : "Afficher"}
        </button>

        <button type="button" className="secondary-button" onClick={onRefresh} disabled={loading}>
          Actualiser
        </button>
      </div>
    </section>
  );
}

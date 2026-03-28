import { useMemo, useState } from "preact/hooks";

export function SearchPanel({ query, onQueryChange, onSubmit, onRefresh, loading, recentRiotIds = [] }) {
  const [isSuggestionsOpen, setIsSuggestionsOpen] = useState(false);

  const filteredRecentRiotIds = useMemo(() => {
    if (query.mode !== "riot_name") {
      return [];
    }

    const normalizedValue = query.value.trim().toLowerCase();
    const recentIds = Array.isArray(recentRiotIds) ? recentRiotIds : [];

    if (!normalizedValue) {
      return recentIds.slice(0, 6);
    }

    return recentIds
      .filter((riotId) => riotId.toLowerCase().includes(normalizedValue))
      .slice(0, 6);
  }, [query.mode, query.value, recentRiotIds]);

  const showSuggestions = query.mode === "riot_name" && isSuggestionsOpen && filteredRecentRiotIds.length > 0;

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

        <div className="search-input-wrap">
          <input
            className="search-input"
            type="text"
            value={query.value}
            onFocus={() => setIsSuggestionsOpen(true)}
            onBlur={() => window.setTimeout(() => setIsSuggestionsOpen(false), 120)}
            onInput={(event) => {
              setIsSuggestionsOpen(true);
              onQueryChange({ ...query, value: event.currentTarget.value });
            }}
            placeholder={query.mode === "riot_name" ? "proctologue#urgot" : "PUUID local"}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                setIsSuggestionsOpen(false);
                onSubmit();
              }
            }}
          />

          {showSuggestions ? (
            <div className="search-suggestions" role="listbox" aria-label="Riot ID récents">
              {filteredRecentRiotIds.map((riotId) => (
                <button
                  key={riotId}
                  type="button"
                  className="search-suggestion-item"
                  onMouseDown={(event) => {
                    event.preventDefault();
                    onQueryChange({ ...query, value: riotId });
                    setIsSuggestionsOpen(false);
                  }}
                >
                  <span className="search-suggestion-label">{riotId}</span>
                  <span className="search-suggestion-meta">Récent</span>
                </button>
              ))}
            </div>
          ) : null}
        </div>

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

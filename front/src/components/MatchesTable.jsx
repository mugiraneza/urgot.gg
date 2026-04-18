function formatDateLabel(value) {
  const date = new Date(value);
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
}

function formatTime(value) {
  const date = new Date(value);
  return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function formatDuration(seconds) {
  const minutes = Math.floor((seconds || 0) / 60);
  const remainingSeconds = (seconds || 0) % 60;
  return `${minutes}m ${remainingSeconds.toString().padStart(2, "0")}s`;
}

function getNextPageNumber(urlString) {
  if (!urlString) {
    return null;
  }
  try {
    const url = new URL(urlString, window.location.origin);
    return Number(url.searchParams.get("page") || "1");
  } catch {
    return null;
  }
}

function groupMatchesByDay(matches) {
  const groups = [];
  let currentKey = null;
  let currentGroup = null;

  matches.forEach((match) => {
    const key = new Date(match.end_time).toDateString();
    if (key !== currentKey) {
      currentKey = key;
      currentGroup = {
        key,
        label: formatDateLabel(match.end_time),
        matches: [],
      };
      groups.push(currentGroup);
    }
    currentGroup.matches.push(match);
  });

  return groups;
}

function TeamRoster({ title, players }) {
  return (
    <div className="expanded-team">
      <h4>{title}</h4>
      <div className="expanded-roster">
        {players.map((player) => (
          <div className="expanded-player" key={`${title}-${player.riot_name}`}>
            <div className="expanded-player-title">
              {player.champion_image_url ? (
                <img className="champion-icon" src={player.champion_image_url} alt={player.champion} />
              ) : null}
              <div className="expanded-player-heading">
                <strong>{player.riot_name}</strong>
                {player.rank_label ? <span className="rank-badge">{player.rank_label}</span> : null}
              </div>
            </div>
            <span>{player.champion}</span>
            <small>
              {player.kills}/{player.deaths}/{player.assists}
            </small>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MatchesTable({
  matches,
  pagination,
  selectedMatchId,
  onSelectMatch,
  onPageChange,
  loading,
  filters,
  filterOptions,
  onFiltersChange,
}) {
  const groups = groupMatchesByDay(matches);
  const activeFiltersCount = [filters.queue, filters.championName, filters.position].filter(Boolean).length;

  function updateFilter(key, value) {
    onFiltersChange({
      ...filters,
      [key]: value,
    });
  }

  function resetFilters() {
    onFiltersChange({
      queue: "",
      championName: "",
      position: "",
    });
  }

  return (
    <section className="feed-card">
      <div className="section-header">
        <div>
          <p className="eyebrow">Historique</p>
          <h2>Flux de matchs</h2>
        </div>
        <span className="pill">{pagination.count} parties locales</span>
      </div>

      <div className="match-filters" aria-label="Filtres des parties">
        <label>
          <span>Type</span>
          <select
            value={filters.queue}
            onChange={(event) => updateFilter("queue", event.currentTarget.value)}
            disabled={loading}
          >
            <option value="">Tous les types</option>
            {filterOptions.modes.map((mode) => (
              <option value={mode.value} key={mode.value}>
                {mode.label} ({mode.count})
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Champion</span>
          <select
            value={filters.championName}
            onChange={(event) => updateFilter("championName", event.currentTarget.value)}
            disabled={loading}
          >
            <option value="">Tous les champions</option>
            {filterOptions.champions.map((champion) => (
              <option value={champion.value} key={champion.value}>
                {champion.label} ({champion.count})
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Poste</span>
          <select
            value={filters.position}
            onChange={(event) => updateFilter("position", event.currentTarget.value)}
            disabled={loading}
          >
            <option value="">Tous les postes</option>
            {filterOptions.positions.map((position) => (
              <option value={position.value} key={position.value}>
                {position.label}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="secondary-button"
          disabled={!activeFiltersCount || loading}
          onClick={resetFilters}
        >
          Réinitialiser
        </button>
      </div>

      <div className="match-feed">
        {groups.map((group) => (
          <div className="day-group" key={group.key}>
            <div className="day-header">{group.label}</div>
            {group.matches.map((match) => {
              const isSelected = selectedMatchId === match.match_id;
              const bluePlayers = match.participants.filter((player) => player.team_id === 100);
              const redPlayers = match.participants.filter((player) => player.team_id === 200);

              return (
                <article
                  key={match.match_id}
                  className={`match-card ${ match.advanced_stats.game_ended_in_early_surrender ? "surrender": (match.win ? "is-win" : "is-loss")} ${isSelected ? "is-selected" : ""}  `}
                  onClick={() => onSelectMatch(match)}
                >
                  <div className="match-summary">
                    <div className="match-lane">
                      <span className="result-chip">{match.win ? "Victoire" : "Défaite"}</span>
                      <small style={"align-content:center"}>{formatTime(match.end_time)}</small>
                      <small>{match.queue_name}</small>
                    </div>

                    <div className="match-champion">
                      <div className="match-champion-title">
                        {match.champion_image_url ? (
                          <img className="champion-icon champion-icon-lg" src={match.champion_image_url} alt={match.champion} />
                        ) : null}
                        <div className="match-champion-heading">
                          <strong>{match.champion}</strong>
                          {match.rank_label ? <span className="rank-badge">{match.rank_label}</span> : null}
                        </div>
                      </div>
                      <span>{match.position || "Inconnue"}</span>
                    </div>

                    <div className="match-kda">
                      <strong>
                        {match.kills}/{match.deaths}/{match.assists}
                      </strong>
                      <span>{match.kda_ratio} KDA</span>
                    </div>

                    <div className="match-meta">
                      <span>{match.kill_participation}% KP</span>
                      <span>{match.vision_score} vision</span>
                      <span>{formatDuration(match.game_duration)}</span>
                    </div>

                    <div className="match-items">
                      {match.items.map((item, index) =>
                        item?.image_url ? (
                          <img
                            className="item-icon"
                            key={`${match.match_id}-${index}`}
                            src={item.image_url}
                            alt={item.name || `Objet ${index + 1}`}
                          />
                        ) : (
                          <span className="item-dot" key={`${match.match_id}-${index}`}>
                            -
                          </span>
                        ),
                      )}
                    </div>
                  </div>

                  {isSelected ? (
                    <div className="match-expanded">
                      <TeamRoster title="Équipe bleue" players={bluePlayers} />
                      <TeamRoster title="Équipe rouge" players={redPlayers} />
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ))}

        {!matches.length && !loading ? <p className="empty-inline">Aucun match local à afficher.</p> : null}
      </div>

      <div className="pagination-row">
        <button
          type="button"
          className="secondary-button"
          disabled={!pagination.previous || loading}
          onClick={() => onPageChange(getNextPageNumber(pagination.previous))}
        >
          Précédent
        </button>
        <span>Page {pagination.page}</span>
        <button
          type="button"
          className="secondary-button"
          disabled={!pagination.next || loading}
          onClick={() => onPageChange(getNextPageNumber(pagination.next))}
        >
          Suivant
        </button>
      </div>
    </section>
  );
}

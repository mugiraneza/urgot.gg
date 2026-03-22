function splitTeams(participants = []) {
  return {
    blue: participants.filter((player) => player.team_id === 100),
    red: participants.filter((player) => player.team_id === 200),
  };
}

export function MatchDetailPanel({ match }) {
  if (!match) {
    return (
      <aside className="card detail-panel">
        <p className="eyebrow">Détail</p>
        <h2>Sélectionne une partie</h2>
        <p className="muted">Clique sur une ligne pour afficher les participants, les scores et les infos de vision.</p>
      </aside>
    );
  }

  const teams = splitTeams(match.participants);

  return (
    <aside className="card detail-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Partie</p>
          <h2>{match.champion}</h2>
        </div>
        <span className="pill">{match.position || "UNKNOWN"}</span>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <span>KDA</span>
          <strong>
            {match.kills}/{match.deaths}/{match.assists}
          </strong>
        </div>
        <div className="metric-card">
          <span>Ratio</span>
          <strong>{match.kda_ratio}</strong>
        </div>
        <div className="metric-card">
          <span>KP</span>
          <strong>{match.kill_participation}%</strong>
        </div>
        <div className="metric-card">
          <span>Vision</span>
          <strong>{match.vision_score}</strong>
        </div>
      </div>

      <div className="team-columns">
        <div>
          <h3>Blue side</h3>
          <ul className="roster-list">
            {teams.blue.map((player) => (
              <li key={`${match.match_id}-${player.riot_name}`}>
                <span>{player.champion}</span>
                <strong>{player.riot_name}</strong>
                <small>
                  {player.kills}/{player.deaths}/{player.assists}
                </small>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3>Red side</h3>
          <ul className="roster-list">
            {teams.red.map((player) => (
              <li key={`${match.match_id}-${player.riot_name}`}>
                <span>{player.champion}</span>
                <strong>{player.riot_name}</strong>
                <small>
                  {player.kills}/{player.deaths}/{player.assists}
                </small>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </aside>
  );
}

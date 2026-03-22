function statValue(value) {
  return value || "N/A";
}

export function StatsOverview({ stats, query, activeMatch }) {
  return (
    <section className="profile-card">
      <div className="profile-header">
        <div className="avatar-ring">{(query.value || "U").slice(0, 2).toUpperCase()}</div>
        <div>
          <p className="eyebrow">Profil</p>
          <h3>{query.value || "Joueur local"}</h3>
          <p className="muted"> palceholder</p> 
        </div>
      </div>

      <div className="profile-highlight">
        <div>
          <span>Games</span>
          <strong>{statValue(stats?.games_analyzed)}</strong>
        </div>
        <div>
          <span>Temps</span>
          <strong>{statValue(stats?.total_time_played)}</strong>
        </div>
      </div>

      {activeMatch ? (
        <div className="focus-card">
          <p className="eyebrow">Partie sélectionnée</p>
          <div className="focus-title">
            {activeMatch.champion_image_url ? (
              <img className="champion-icon champion-icon-lg" src={activeMatch.champion_image_url} alt={activeMatch.champion} />
            ) : null}
            <h3>{activeMatch.champion}</h3>
          </div>
          <div className="focus-kda">
            <strong>
              {activeMatch.kills}/{activeMatch.deaths}/{activeMatch.assists}
            </strong>
            <span>{activeMatch.queue_name}</span>
          </div>
          <div className="focus-meta">
            <span>{activeMatch.position || "UNKNOWN"}</span>
            <span>{activeMatch.kill_participation}% KP</span>
            <span>{activeMatch.kda_ratio} KDA</span>
          </div>
        </div>
      ) : null}

      <div className="mini-stat-list">
        <div className="mini-stat">
          <span>People met</span>
          <strong>{statValue(stats?.people_met)}</strong>
        </div>
        {/* <div className="mini-stat">
          <span>Nouveaux / game</span>
          <strong>{statValue(stats?.avg_new_people_per_game)}</strong>
        </div>
        <div className="mini-stat">
          <span>Anciennes connaissances</span>
          <strong>{statValue(stats?.avg_old_friends_per_game)}</strong>
        </div> */}
      </div>
    </section>
  );
}

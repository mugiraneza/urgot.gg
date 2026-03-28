function statValue(value) {
  return value || "N/A";
}

function buildRankIconUrl(rankTier) {
  if (!rankTier) {
    return null;
  }
  const normalizedTier = `${rankTier}`.trim();
  return `/api/assets/elo/elo/Rank=${normalizedTier}.png`;
}

function WinrateChart({ winrate = 0 }) {
  const safeWinrate = Math.max(0, Math.min(100, Number(winrate) || 0));

  return (
    <div className="winrate-card">
      <div className="winrate-chart" aria-label={`Taux de victoire de ${safeWinrate.toFixed(1)} pour cent`}>
        <svg viewBox="0 0 36 36" className="circular-chart">
          <path
            className="circle-bg"
            d="M18 2.0845
              a 15.9155 15.9155 0 0 1 0 31.831
              a 15.9155 15.9155 0 0 1 0 -31.831"
          />
          <path
            className="circle"
            style={{ strokeDasharray: `${safeWinrate}, 100` }}
            d="M18 2.0845
              a 15.9155 15.9155 0 0 1 0 31.831
              a 15.9155 15.9155 0 0 1 0 -31.831"
          />
        </svg>
        <div className="winrate-chart-center">
          <strong>{Math.round(safeWinrate)}%</strong>
        </div>
      </div>
    </div>
  );
}

export function StatsOverview({ stats, query, activeMatch }) {
  const eloLabel = stats?.player_elo || activeMatch?.rank_label || "Elo inconnu";
  const eloIconUrl = stats?.player_elo_icon_url || buildRankIconUrl(activeMatch?.rank_tier);

  return (
    <section className="profile-card">
      <div className="profile-header">
        <div className="avatar-ring">{(query.value || "U").slice(0, 2).toUpperCase()}</div>
        <div>
          <p className="eyebrow">Profil</p>
          <h3>{query.value || "Joueur local"}</h3>
          <div className="profile-rank-row">
            {eloIconUrl ? <img className="rank-emblem" src={eloIconUrl} alt={eloLabel} /> : null}
            <p className="muted">{eloLabel}</p>
          </div>
        </div>
      </div>

      <div className="profile-highlight">
        <WinrateChart winrate={stats?.winrate} />
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
            <span>{activeMatch.position || "Inconnue"}</span>
            <span>{activeMatch.kill_participation}% KP</span>
            <span>{activeMatch.kda_ratio} KDA</span>
          </div>
        </div>
      ) : null}

      <div className="mini-stat-list">
        <div className="mini-stat">
          <span>Joueurs rencontrés</span>
          <strong>{statValue(stats?.people_met)}</strong>
        </div>
      </div>
    </section>
  );
}

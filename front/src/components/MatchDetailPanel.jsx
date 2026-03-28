function splitTeams(participants = []) {
  return {
    blue: participants.filter((player) => player.team_id === 100),
    red: participants.filter((player) => player.team_id === 200),
  };
}

function formatValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return `${value}${suffix}`;
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toFixed(digits);
}

function renderRuneTree(styleId, selections) {
  if (!styleId && (!selections || !selections.length)) {
    return "-";
  }
  const perks = selections?.length ? selections.join(" / ") : "-";
  return `${styleId} -> ${perks}`;
}

function renderSkillOrder(skillOrder = []) {
  if (!skillOrder.length) {
    return "-";
  }
  const labels = { 1: "Q", 2: "W", 3: "E", 4: "R" };
  return skillOrder.map((slot) => labels[slot] || slot).join(" > ");
}

function renderPingStats(pingStats = {}) {
  const entries = Object.entries(pingStats).filter(([, value]) => value !== null && value !== undefined && value !== 0);
  if (!entries.length) {
    return "Aucun ping notable";
  }
  return entries
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}: ${value}`)
    .join(" | ");
}

function StatList({ title, stats }) {
  const filteredStats = stats.filter((stat) => stat.value !== undefined);
  if (!filteredStats.length) {
    return null;
  }

  return (
    <section className="detail-block">
      <h3>{title}</h3>
      <div className="detail-stat-grid">
        {filteredStats.map((stat) => (
          <div className="detail-stat-card" key={`${title}-${stat.label}`}>
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

export function MatchDetailPanel({ match }) {
  if (!match) {
    return (
      <aside className="card detail-panel">
        <p className="eyebrow">Détail</p>
        <h2>Sélectionne une partie</h2>
        <p className="muted">Clique sur une ligne pour afficher les participants, les statistiques avancées et les runes.</p>
      </aside>
    );
  }

  splitTeams(match.participants);
  const details = match.advanced_stats || {};

  return (
    <aside className="card detail-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Partie</p>
          <h2>{match.champion}</h2>
          {match.rank_label ? <p className="muted rank-line">{match.rank_label}</p> : null}
        </div>
        <span className="pill">{match.position || "Inconnue"}</span>
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

      <StatList
        title="Objectifs et impact"
        stats={[
          { label: "Dégâts objectifs", value: formatValue(details.damage_dealt_to_objectives) },
          { label: "Dégâts tourelles", value: formatValue(details.damage_dealt_to_turrets) },
          { label: "Tourelles", value: formatValue(details.turret_kills) },
          { label: "Inhibiteurs", value: formatValue(details.inhibitor_kills) },
          { label: "Destructions inhib.", value: formatValue(details.inhibitor_takedowns) },
          { label: "Objectifs volés", value: formatValue(details.objectives_stolen) },
          { label: "Assistances sur vols", value: formatValue(details.objectives_stolen_assists) },
          { label: "Boucliers alliés", value: formatValue(details.total_damage_shielded_on_teammates) },
          { label: "Soins alliés", value: formatValue(details.total_heals_on_teammates) },
        ]}
      />

      <StatList
        title="Vision"
        stats={[
          { label: "Score de vision", value: formatValue(details.vision_score) },
          { label: "Balises posées", value: formatValue(details.wards_placed) },
          { label: "Balises de contrôle posées", value: formatValue(details.detector_wards_placed) },
          { label: "Balises de contrôle achetées", value: formatValue(details.vision_wards_bought_in_game) },
          { label: "Balises détruites", value: formatValue(details.wards_killed) },
          { label: "Balises furtives", value: formatValue(details.stealth_wards_placed) },
          { label: "Avantage vision de lane", value: formatNumber(details.vision_score_advantage_lane_opponent) },
        ]}
      />

      <StatList
        title="Lane et early"
        stats={[
          { label: "Lane", value: formatValue(details.lane) },
          { label: "SoloKills", value: formatValue(details.solo_kills) },
          { label: "Séries", value: formatValue(details.killing_sprees) },
          { label: "+ Grande série", value: formatValue(details.largest_killing_spree) },
          { label: "multi-kill", value: formatValue(details.largest_multi_kill) },
          { label: "CS /10", value: formatNumber(details.lane_minions_first_10_minutes) },
          { label: "CS jgl/10", value: formatNumber(details.jungle_cs_before_10_minutes) },
          { label: "Or/min", value: formatNumber(details.gold_per_minute) },
          { label: "Dégâts/min", value: formatNumber(details.damage_per_minute) },
        ]}
      />

      <StatList
        title="Déroulé de partie"
        stats={[
          { label: "Transf.", value: formatValue(details.champion_transform) },
          { label: "ff", value: formatValue(details.team_early_surrendered === null ? null : details.team_early_surrendered ? "Oui" : "Non") },
          { label: "Fin rapide ff", value: formatValue(details.game_ended_in_early_surrender === null ? null : details.game_ended_in_early_surrender ? "Oui" : "Non") },
          { label: "Fin par abandon", value: formatValue(details.game_ended_in_surrender === null ? null : details.game_ended_in_surrender ? "Oui" : "Non") },
          { label: "Temps max en vie", value: formatValue(details.longest_time_spent_living, "s") },
          { label: "CC infligé", value: formatValue(details.total_time_cc_dealt) },
          { label: "CC sur ennemis", value: formatValue(details.time_ccing_others) },
          { label: "Temps joué", value: formatValue(details.time_played, "s") },
        ]}
      />

      {/* <section className="detail-block">
        <h3>Runes et progression</h3>
        <div className="detail-copy">
          <p><strong>Primaire:</strong> {renderRuneTree(details.primary_rune_style, details.primary_rune_selections)}</p>
          <p><strong>Secondaire:</strong> {renderRuneTree(details.secondary_rune_style, details.secondary_rune_selections)}</p>
          <p><strong>Shards:</strong> {details.stat_perks && Object.keys(details.stat_perks).length ? JSON.stringify(details.stat_perks) : "-"}</p>
          <p><strong>Ordre des sorts:</strong> {renderSkillOrder(details.skill_order)}</p>
        </div>
      </section>

      <section className="detail-block">
        <h3>Pings</h3>
        <div className="detail-copy">
          <p><strong>Appât:</strong> {formatValue(details.bait_pings)}</p>
          <p><strong>Danger:</strong> {formatValue(details.danger_pings)}</p>
          <p><strong>Repli:</strong> {formatValue(details.get_back_pings)}</p>
          <p><strong>Tous:</strong> {renderPingStats(details.ping_stats)}</p>
        </div>
      </section> */}
    </aside>
  );
}

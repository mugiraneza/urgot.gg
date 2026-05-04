import { useState } from "preact/hooks";

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

const MATCH_TABS = [
  { id: "teams", label: "Equipes" },
  { id: "overview", label: "Resume" },
  { id: "impact", label: "Impact" },
  { id: "vision", label: "Vision" },
  { id: "progression", label: "Progression" },
];

export function MatchDetailPanel({ match, embedded = false }) {
  const [activeTab, setActiveTab] = useState("teams");

  if (!match) {
    return embedded ? null : (
      <aside className="card detail-panel">
        <p className="eyebrow">Detail</p>
        <h2>Selectionne une partie</h2>
        <p className="muted">Clique sur une ligne pour afficher les participants, les statistiques avancees et les runes.</p>
      </aside>
    );
  }

  const details = match.advanced_stats || {};
  const teams = splitTeams(match.participants);
  const WrapperTag = embedded ? "div" : "aside";
  const wrapperClassName = embedded ? "match-detail-tabs" : "card detail-panel";

  return (
    <WrapperTag className={wrapperClassName}>
      {!embedded ? (
        <div className="section-header">
          <div>
            <p className="eyebrow">Partie</p>
            <h2>{match.champion}</h2>
            {match.rank_label ? <p className="muted rank-line">{match.rank_label}</p> : null}
          </div>
          <span className="pill">{match.position || "Inconnue"}</span>
        </div>
      ) : null}

      <div className="match-tab-strip" role="tablist" aria-label="Details de la partie">
        {MATCH_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            className={`match-tab-button ${activeTab === tab.id ? "is-active" : ""}`}
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "teams" ? (
        <div className="match-expanded match-expanded-tabs">
          <TeamRoster title="Equipe bleue" players={teams.blue} />
          <TeamRoster title="Equipe rouge" players={teams.red} />
        </div>
      ) : null}

      {activeTab === "overview" ? (
        <div className="tab-panel-grid">
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
            title="Lane et early"
            stats={[
              { label: "Lane", value: formatValue(details.lane) },
              { label: "Solo kills", value: formatValue(details.solo_kills) },
              { label: "Series", value: formatValue(details.killing_sprees) },
              { label: "Plus grande serie", value: formatValue(details.largest_killing_spree) },
              { label: "Multi-kill", value: formatValue(details.largest_multi_kill) },
              { label: "CS /10", value: formatNumber(details.lane_minions_first_10_minutes) },
              { label: "CS jgl/10", value: formatNumber(details.jungle_cs_before_10_minutes) },
              { label: "Or/min", value: formatNumber(details.gold_per_minute) },
              { label: "Degats/min", value: formatNumber(details.damage_per_minute) },
            ]}
          />

          <StatList
            title="Deroule de partie"
            stats={[
              { label: "Temps joue", value: formatValue(details.time_played, "s") },
              { label: "Fin rapide ff", value: formatValue(details.game_ended_in_early_surrender === null ? null : details.game_ended_in_early_surrender ? "Oui" : "Non") },
              { label: "Fin par abandon", value: formatValue(details.game_ended_in_surrender === null ? null : details.game_ended_in_surrender ? "Oui" : "Non") },
              { label: "Equipe ff", value: formatValue(details.team_early_surrendered === null ? null : details.team_early_surrendered ? "Oui" : "Non") },
              { label: "Temps max en vie", value: formatValue(details.longest_time_spent_living, "s") },
              { label: "CC inflige", value: formatValue(details.total_time_cc_dealt) },
            ]}
          />
        </div>
      ) : null}

      {activeTab === "impact" ? (
        <div className="tab-panel-grid">
          <StatList
            title="Objectifs et impact"
            stats={[
              { label: "Degats objectifs", value: formatValue(details.damage_dealt_to_objectives) },
              { label: "Degats tourelles", value: formatValue(details.damage_dealt_to_turrets) },
              { label: "Tourelles", value: formatValue(details.turret_kills) },
              { label: "Inhibiteurs", value: formatValue(details.inhibitor_kills) },
              { label: "Destructions inhib.", value: formatValue(details.inhibitor_takedowns) },
              { label: "Objectifs voles", value: formatValue(details.objectives_stolen) },
              { label: "Assistances sur vols", value: formatValue(details.objectives_stolen_assists) },
            ]}
          />

          <StatList
            title="Combat et tenue"
            stats={[
              { label: "Degats champions", value: formatValue(details.total_damage_dealt_champs) },
              { label: "Degats subis", value: formatValue(details.total_damage_taken) },
              { label: "Auto-mitigation", value: formatValue(details.damage_self_mitigated) },
              { label: "Soins", value: formatValue(details.total_heal) },
              { label: "Boucliers allies", value: formatValue(details.total_damage_shielded_on_teammates) },
              { label: "Soins allies", value: formatValue(details.total_heals_on_teammates) },
            ]}
          />
        </div>
      ) : null}

      {activeTab === "vision" ? (
        <div className="tab-panel-grid">
          <StatList
            title="Vision"
            stats={[
              { label: "Score de vision", value: formatValue(details.vision_score) },
              { label: "Balises posees", value: formatValue(details.wards_placed) },
              { label: "Balises de controle posees", value: formatValue(details.detector_wards_placed) },
              { label: "Balises de controle achetees", value: formatValue(details.vision_wards_bought_in_game) },
              { label: "Balises detruites", value: formatValue(details.wards_killed) },
              { label: "Balises furtives", value: formatValue(details.stealth_wards_placed) },
              { label: "Avantage de lane", value: formatNumber(details.vision_score_advantage_lane_opponent) },
            ]}
          />

          <section className="detail-block">
            <h3>Pings</h3>
            <div className="detail-copy">
              <p><strong>Appat:</strong> {formatValue(details.bait_pings)}</p>
              <p><strong>Danger:</strong> {formatValue(details.danger_pings)}</p>
              <p><strong>Repli:</strong> {formatValue(details.get_back_pings)}</p>
              <p><strong>Tous:</strong> {renderPingStats(details.ping_stats)}</p>
            </div>
          </section>
        </div>
      ) : null}

      {activeTab === "progression" ? (
        <div className="tab-panel-grid">
          <section className="detail-block">
            <h3>Runes et progression</h3>
            <div className="detail-copy">
              <p><strong>Primaire:</strong> {renderRuneTree(details.primary_rune_style, details.primary_rune_selections)}</p>
              <p><strong>Secondaire:</strong> {renderRuneTree(details.secondary_rune_style, details.secondary_rune_selections)}</p>
              <p><strong>Shards:</strong> {details.stat_perks && Object.keys(details.stat_perks).length ? JSON.stringify(details.stat_perks) : "-"}</p>
              <p><strong>Ordre des sorts:</strong> {renderSkillOrder(details.skill_order)}</p>
            </div>
          </section>

          <StatList
            title="Ressources"
            stats={[
              { label: "Niveau", value: formatValue(details.champ_level) },
              { label: "Experience", value: formatValue(details.champ_experience) },
              { label: "Or gagne", value: formatValue(details.gold_earned) },
              { label: "Or depense", value: formatValue(details.gold_spent) },
              { label: "CS lane", value: formatValue(details.total_minions_killed) },
              { label: "CS jungle", value: formatValue(details.neutral_minions_killed) },
            ]}
          />
        </div>
      ) : null}
    </WrapperTag>
  );
}

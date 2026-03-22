export function ChampionStatsTable({ rows }) {
  return (
    <section className="side-card">
      <div className="section-header compact">
        <div>
          <p className="eyebrow">Performance champion</p>
          <h2>Champion pool</h2>
        </div>
      </div>

      <div className="champion-list">
        {rows.map((row, index) => (
          <div className="champion-row" key={row.champion}>
            <span className="champion-rank">{index + 1}</span>
            <div className="champion-meta">
              <div className="champion-meta-title">
                {row.champion_image_url ? (
                  <img className="champion-icon" src={row.champion_image_url} alt={row.champion} />
                ) : null}
                <strong>{row.champion}</strong>
              </div>
              <small>
                {row.games} games • {row.win_rate}% WR
              </small>
            </div>
            <div className="champion-values">
              <span>{row.kda} KDA</span>
              <span>{row.cs_per_min} CS/min</span>
            </div>
          </div>
        ))}
        {!rows.length ? <p className="empty-inline">Aucune donnée champion.</p> : null}
      </div>
    </section>
  );
}

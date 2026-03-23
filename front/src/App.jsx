import { useMemo, useState } from "preact/hooks";
import { fetchFrontDashboard, fetchFrontMatches, triggerMatchImport } from "./api/client";
import { AppShell } from "./components/AppShell";
import { SearchPanel } from "./components/SearchPanel";
import { MatchesTable } from "./components/MatchesTable";
import { StatsOverview } from "./components/StatsOverview";
import { ChampionStatsTable } from "./components/ChampionStatsTable";
import { ChartCard } from "./components/ChartCard";

const DEFAULT_QUERY = {
  mode: "riot_name",
  value: "",
};

export function App() {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [matches, setMatches] = useState([]);
  const [matchesPagination, setMatchesPagination] = useState({ next: null, previous: null, count: 0, page: 1 });
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [globalStats, setGlobalStats] = useState(null);
  const [championStats, setChampionStats] = useState([]);
  const [modeStats, setModeStats] = useState([]);
  const [csEvolution, setCsEvolution] = useState([]);

  const hasQuery = query.value.trim().length > 0;
  const queryParams = useMemo(() => {
    if (!hasQuery) {
      return null;
    }
    return query.mode === "puuid"
      ? { puuid: query.value.trim() }
      : { riot_name: query.value.trim() };
  }, [hasQuery, query]);

  async function loadDashboard(nextPage = 1) {
    if (!queryParams) {
      setError("Renseigne un Riot ID ou un PUUID.");
      return;
    }

    setLoading(true);
    setError("");
    setInfo("");

    try {
      const [matchesResponse, dashboardResponse] = await Promise.all([
        fetchFrontMatches({ ...queryParams, page: nextPage }),
        fetchFrontDashboard(queryParams),
      ]);

      const matchResults = matchesResponse.results || [];
      setMatches(matchResults);
      setMatchesPagination({
        next: matchesResponse.next,
        previous: matchesResponse.previous,
        count: matchesResponse.count || 0,
        page: nextPage,
      });
      setSelectedMatchId((currentId) => {
        if (!currentId) {
          return matchResults[0]?.match_id || null;
        }
        const existsOnPage = matchResults.some((match) => match.match_id === currentId);
        return existsOnPage ? currentId : matchResults[0]?.match_id || null;
      });
      setGlobalStats(dashboardResponse.overview || null);
      setChampionStats(Array.isArray(dashboardResponse.champions) ? dashboardResponse.champions : []);
      setModeStats(Array.isArray(dashboardResponse.modes) ? dashboardResponse.modes : []);
      setCsEvolution(Array.isArray(dashboardResponse.cs_evolution) ? dashboardResponse.cs_evolution : []);
    } catch (loadError) {
      setError(loadError.message || "Impossible de charger le dashboard.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    if (!queryParams) {
      setError("Renseigne un Riot ID ou un PUUID.");
      return;
    }

    setLoading(true);
    setError("");
    setInfo("");

    try {
      if (query.mode === "riot_name") {
        const importResponse = await triggerMatchImport({
          riot_id: query.value.trim(),
          region: "europe",
        });
        setInfo(importResponse.message || "Import lancé en arrière-plan.");
      } else {
        setInfo("Actualisation locale lancée.");
      }

      const [matchesResponse, dashboardResponse] = await Promise.all([
        fetchFrontMatches({ ...queryParams, page: 1 }),
        fetchFrontDashboard(queryParams),
      ]);

      const matchResults = matchesResponse.results || [];
      setMatches(matchResults);
      setMatchesPagination({
        next: matchesResponse.next,
        previous: matchesResponse.previous,
        count: matchesResponse.count || 0,
        page: 1,
      });
      setSelectedMatchId(matchResults[0]?.match_id || null);
      setGlobalStats(dashboardResponse.overview || null);
      setChampionStats(Array.isArray(dashboardResponse.champions) ? dashboardResponse.champions : []);
      setModeStats(Array.isArray(dashboardResponse.modes) ? dashboardResponse.modes : []);
      setCsEvolution(Array.isArray(dashboardResponse.cs_evolution) ? dashboardResponse.cs_evolution : []);
    } catch (refreshError) {
      setError(refreshError.message || "Impossible d'actualiser les données.");
    } finally {
      setLoading(false);
    }
  }

  const activeMatch = matches.find((match) => match.match_id === selectedMatchId) || matches[0] || null;

  return (
    <AppShell loading={loading} playerLabel={query.value}>
      <SearchPanel
        query={query}
        onQueryChange={setQuery}
        onSubmit={() => loadDashboard(1)}
        onRefresh={handleRefresh}
        loading={loading}
      />

      {error ? <div className="alert alert-error">{error}</div> : null}
      {info ? <div className="alert alert-info">{info}</div> : null}

      {!hasQuery ? (
        <div className="empty-state">
          <h2>Profil local</h2>
          <p>Charge un joueur pour afficher l’historique stocké dans ta base locale et les statistiques calculées par tes endpoints internes.</p>
        </div>
      ) : null}

      {hasQuery ? (
        <section className="opgg-layout">
          <aside className="left-rail">
            <StatsOverview stats={globalStats} query={query} activeMatch={activeMatch} />
            <ChartCard
              title="Répartition des parties"
              subtitle="Base locale"
              type="doughnut"
              data={{
                labels: modeStats.map((mode) => mode.queue_name || `Queue ${mode.queue}`),
                datasets: [
                  {
                    label: "Games",
                    data: modeStats.map((mode) => mode.total_games),
                    backgroundColor: ["#5b8cff", "#9f7aea", "#f6ad55", "#63b3ed", "#f56565", "#68d391"],
                    borderWidth: 0,
                  },
                ],
              }}
            />
            <ChampionStatsTable rows={championStats.slice(0, 8)} />
            <ChartCard
              title="CS / min"
              subtitle="Tendance récente"
              type="line"
              data={{
                labels: csEvolution.slice(-12).map((entry) => `${entry.champion} ${entry.date.slice(5, 10)}`),
                datasets: [
                  {
                    label: "CS/min",
                    data: csEvolution.slice(-12).map((entry) => entry.cs_per_min),
                    borderColor: "#6ea8fe",
                    backgroundColor: "rgba(110,168,254,0.14)",
                    borderWidth: 2,
                    tension: 0.35,
                    fill: true,
                  },
                ],
              }}
            />
          </aside>

          <div className="matchs-rail">
            <MatchesTable
              matches={matches}
              pagination={matchesPagination}
              selectedMatchId={selectedMatchId}
              onSelectMatch={(match) => setSelectedMatchId(match.match_id)}
              onPageChange={(page) => loadDashboard(page)}
              loading={loading}
            />
          </div>
        </section>
      ) : null}
    </AppShell>
  );
}

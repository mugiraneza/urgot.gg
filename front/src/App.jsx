import { useEffect, useMemo, useState } from "preact/hooks";
import { fetchFrontDashboard, fetchFrontMatchDetail, fetchFrontMatches, fetchRecentRiotIds, triggerMatchImport } from "./api/client";
import { AppShell } from "./components/AppShell";
import { SearchPanel } from "./components/SearchPanel";
import { MatchesTable } from "./components/MatchesTable";
import { StatsOverview } from "./components/StatsOverview";
import { ChampionStatsTable } from "./components/ChampionStatsTable";
import { ChartCard } from "./components/ChartCard";

const DEFAULT_QUERY = {
  mode: "riot_name",
  value: "",
  region: "europe",
};

const REGION_OPTIONS = [
  { value: "europe", label: "Europe" },
  { value: "americas", label: "Americas" },
  { value: "asia", label: "Asia" },
  { value: "sea", label: "SEA" },
];

const DEFAULT_MATCH_FILTERS = {
  queue: "",
  championName: "",
  position: "",
};

const POSITION_OPTIONS = [
  { value: "TOP", label: "Top" },
  { value: "JUNGLE", label: "Jungle" },
  { value: "MIDDLE", label: "Mid" },
  { value: "BOTTOM", label: "Bot" },
  { value: "UTILITY", label: "Support" },
];

function hasActiveMatchFilters(filters) {
  return Boolean(filters.queue || filters.championName || filters.position);
}

function buildMatchFilterParams(filters) {
  return {
    queue: filters.queue,
    champion_name: filters.championName,
    position: filters.position,
  };
}

function matchesFilters(match, filters) {
  if (filters.queue && String(match.queue) !== filters.queue) {
    return false;
  }

  if (filters.championName && `${match.champion || ""}`.toLowerCase() !== filters.championName.toLowerCase()) {
    return false;
  }

  if (filters.position && `${match.position || ""}`.toUpperCase() !== filters.position) {
    return false;
  }

  return true;
}

function filterMatchesLocally(matchList, filters) {
  if (!hasActiveMatchFilters(filters)) {
    return matchList;
  }

  return matchList.filter((match) => matchesFilters(match, filters));
}

const RECENT_RIOT_IDS_STORAGE_KEY = "urgot_recent_riot_ids";
const RECENT_RIOT_IDS_LIMIT = 8;
const DASHBOARD_CACHE_PREFIX = "urgot_dashboard_cache_v1";
const MATCHES_CACHE_PREFIX = "urgot_matches_cache_v1";
const MATCH_DETAIL_CACHE_PREFIX = "urgot_match_detail_cache_v1";

function normalizeRecentRiotIds(values) {
  const recentIds = Array.isArray(values) ? values : [];
  const deduped = [];
  const seen = new Set();

  recentIds.forEach((value) => {
    const normalizedValue = `${value || ""}`.trim();
    const normalizedKey = normalizedValue.toLowerCase();
    if (!normalizedValue || seen.has(normalizedKey)) {
      return;
    }
    seen.add(normalizedKey);
    deduped.push(normalizedValue);
  });

  return deduped.slice(0, RECENT_RIOT_IDS_LIMIT);
}

function readRecentRiotIdsFromStorage() {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const rawValue = window.localStorage.getItem(RECENT_RIOT_IDS_STORAGE_KEY);
    if (!rawValue) {
      return [];
    }
    return normalizeRecentRiotIds(JSON.parse(rawValue));
  } catch {
    return [];
  }
}

function writeRecentRiotIdsToStorage(values) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(
      RECENT_RIOT_IDS_STORAGE_KEY,
      JSON.stringify(normalizeRecentRiotIds(values)),
    );
  } catch {
    // Ignore storage failures and keep the in-memory state.
  }
}

function safeReadJson(key) {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const rawValue = window.localStorage.getItem(key);
    return rawValue ? JSON.parse(rawValue) : null;
  } catch {
    return null;
  }
}

function safeWriteJson(key, value) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage failures and keep the in-memory state.
  }
}

function buildQueryCacheKey(queryParams) {
  if (!queryParams) {
    return "";
  }

  return Object.entries(queryParams)
    .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
    .map(([key, value]) => `${key}:${value}`)
    .join("|");
}

function buildMatchesCacheKey(queryParams, page, filters, remoteFilters) {
  return [
    MATCHES_CACHE_PREFIX,
    buildQueryCacheKey(queryParams),
    `page:${page}`,
    `queue:${filters.queue || ""}`,
    `champion:${filters.championName || ""}`,
    `position:${filters.position || ""}`,
    `remote:${remoteFilters ? "1" : "0"}`,
  ].join("|");
}

function buildDashboardCacheKey(queryParams) {
  return [DASHBOARD_CACHE_PREFIX, buildQueryCacheKey(queryParams)].join("|");
}

function buildMatchDetailCacheKey(queryParams, matchId) {
  return [MATCH_DETAIL_CACHE_PREFIX, buildQueryCacheKey(queryParams), matchId].join("|");
}

export function App() {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [matches, setMatches] = useState([]);
  const [pageMatches, setPageMatches] = useState([]);
  const [remoteFilteredMatches, setRemoteFilteredMatches] = useState(false);
  const [matchesPagination, setMatchesPagination] = useState({ next: null, previous: null, count: 0, page: 1 });
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [matchDetailsById, setMatchDetailsById] = useState({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [globalStats, setGlobalStats] = useState(null);
  const [championStats, setChampionStats] = useState([]);
  const [modeStats, setModeStats] = useState([]);
  const [csEvolution, setCsEvolution] = useState([]);
  const [lpEvolution, setLpEvolution] = useState([]);
  const [recentRiotIds, setRecentRiotIds] = useState(() => readRecentRiotIdsFromStorage());
  const [matchFilters, setMatchFilters] = useState(DEFAULT_MATCH_FILTERS);

  const hasQuery = query.value.trim().length > 0;
  const queryParams = useMemo(() => {
    if (!hasQuery) {
      return null;
    }
    return query.mode === "puuid"
      ? { puuid: query.value.trim() }
      : { riot_name: query.value.trim() };
  }, [hasQuery, query]);

  const matchFilterOptions = useMemo(
    () => ({
      modes: modeStats.map((mode) => ({
        value: String(mode.queue),
        label: mode.queue_name || `File ${mode.queue}`,
        count: mode.total_games,
      })),
      champions: championStats.map((champion) => ({
        value: champion.champion,
        label: champion.champion,
        count: champion.games,
      })),
      positions: POSITION_OPTIONS,
    }),
    [championStats, modeStats],
  );

  function updateRecentRiotIds(nextValues) {
    const normalizedValues = normalizeRecentRiotIds(nextValues);
    setRecentRiotIds(normalizedValues);
    writeRecentRiotIdsToStorage(normalizedValues);
  }

  function pushRecentRiotId(riotId) {
    const normalizedValue = `${riotId || ""}`.trim();
    if (!normalizedValue) {
      return;
    }

    const currentValues = readRecentRiotIdsFromStorage();
    updateRecentRiotIds([normalizedValue, ...currentValues, ...recentRiotIds]);
  }

  async function loadRecentRiotIds() {
    try {
      const response = await fetchRecentRiotIds();
      updateRecentRiotIds([...(Array.isArray(response?.results) ? response.results : []), ...readRecentRiotIdsFromStorage()]);
    } catch {
      updateRecentRiotIds(readRecentRiotIdsFromStorage());
    }
  }

  useEffect(() => {
    loadRecentRiotIds();
  }, []);

  function selectVisibleMatch(matchResults) {
    setSelectedMatchId((currentId) => {
      if (!currentId) {
        return matchResults[0]?.match_id || null;
      }
      const existsOnPage = matchResults.some((match) => match.match_id === currentId);
      return existsOnPage ? currentId : matchResults[0]?.match_id || null;
    });
  }

  function applyCachedMatches(cacheEntry) {
    if (!cacheEntry) {
      return false;
    }

    const cachedResults = Array.isArray(cacheEntry.matches) ? cacheEntry.matches : [];
    const cachedPageMatches = Array.isArray(cacheEntry.pageMatches) ? cacheEntry.pageMatches : cachedResults;

    setPageMatches(cachedPageMatches);
    setRemoteFilteredMatches(Boolean(cacheEntry.remoteFilteredMatches));
    setMatches(cachedResults);
    setMatchesPagination(
      cacheEntry.pagination || { next: null, previous: null, count: cachedResults.length, page: 1 },
    );
    selectVisibleMatch(cachedResults);
    return true;
  }

  function applyCachedDashboard(cacheEntry) {
    if (!cacheEntry) {
      return false;
    }

    setGlobalStats(cacheEntry.overview || null);
    setChampionStats(Array.isArray(cacheEntry.champions) ? cacheEntry.champions : []);
    setModeStats(Array.isArray(cacheEntry.modes) ? cacheEntry.modes : []);
    setCsEvolution(Array.isArray(cacheEntry.cs_evolution) ? cacheEntry.cs_evolution : []);
    setLpEvolution(Array.isArray(cacheEntry.lp_evolution) ? cacheEntry.lp_evolution : []);
    return true;
  }

  function resetLoadedMatchDetails() {
    setMatchDetailsById({});
    setDetailLoading(false);
    setDetailError("");
  }

  async function loadMatchDetail(matchId, nextQueryParams = queryParams) {
    if (!matchId || !nextQueryParams) {
      return;
    }

    const cacheKey = buildMatchDetailCacheKey(nextQueryParams, matchId);
    const cachedDetail = safeReadJson(cacheKey);

    if (cachedDetail) {
      setMatchDetailsById((current) => ({
        ...current,
        [matchId]: cachedDetail,
      }));
    } else if (matchDetailsById[matchId]) {
      setDetailError("");
      setDetailLoading(false);
      return;
    }

    setDetailLoading(true);
    setDetailError("");

    try {
      const matchDetail = await fetchFrontMatchDetail(matchId, nextQueryParams);
      setMatchDetailsById((current) => ({
        ...current,
        [matchId]: matchDetail,
      }));
      safeWriteJson(cacheKey, matchDetail);
    } catch (loadError) {
      setDetailError(loadError.message || "Impossible de charger les details de cette partie.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function loadDashboard(nextPage = 1, nextMatchFilters = matchFilters, options = {}) {
    if (!queryParams) {
      setError("Renseigne un Riot ID ou un PUUID.");
      return;
    }

    if (query.mode === "riot_name") {
      pushRecentRiotId(query.value);
    }

    const useRemoteFilters = Boolean(options.remoteFilters);
    const matchesCacheKey = buildMatchesCacheKey(queryParams, nextPage, nextMatchFilters, useRemoteFilters);
    const dashboardCacheKey = buildDashboardCacheKey(queryParams);
    const hasCachedMatches = applyCachedMatches(safeReadJson(matchesCacheKey));
    const hasCachedDashboard = applyCachedDashboard(safeReadJson(dashboardCacheKey));

    setLoading(true);
    setError("");
    setInfo(hasCachedMatches || hasCachedDashboard ? "Affichage du cache local, mise a jour en cours..." : "");
    resetLoadedMatchDetails();

    try {
      const matchParams = useRemoteFilters ? buildMatchFilterParams(nextMatchFilters) : {};
      const [matchesResult, dashboardResult] = await Promise.allSettled([
        fetchFrontMatches({ ...queryParams, ...matchParams, page: nextPage }),
        fetchFrontDashboard(queryParams),
      ]);

      if (matchesResult.status === "fulfilled") {
        const matchesResponse = matchesResult.value;
        const matchResults = matchesResponse.results || [];
        const visibleMatches = useRemoteFilters ? matchResults : filterMatchesLocally(matchResults, nextMatchFilters);

        if (!useRemoteFilters) {
          setPageMatches(matchResults);
        }
        setRemoteFilteredMatches(useRemoteFilters);
        setMatches(visibleMatches);
        setMatchesPagination({
          next: matchesResponse.next,
          previous: matchesResponse.previous,
          count: matchesResponse.count || 0,
          page: nextPage,
        });
        selectVisibleMatch(visibleMatches);
        safeWriteJson(matchesCacheKey, {
          matches: visibleMatches,
          pageMatches: matchResults,
          remoteFilteredMatches: useRemoteFilters,
          pagination: {
            next: matchesResponse.next,
            previous: matchesResponse.previous,
            count: matchesResponse.count || 0,
            page: nextPage,
          },
        });
      } else {
        setMatches([]);
        setPageMatches([]);
        setMatchesPagination({ next: null, previous: null, count: 0, page: nextPage });
        setSelectedMatchId(null);
      }

      if (dashboardResult.status === "fulfilled") {
        const dashboardResponse = dashboardResult.value;
        setGlobalStats(dashboardResponse.overview || null);
        setChampionStats(Array.isArray(dashboardResponse.champions) ? dashboardResponse.champions : []);
        setModeStats(Array.isArray(dashboardResponse.modes) ? dashboardResponse.modes : []);
        setCsEvolution(Array.isArray(dashboardResponse.cs_evolution) ? dashboardResponse.cs_evolution : []);
        setLpEvolution(Array.isArray(dashboardResponse.lp_evolution) ? dashboardResponse.lp_evolution : []);
        safeWriteJson(dashboardCacheKey, dashboardResponse);
      } else {
        setGlobalStats(null);
        setChampionStats([]);
        setModeStats([]);
        setCsEvolution([]);
        setLpEvolution([]);
      }

      if (matchesResult.status === "rejected" && dashboardResult.status === "rejected") {
        throw new Error(matchesResult.reason?.message || dashboardResult.reason?.message || "Impossible de charger les donnees.");
      }

      if (dashboardResult.status === "rejected") {
        setInfo("Les matchs ont ete charges, mais le dashboard n'a pas pu etre affiche.");
      }

      loadRecentRiotIds();
    } catch (loadError) {
      setError(loadError.message || "Impossible de charger le tableau de bord.");
    } finally {
      setLoading(false);
    }
  }

  async function handleMatchFiltersChange(nextFilters) {
    setMatchFilters(nextFilters);

    const visibleMatches = filterMatchesLocally(pageMatches, nextFilters);
    if (!queryParams || visibleMatches.length || !hasActiveMatchFilters(nextFilters)) {
      setRemoteFilteredMatches(false);
      setMatches(visibleMatches);
      selectVisibleMatch(visibleMatches);
      return;
    }

    await loadDashboard(1, nextFilters, { remoteFilters: true });
  }

  async function handleRefresh() {
    if (!queryParams) {
      setError("Renseigne un Riot ID ou un PUUID.");
      return;
    }

    if (query.mode === "riot_name") {
      pushRecentRiotId(query.value);
    }

    const dashboardCacheKey = buildDashboardCacheKey(queryParams);
    const matchesCacheKey = buildMatchesCacheKey(queryParams, 1, matchFilters, false);

    setLoading(true);
    setError("");
    setInfo("");
    resetLoadedMatchDetails();

    try {
      if (query.mode === "riot_name") {
        const importResponse = await triggerMatchImport({
          riot_id: query.value.trim(),
          region: query.region,
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
      const visibleMatches = filterMatchesLocally(matchResults, matchFilters);
      setPageMatches(matchResults);
      setRemoteFilteredMatches(false);
      setMatches(visibleMatches);
      setMatchesPagination({
        next: matchesResponse.next,
        previous: matchesResponse.previous,
        count: matchesResponse.count || 0,
        page: 1,
      });
      setSelectedMatchId(visibleMatches[0]?.match_id || null);
      setGlobalStats(dashboardResponse.overview || null);
      setChampionStats(Array.isArray(dashboardResponse.champions) ? dashboardResponse.champions : []);
      setModeStats(Array.isArray(dashboardResponse.modes) ? dashboardResponse.modes : []);
      setCsEvolution(Array.isArray(dashboardResponse.cs_evolution) ? dashboardResponse.cs_evolution : []);
      setLpEvolution(Array.isArray(dashboardResponse.lp_evolution) ? dashboardResponse.lp_evolution : []);
      safeWriteJson(matchesCacheKey, {
        matches: visibleMatches,
        pageMatches: matchResults,
        remoteFilteredMatches: false,
        pagination: {
          next: matchesResponse.next,
          previous: matchesResponse.previous,
          count: matchesResponse.count || 0,
          page: 1,
        },
      });
      safeWriteJson(dashboardCacheKey, dashboardResponse);
      loadRecentRiotIds();
    } catch (refreshError) {
      setError(refreshError.message || "Impossible d'actualiser les données.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!selectedMatchId || !queryParams) {
      return;
    }

    loadMatchDetail(selectedMatchId, queryParams);
  }, [selectedMatchId, queryParams]);

  const activeMatchSummary = matches.find((match) => match.match_id === selectedMatchId) || matches[0] || null;
  const activeMatch = (selectedMatchId && matchDetailsById[selectedMatchId]) || activeMatchSummary;

  return (
    <AppShell loading={loading} playerLabel={query.value}>
      <SearchPanel
        query={query}
        regionOptions={REGION_OPTIONS}
        onQueryChange={setQuery}
        onSubmit={() => loadDashboard(1)}
        onRefresh={handleRefresh}
        loading={loading}
        recentRiotIds={recentRiotIds}
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
              title="Évolution LP"
              subtitle="Snapshots classés"
              type="line"
              variant="ranked"
              data={{
                labels: lpEvolution.map((entry) => entry.date.slice(5, 16)),
                datasets: [
                  {
                    label: "Elo",
                    data: lpEvolution.map((entry) => entry.elo_score ?? entry.lp),
                    hoverLabels: lpEvolution.map((entry) => entry.rank_label || `${entry.tier || ""} ${entry.rank_division || ""} - ${entry.lp} LP`.trim()),
                    borderColor: "#5377d8",
                    backgroundColor: "rgba(83,119,216,0.16)",
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                  },
                ],
              }}
            />
            <ChartCard
              title="Répartition des parties"
              subtitle="Base locale"
              type="doughnut"
              data={{
                labels: modeStats.map((mode) => mode.queue_name || `File ${mode.queue}`),
                datasets: [
                  {
                    label: "Parties",
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
              selectedMatchDetail={selectedMatchId ? matchDetailsById[selectedMatchId] || null : null}
              detailLoading={detailLoading}
              detailError={detailError}
              onPageChange={(page) => loadDashboard(page, matchFilters, { remoteFilters: remoteFilteredMatches })}
              loading={loading}
              filters={matchFilters}
              filterOptions={matchFilterOptions}
              onFiltersChange={handleMatchFiltersChange}
            />
          </div>
        </section>
      ) : null}
    </AppShell>
  );
}

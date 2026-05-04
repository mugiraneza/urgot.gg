import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
from django.db import transaction
from django.utils import timezone
from api.models import Match, Participant, Team, Ban, Objective, Death, Item, Champion, RankSnapshot
from datetime import datetime

RIOT_API_KEY = os.getenv("RIOT_KEY")
MAX_MATCHES = int(1000)
DELAY_SEC = float(1.3)
IMPORT_WORKERS = max(1, int(os.getenv("RIOT_IMPORT_WORKERS", "4")))
REQUEST_TIMEOUT = float(os.getenv("RIOT_REQUEST_TIMEOUT", "10"))
REQUEST_MAX_RETRIES = max(1, int(os.getenv("RIOT_REQUEST_MAX_RETRIES", "5")))
REQUEST_RETRY_BASE_DELAY = max(0.1, float(os.getenv("RIOT_REQUEST_RETRY_BASE_DELAY", "2")))
IMPORT_CACHE_MAX_SIZE = max(1, int(os.getenv("RIOT_IMPORT_CACHE_MAX_SIZE", "1000")))
HEADERS = {"X-Riot-Token": RIOT_API_KEY}
RANKED_QUEUE_PRIORITY = ["RANKED_SOLO_5x5", "RANKED_FLEX_SR"]
MATCH_QUEUE_TO_RANK_QUEUE = {
    420: "RANKED_SOLO_5x5",
    440: "RANKED_FLEX_SR",
}
DATA_DRAGON_BASE_URL = "https://ddragon.leagueoflegends.com"
DATA_DRAGON_VERSION: Optional[str] = None
ACCOUNT_REGION_BY_PLATFORM = {
    "br1": "americas",
    "eun1": "europe",
    "euw1": "europe",
    "jp1": "asia",
    "kr": "asia",
    "la1": "americas",
    "la2": "americas",
    "na1": "americas",
    "oc1": "americas",
    "ru": "europe",
    "tr1": "europe",
}
ACCOUNT_REGIONS = ("europe", "americas", "asia", "sea")


def _current_log_timestamp():
    return timezone.localtime().strftime("%Y-%m-%d %H:%M:%S %Z")


class BoundedCache:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._store: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        value = self._store.get(key)
        if value is None:
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
        self._store[key] = value
        self._store.move_to_end(key)
        if len(self._store) > self.max_size:
            self._store.popitem(last=False)
        return value


RANK_CACHE = BoundedCache(IMPORT_CACHE_MAX_SIZE)
SUMMONER_CACHE = BoundedCache(IMPORT_CACHE_MAX_SIZE)

def _get_json_without_retries(url: str) -> Dict:
    while True:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 5))
            print(f"[!] 429 â€“ Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()


def _get_retry_delay(attempt: int, response: Optional[requests.Response] = None) -> float:
    if response is not None and response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass

    return min(60.0, REQUEST_RETRY_BASE_DELAY * (2 ** (attempt - 1)))


def _sleep_before_retry(url: str, attempt: int, reason: str, response: Optional[requests.Response] = None) -> None:
    wait = _get_retry_delay(attempt, response)
    print(
        f"[!] Riot API indisponible ({reason}). "
        f"Nouvel essai {attempt + 1}/{REQUEST_MAX_RETRIES} dans {wait:g}s: {url}"
    )
    time.sleep(wait)


def _get_json(url: str) -> Dict:
    for attempt in range(1, REQUEST_MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            if attempt >= REQUEST_MAX_RETRIES:
                print(f"[!] Riot API inaccessible apres {REQUEST_MAX_RETRIES} essais: {url}")
                raise
            _sleep_before_retry(url, attempt, str(exc))
            continue

        if r.status_code == 429 or 500 <= r.status_code < 600:
            if attempt >= REQUEST_MAX_RETRIES:
                r.raise_for_status()
            _sleep_before_retry(url, attempt, f"HTTP {r.status_code}", r)
            continue

        r.raise_for_status()
        return r.json()

    raise RuntimeError("Riot API inaccessible.")

def split_riot_id(rid: str) -> Tuple[str, str]:
    if "#" not in rid:
        raise ValueError("Format attendu : nom#tag")
    name, tag = rid.split("#", 1)
    return name.strip(), tag.strip()


def normalize_account_region(region: Optional[str]) -> str:
    normalized_region = (region or "europe").strip().lower()
    if normalized_region in ACCOUNT_REGIONS:
        return normalized_region

    cluster_region = ACCOUNT_REGION_BY_PLATFORM.get(normalized_region)
    if cluster_region:
        return cluster_region

    raise ValueError(f"Region inconnue : {region}")

def get_puuid(name: str, tag: str, region: str) -> str:
    return get_account_by_riot_id(name, tag, region)["puuid"]


def get_account_by_riot_id(name: str, tag: str, region: str) -> Dict[str, Any]:
    normalized_region = normalize_account_region(region)
    encoded_name = quote(name, safe="")
    encoded_tag = quote(tag, safe="")
    url = f"https://{normalized_region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{encoded_name}/{encoded_tag}"
    account = _get_json(url)
    if not isinstance(account, dict) or not account.get("puuid"):
        raise RuntimeError("Reponse Riot invalide pour ce Riot ID.")
    return {
        "region": normalized_region,
        "puuid": account["puuid"],
        "gameName": account.get("gameName"),
        "tagLine": account.get("tagLine"),
    }


def find_accounts_by_riot_id(name: str, tag: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []

    for account_region in ACCOUNT_REGIONS:
        try:
            matches.append(get_account_by_riot_id(name, tag, account_region))
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 404:
                continue
            raise

    return matches

def get_all_match_ids(puuid: str, region: str, total: int = MAX_MATCHES) -> List[str]:
    ids, start, step = [], 0, 100
    while start < total:
        url = (
            f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/"
            f"{puuid}/ids?start={start}&count={step}"
        )
        batch = _get_json(url)
        if not batch:
            break
        ids.extend(batch)
        if len(batch) < step:
            break
        start += step
        time.sleep(DELAY_SEC)
    return ids[:total]

def get_item_id(item_id):
    if item_id is None:
        return None
    return Item.objects.filter(item_id=str(item_id)).first()

def get_champion_obj(champion_id):
    if champion_id is None:
        return None
    return Champion.objects.filter(champion_id=str(champion_id)).first()

def get_champion_id(champion_id):
    if champion_id is None:
        return None
    champ = Champion.objects.filter(champion_id=str(champion_id)).first()
    return champ.pk if champ else None

def get_match(mid: str, region: str) -> Dict:
    return _get_json(f"https://{region}.api.riotgames.com/lol/match/v5/matches/{mid}")

def get_timeline(mid: str, region: str) -> Dict:
    return _get_json(f"https://{region}.api.riotgames.com/lol/match/v5/matches/{mid}/timeline")


def fetch_match_bundle(mid: str, region: str) -> Tuple[str, Dict, Dict]:
    return mid, get_match(mid, region), get_timeline(mid, region)


def get_platform_region(match_id: str) -> str:
    return match_id.split("_", 1)[0].lower()


def _is_rank_lookup_puuid(puuid: str) -> bool:
    return bool(puuid and puuid != "BOT" and len(puuid) >= 20)


def _get_ranked_queue_type_for_match(match: Match) -> Optional[str]:
    return MATCH_QUEUE_TO_RANK_QUEUE.get(match.queue_id)


def get_rank_entries_for_puuid(puuid: str, platform_region: str) -> Dict[str, Dict]:
    if not _is_rank_lookup_puuid(puuid):
        return {}

    cache_key = f"{platform_region}:{puuid}"
    cached_entries = RANK_CACHE.get(cache_key)
    if cached_entries is not None:
        return cached_entries

    try:
        entries = _get_json(
            f"https://{platform_region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        )
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (400, 404):
            return RANK_CACHE.set(cache_key, {})
        raise
    except requests.RequestException as exc:
        print(f"[!] Impossible de recuperer le rang pour {puuid}: {exc}")
        return RANK_CACHE.set(cache_key, {})

    if not isinstance(entries, list):
        return RANK_CACHE.set(cache_key, {})

    ranked_entries = {
        entry.get("queueType"): entry
        for entry in entries
        if entry.get("queueType")
    }
    return RANK_CACHE.set(cache_key, ranked_entries)


def get_rank_entry_for_puuid(
    puuid: str,
    platform_region: str,
    preferred_queue_type: Optional[str] = None,
) -> Dict:
    entries_by_queue = get_rank_entries_for_puuid(puuid, platform_region)
    if not entries_by_queue:
        return {}

    if preferred_queue_type and preferred_queue_type in entries_by_queue:
        return entries_by_queue[preferred_queue_type]

    for queue_type in RANKED_QUEUE_PRIORITY:
        if queue_type in entries_by_queue:
            return entries_by_queue[queue_type]

    return next(iter(entries_by_queue.values()), {})


def get_summoner_profile_by_puuid(puuid: str, platform_region: str) -> Dict:
    if not RIOT_API_KEY or not puuid or not platform_region:
        return {}

    cache_key = f"{platform_region}:{puuid}"
    cached_profile = SUMMONER_CACHE.get(cache_key)
    if cached_profile is not None:
        return cached_profile

    try:
        data = _get_json(
            f"https://{platform_region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        )
    except requests.RequestException:
        data = {}

    return SUMMONER_CACHE.set(cache_key, data if isinstance(data, dict) else {})


def get_latest_data_dragon_version() -> Optional[str]:
    global DATA_DRAGON_VERSION

    if DATA_DRAGON_VERSION:
        return DATA_DRAGON_VERSION

    try:
        response = requests.get(f"{DATA_DRAGON_BASE_URL}/api/versions.json", timeout=10)
        response.raise_for_status()
        versions = response.json()
    except requests.RequestException:
        return None

    if isinstance(versions, list) and versions:
        DATA_DRAGON_VERSION = versions[0]
    return DATA_DRAGON_VERSION


def build_profile_icon_url(profile_icon_id: Optional[int]) -> Optional[str]:
    if profile_icon_id is None:
        return None

    version = get_latest_data_dragon_version()
    if not version:
        return None

    return f"{DATA_DRAGON_BASE_URL}/cdn/{version}/img/profileicon/{profile_icon_id}.png"


def store_rank_snapshot(match_id: str, puuid: str, riot_name: str) -> None:
    platform_region = get_platform_region(match_id)
    rank_entries = get_rank_entries_for_puuid(puuid, platform_region)
    if not rank_entries:
        return

    match = Match.objects.get(pk=match_id)
    for queue_type, rank_entry in rank_entries.items():
        RankSnapshot.objects.update_or_create(
            match=match,
            puuid=puuid,
            queue_type=queue_type,
            defaults={
                "riot_name": riot_name,
                "tier": rank_entry.get("tier", ""),
                "rank_division": rank_entry.get("rank", ""),
                "league_points": rank_entry.get("leaguePoints"),
                "wins": rank_entry.get("wins"),
                "losses": rank_entry.get("losses"),
            },
        )


def _extract_ping_stats(participant: Dict) -> Dict:
    return {
        key: value
        for key, value in participant.items()
        if key.endswith("Pings") and value is not None
    }


def _extract_perk_data(participant: Dict) -> Dict:
    perks = participant.get("perks") or {}
    styles = perks.get("styles") or []
    primary_style = styles[0] if len(styles) > 0 else {}
    secondary_style = styles[1] if len(styles) > 1 else {}

    return {
        "perks": perks,
        "primary_rune_style": primary_style.get("style"),
        "secondary_rune_style": secondary_style.get("style"),
        "primary_rune_selections": [
            selection.get("perk")
            for selection in primary_style.get("selections", [])
            if selection.get("perk") is not None
        ],
        "secondary_rune_selections": [
            selection.get("perk")
            for selection in secondary_style.get("selections", [])
            if selection.get("perk") is not None
        ],
        "stat_perks": perks.get("statPerks") or {},
    }


def _participant_defaults(p: Dict, rank_entry: Dict) -> Dict:
    challenges = p.get("challenges") or {}
    ping_stats = _extract_ping_stats(p)

    defaults = {
        "puuid": p["puuid"],
        "riot_name": f"{p['riotIdGameName']}#{p['riotIdTagline']}",
        "team_id": p["teamId"],
        "champion_id": get_champion_id(p["championId"]),
        "champion_name": p["championName"],
        "individual_position": p["individualPosition"],
        "role": p["role"],
        "summoner1_id": p["summoner1Id"],
        "summoner2_id": p["summoner2Id"],
        "kills": p["kills"],
        "deaths": p["deaths"],
        "assists": p["assists"],
        "total_damage_dealt_champs": p["totalDamageDealtToChampions"],
        "damage_self_mitigated": p["damageSelfMitigated"],
        "total_heal": p["totalHeal"],
        "total_damage_shielded_on_teammates": p.get("totalDamageShieldedOnTeammates"),
        "total_heals_on_teammates": p.get("totalHealsOnTeammates"),
        "total_damage_taken": p["totalDamageTaken"],
        "damage_dealt_to_objectives": p.get("damageDealtToObjectives"),
        "damage_dealt_to_turrets": p.get("damageDealtToTurrets"),
        "largest_killing_spree": p["largestKillingSpree"],
        "killing_sprees": p.get("killingSprees"),
        "largest_multi_kill": p.get("largestMultiKill"),
        "penta_kills": p["pentaKills"],
        "quadra_kills": p["quadraKills"],
        "turret_kills": p.get("turretKills"),
        "inhibitor_kills": p.get("inhibitorKills"),
        "inhibitor_takedowns": p.get("inhibitorTakedowns"),
        "turrets_lost": p.get("turretsLost"),
        "objectives_stolen": p.get("objectivesStolen"),
        "objectives_stolen_assists": p.get("objectivesStolenAssists"),
        "solo_kills": p.get("soloKills"),
        "vision_score": p["visionScore"],
        "wards_placed": p["wardsPlaced"],
        "detector_wards_placed": p.get("detectorWardsPlaced"),
        "vision_wards_bought_in_game": p.get("visionWardsBoughtInGame"),
        "wards_killed": p.get("wardsKilled"),
        "stealth_wards_placed": p.get("stealthWardsPlaced"),
        "vision_score_advantage_lane_opponent": challenges.get("visionScoreAdvantageLaneOpponent"),
        "total_minions_killed": p["totalMinionsKilled"],
        "neutral_minions_killed": p["neutralMinionsKilled"],
        "time_ccing_others": p["timeCCingOthers"],
        "item0": get_item_id(p["item0"]),
        "item1": get_item_id(p["item1"]),
        "item2": get_item_id(p["item2"]),
        "item3": get_item_id(p["item3"]),
        "item4": get_item_id(p["item4"]),
        "item5": get_item_id(p["item5"]),
        "item6": get_item_id(p["item6"]),
        "gold_earned": p["goldEarned"],
        "gold_spent": p["goldSpent"],
        "champ_level": p["champLevel"],
        "champ_experience": p["champExperience"],
        "lane": p.get("lane", ""),
        "lane_minions_first_10_minutes": challenges.get("laneMinionsFirst10Minutes"),
        "jungle_cs_before_10_minutes": challenges.get("jungleCsBefore10Minutes"),
        "gold_per_minute": challenges.get("goldPerMinute"),
        "damage_per_minute": challenges.get("damagePerMinute"),
        "champion_transform": p.get("championTransform"),
        "win": bool(p["win"]),
        "first_blood_kill": bool(p["firstBloodKill"]),
        "first_tower_kill": bool(p["firstTowerKill"]),
        "team_position": p["teamPosition"],
        "team_early_surrendered": p.get("teamEarlySurrendered"),
        "game_ended_in_early_surrender": p.get("gameEndedInEarlySurrender"),
        "game_ended_in_surrender": p.get("gameEndedInSurrender"),
        "longest_time_spent_living": p.get("longestTimeSpentLiving"),
        "total_time_cc_dealt": p.get("totalTimeCCDealt"),
        "time_played": p["timePlayed"],
        "bait_pings": p.get("baitPings"),
        "danger_pings": p.get("dangerPings"),
        "get_back_pings": p.get("getBackPings"),
        "ping_stats": ping_stats,
        "rank_queue": rank_entry.get("queueType", ""),
        "rank_tier": rank_entry.get("tier", ""),
        "rank_division": rank_entry.get("rank", ""),
        "rank_lp": rank_entry.get("leaguePoints"),
    }
    defaults.update(_extract_perk_data(p))
    return defaults

def insert_match(info: Dict, mid: str, obj:Dict):
    Match.objects.get_or_create(
        match_id=mid,
        defaults={
            "game_creation": info["gameCreation"],
            "game_end_ts": info["gameEndTimestamp"],
            "game_duration": info["gameDuration"],
            "game_mode": info["gameMode"],
            "game_type": info["gameType"],
            "game_version": info["gameVersion"],
            "map_id": info["mapId"],
            "queue_id": info["queueId"],
            "tournament_code": info.get("tournamentCode"),
            "objet_complet":obj,
        },
    )


def upsert_match(info: Dict, mid: str, obj: Dict):
    Match.objects.update_or_create(
        match_id=mid,
        defaults={
            "game_creation": info["gameCreation"],
            "game_end_ts": info["gameEndTimestamp"],
            "game_duration": info["gameDuration"],
            "game_mode": info["gameMode"],
            "game_type": info["gameType"],
            "game_version": info["gameVersion"],
            "map_id": info["mapId"],
            "queue_id": info["queueId"],
            "tournament_code": info.get("tournamentCode"),
            "objet_complet": obj,
        },
    )

def insert_teams(mid: str, teams: List[Dict]):
    match = Match.objects.get(pk=mid)
    for t in teams:
        obj = t["objectives"]
        Team.objects.get_or_create(
            match=match,
            team_id=t["teamId"],
            defaults={
                "win": t["win"],
                "baron_first": obj["baron"]["first"],
                "baron_kills": obj["baron"]["kills"],
                "dragon_first": obj["dragon"]["first"],
                "dragon_kills": obj["dragon"]["kills"],
                "tower_first": obj["tower"]["first"],
                "tower_kills": obj["tower"]["kills"],
            },
        )
        for b in t["bans"]:
            Ban.objects.get_or_create(
                match=match,
                team_id=t["teamId"],
                pick_turn=b["pickTurn"],
                champion=get_champion_obj(b["championId"]),
            )
            # print(get_champion_obj(b["championId"]))
        for typ, data in obj.items():
            Objective.objects.get_or_create(
                match=match,
                team_id=t["teamId"],
                type=typ,
                defaults={"first": data["first"], "kills": data["kills"]},
            )

def insert_participants(mid: str, participants: List[Dict]):
    match = Match.objects.get(pk=mid)
    platform_region = get_platform_region(mid)
    preferred_queue_type = _get_ranked_queue_type_for_match(match)
    for p in participants:
        puuid = p["puuid"]
        rank_entry = get_rank_entry_for_puuid(
            puuid,
            platform_region,
            preferred_queue_type=preferred_queue_type,
        )
        Participant.objects.update_or_create(
            match=match,
            participant_id=p["participantId"],
            defaults=_participant_defaults(p, rank_entry),
        )


def insert_skill_orders(mid: str, timeline: Dict):
    skill_orders = {}
    for frame in timeline["info"]["frames"]:
        for event in frame.get("events", []):
            if event.get("type") != "SKILL_LEVEL_UP":
                continue
            participant_id = event.get("participantId")
            skill_slot = event.get("skillSlot")
            if participant_id is None or skill_slot is None:
                continue
            skill_orders.setdefault(participant_id, []).append(skill_slot)

    if not skill_orders:
        return

    participants = Participant.objects.filter(match__pk=mid, participant_id__in=skill_orders.keys())
    for participant in participants:
        participant.skill_order = skill_orders.get(participant.participant_id, [])
        participant.save(update_fields=["skill_order"])

def insert_deaths(mid: str, timeline: Dict):
    match = Match.objects.get(pk=mid)
    for frame in timeline["info"]["frames"]:
        for event in frame.get("events", []):
            if event.get("type") == "CHAMPION_KILL":
                Death.objects.get_or_create(
                    match=match,
                    timestamp=event["timestamp"],
                    participant_id=event["victimId"],
                    defaults={
                        "killer_id": event.get("killerId", -1),
                        "assisting_participant_ids": ",".join(map(str, event.get("assistingParticipantIds", []))),
                        "x": event["position"]["x"],
                        "y": event["position"]["y"],
                    },
                )


def _expected_import_counts(stored_match: Dict[str, Any]) -> Dict[str, int]:
    info = stored_match.get("info") or {}
    teams = info.get("teams") or []
    return {
        "participants": len(info.get("participants") or []),
        "teams": len(teams),
        "bans": sum(len(team.get("bans") or []) for team in teams),
        "objectives": sum(len((team.get("objectives") or {}).keys()) for team in teams),
    }


def _actual_import_counts(match: Match) -> Dict[str, int]:
    return {
        "participants": Participant.objects.filter(match=match).count(),
        "teams": Team.objects.filter(match=match).count(),
        "bans": Ban.objects.filter(match=match).count(),
        "objectives": Objective.objects.filter(match=match).count(),
    }


def is_match_import_incomplete(match: Match) -> bool:
    stored_match = match.objet_complet or {}
    if not stored_match.get("info"):
        return False

    expected = _expected_import_counts(stored_match)
    actual = _actual_import_counts(match)
    return any(actual[key] < expected[key] for key in expected)


@transaction.atomic
def repair_match_import_from_stored_object(match: Match) -> Dict[str, Any]:
    stored_match = match.objet_complet or {}
    info = stored_match.get("info") or {}
    participants = info.get("participants") or []
    teams = info.get("teams") or []

    if not info or not participants:
        return {
            "match_id": match.match_id,
            "status": "skipped",
            "reason": "missing_stored_match_info",
        }

    before = _actual_import_counts(match)

    upsert_match(info, match.match_id, stored_match)
    insert_teams(match.match_id, teams)
    insert_participants(match.match_id, participants)

    after = _actual_import_counts(Match.objects.get(pk=match.match_id))
    repaired = any(after[key] > before[key] for key in before)

    return {
        "match_id": match.match_id,
        "status": "repaired" if repaired else "ok",
        "before": before,
        "after": after,
    }


def repair_incomplete_match_imports(match_id: Optional[str] = None) -> Dict[str, Any]:
    queryset = Match.objects.all().order_by("match_id")
    if match_id:
        queryset = queryset.filter(match_id=match_id)

    summary = {
        "checked": 0,
        "repaired": 0,
        "ok": 0,
        "skipped": 0,
        "details": [],
    }

    for match in queryset:
        summary["checked"] += 1
        stored_match = match.objet_complet or {}
        if not stored_match.get("info"):
            summary["skipped"] += 1
            summary["details"].append(
                {
                    "match_id": match.match_id,
                    "status": "skipped",
                    "reason": "missing_stored_match_info",
                }
            )
            continue

        if not is_match_import_incomplete(match):
            summary["ok"] += 1
            summary["details"].append(
                {
                    "match_id": match.match_id,
                    "status": "ok",
                }
            )
            continue

        result = repair_match_import_from_stored_object(match)
        summary["details"].append(result)
        if result["status"] == "repaired":
            summary["repaired"] += 1
        elif result["status"] == "ok":
            summary["ok"] += 1
        else:
            summary["skipped"] += 1

    return summary
                
def run_find_puid(riot_id: str, region: str):
    if not RIOT_API_KEY:
        raise RuntimeError("RIOT_API_KEY manquante.")
    name, tag = split_riot_id(riot_id)
    if region:
        return get_account_by_riot_id(name, tag, region)

    matches = find_accounts_by_riot_id(name, tag)
    if not matches:
        raise RuntimeError("Aucun compte Riot trouve pour ce Riot ID.")
    if len(matches) == 1:
        return matches[0]

    raise RuntimeError(
        "Plusieurs comptes trouves pour ce Riot ID. Precise la region: "
        + ", ".join(match["region"] for match in matches)
    )

def run_match_import(riot_id: str, region: str):
    if not RIOT_API_KEY:
        raise RuntimeError("RIOT_API_KEY manquante.")
    name, tag = split_riot_id(riot_id)
    puuid = get_puuid(name, tag, region)

    existing = set(Match.objects.values_list("match_id", flat=True))
    all_ids = get_all_match_ids(puuid, region, MAX_MATCHES)
    to_do = [mid for mid in all_ids if mid not in existing]
    print(riot_id)
    print(f"[i] {len(existing)} match(s) déjà en base")
    print(f"[i] {len(to_do)} match(s) à importer")

    if IMPORT_WORKERS <= 1:
        for i, mid in enumerate(to_do, 1):
            print(f"[{i}/{len(to_do)}] Import {mid}")
            match_data = get_match(mid, region)
            insert_match(match_data["info"], mid, match_data)
            insert_teams(mid, match_data["info"]["teams"])
            insert_participants(mid, match_data["info"]["participants"])

            timeline = get_timeline(mid, region)
            insert_deaths(mid, timeline)
            insert_skill_orders(mid, timeline)
            time.sleep(DELAY_SEC)
    else:
        print(f"[i] Telechargement parallele active: {IMPORT_WORKERS} workers")
        with ThreadPoolExecutor(max_workers=IMPORT_WORKERS) as executor:
            future_map = {
                executor.submit(fetch_match_bundle, mid, region): mid
                for mid in to_do
            }
            for i, future in enumerate(as_completed(future_map), 1):
                mid, match_data, timeline = future.result()
                print(f"[{i}/{len(to_do)}] Import {mid}")
                insert_match(match_data["info"], mid, match_data)
                insert_teams(mid, match_data["info"]["teams"])
                insert_participants(mid, match_data["info"]["participants"])
                insert_deaths(mid, timeline)
                insert_skill_orders(mid, timeline)


    snapshot_match_id = to_do[0] if to_do else (all_ids[0] if all_ids else None)
    if snapshot_match_id:
        # Riot ne fournit pas le LP gagne/perdu dans les donnees de match.
        # On capture l'etat classe courant et on l'associe au match le plus recent connu.
        store_rank_snapshot(snapshot_match_id, puuid, riot_id)
    print(f"[✅][{_current_log_timestamp()}]..... Import terminé.")

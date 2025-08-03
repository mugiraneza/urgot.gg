import os
import time
import requests
from typing import Dict, List, Tuple
from api.models import Match, Participant, Team, Ban, Objective, Death,Item,Champion

RIOT_API_KEY = os.getenv("RIOT_KEY")
MAX_MATCHES = int(1000)
DELAY_SEC = float(1.3)
HEADERS = {"X-Riot-Token": RIOT_API_KEY}

def _get_json(url: str) -> Dict:
    while True:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 5))
            print(f"[!] 429 – Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()

def split_riot_id(rid: str) -> Tuple[str, str]:
    if "#" not in rid:
        raise ValueError("Format attendu : nom#tag")
    return rid.split("#", 1)

def get_puuid(name: str, tag: str, region: str) -> str:
    url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    return _get_json(url)["puuid"]

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

def get_champion_id(champion_name):
    if champion_name is None:
        return None
    return Champion.objects.filter(name=str(champion_name)).first()

def get_match(mid: str, region: str) -> Dict:
    return _get_json(f"https://{region}.api.riotgames.com/lol/match/v5/matches/{mid}")

def get_timeline(mid: str, region: str) -> Dict:
    return _get_json(f"https://{region}.api.riotgames.com/lol/match/v5/matches/{mid}/timeline")

def insert_match(info: Dict, mid: str):
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
                champion=get_champion_id(b["championId"]),
            )
        for typ, data in obj.items():
            Objective.objects.get_or_create(
                match=match,
                team_id=t["teamId"],
                type=typ,
                defaults={"first": data["first"], "kills": data["kills"]},
            )

def insert_participants(mid: str, participants: List[Dict]):
    match = Match.objects.get(pk=mid)
    for p in participants:
        Participant.objects.get_or_create(
            match=match,
            participant_id=p["participantId"],
            defaults={
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
                "total_damage_taken": p["totalDamageTaken"],
                "largest_killing_spree": p["largestKillingSpree"],
                "penta_kills": p["pentaKills"],
                "quadra_kills": p["quadraKills"],
                "vision_score": p["visionScore"],
                "wards_placed": p["wardsPlaced"],
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
                "win": bool(p["win"]),
                "first_blood_kill": bool(p["firstBloodKill"]),
                "first_tower_kill": bool(p["firstTowerKill"]),
                "team_position": p["teamPosition"],
                "time_played": p["timePlayed"],
            },
        )

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

def run_match_import(riot_id: str, region: str):
    if not RIOT_API_KEY:
        raise RuntimeError("RIOT_API_KEY manquante.")
    name, tag = split_riot_id(riot_id)
    puuid = get_puuid(name, tag, region)

    existing = set(Match.objects.values_list("match_id", flat=True))
    all_ids = get_all_match_ids(puuid, region, MAX_MATCHES)
    to_do = [mid for mid in all_ids if mid not in existing]

    print(f"[i] {len(existing)} match(s) déjà en base")
    print(f"[i] {len(to_do)} match(s) à importer")

    for i, mid in enumerate(to_do, 1):
        print(f"[{i}/{len(to_do)}] Import {mid}")
        match_data = get_match(mid, region)
        insert_match(match_data["info"], mid)
        insert_teams(mid, match_data["info"]["teams"])
        insert_participants(mid, match_data["info"]["participants"])

        timeline = get_timeline(mid, region)
        insert_deaths(mid, timeline)
        time.sleep(DELAY_SEC)

    print("✅ Import terminé.")

# docker-compose exec api python manage.py collect_matches

from django.core.management.base import BaseCommand
from api.models import Match, Participant, Team, Ban, Objective, Death

import os, time, requests
from typing import Dict, List, Tuple

RIOT_API_KEY  = os.getenv("RIOT_KEY")
RIOT_ID       = os.getenv("RIOT_ID", "proctologue#urgot")
REGION        = os.getenv("RIOT_REGION", "europe")
MAX_MATCHES   = int(os.getenv("RIOT_MAX_MATCHES", "1000"))
DELAY_SEC     = float(os.getenv("RIOT_DELAY_SEC", "1.3"))
HEADERS       = {"X-Riot-Token": RIOT_API_KEY}

def _get_json(url: str) -> Dict:
    while True:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 5))
            print(f"\n[!] 429 – pause {wait}s")
            time.sleep(wait); continue
        r.raise_for_status(); return r.json()

def split_riot_id(rid: str) -> Tuple[str, str]:
    if "#" not in rid: raise ValueError("Format attendu : nom#tag")
    return rid.split("#", 1)

def get_puuid(name: str, tag: str) -> str:
    url = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    return _get_json(url)["puuid"]

def get_all_match_ids(puuid: str, total: int = MAX_MATCHES) -> List[str]:
    ids, start, step = [], 0, 100
    while start < total:
        url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={step}"
        batch = _get_json(url)
        if not batch: break
        ids.extend(batch)
        if len(batch) < step: break
        start += step
        time.sleep(DELAY_SEC)
    return ids[:total]

def get_match(mid: str) -> Dict:
    return _get_json(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{mid}")

def get_timeline(mid: str) -> Dict:
    return _get_json(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{mid}/timeline")

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
            "tournament_code": info.get("tournamentCode")
        }
    )

def insert_teams(mid: str, teams: List[Dict]):
    match = Match.objects.get(pk=mid)
    for t in teams:
        Team.objects.get_or_create(
            match=match,
            team_id=t["teamId"],
            defaults={
                "win": t["win"],
                "baron_first": t["objectives"]["baron"]["first"],
                "baron_kills": t["objectives"]["baron"]["kills"],
                "dragon_first": t["objectives"]["dragon"]["first"],
                "dragon_kills": t["objectives"]["dragon"]["kills"],
                "tower_first": t["objectives"]["tower"]["first"],
                "tower_kills": t["objectives"]["tower"]["kills"],
            }
        )
        for b in t["bans"]:
            Ban.objects.get_or_create(
                match=match,
                team_id=t["teamId"],
                pick_turn=b["pickTurn"],
                champion_id=b["championId"]
            )
        for typ, data in t["objectives"].items():
            Objective.objects.get_or_create(
                match=match,
                team_id=t["teamId"],
                type=typ,
                defaults={
                    "first": data["first"],
                    "kills": data["kills"]
                }
            )

def insert_participants(mid: str, parts: List[Dict]):
    match = Match.objects.get(pk=mid)
    for p in parts:
        Participant.objects.get_or_create(
            match=match,
            participant_id=p["participantId"],
            defaults={
                "puuid": p["puuid"],
                "riot_name": f"{p['riotIdGameName']}#{p['riotIdTagline']}",
                "team_id": p["teamId"],
                "champion_id": p["championId"],
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
                "item0": p["item0"], "item1": p["item1"], "item2": p["item2"],
                "item3": p["item3"], "item4": p["item4"], "item5": p["item5"], "item6": p["item6"],
                "gold_earned": p["goldEarned"], "gold_spent": p["goldSpent"],
                "champ_level": p["champLevel"], "champ_experience": p["champExperience"],
                "win": bool(p["win"]),
                "first_blood_kill": bool(p["firstBloodKill"]),
                "first_tower_kill": bool(p["firstTowerKill"]),
                "team_position": p["teamPosition"],
                "time_played": p["timePlayed"],
            }
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
                    }
                )

class Command(BaseCommand):
    help = "Collect League of Legends match data and save to the database"

    def handle(self, *args, **kwargs):
        if not RIOT_API_KEY:
            self.stderr.write("❌ RIOT_API_KEY manquante.")
            return

        name, tag = split_riot_id(RIOT_ID)
        puuid = get_puuid(name, tag)

        existing = set(Match.objects.values_list('match_id', flat=True))
        all_ids = get_all_match_ids(puuid, MAX_MATCHES)
        to_do = [mid for mid in all_ids if mid not in existing]

        total = len(to_do)
        print(f"[i] {len(existing)} match(s) déjà en base")
        print(f"[i] {total} match(s) à importer")

        for i, mid in enumerate(to_do, 1):
            pct = int(i / total * 100) if total else 100
            bar = '█' * (pct // 2)
            print(f"\r[{i:>4}/{total}] {bar:<50} {pct:3d}%  {mid}", end='')

            match_data = get_match(mid)
            insert_match(match_data["info"], mid)
            insert_teams(mid, match_data["info"]["teams"])
            insert_participants(mid, match_data["info"]["participants"])

            timeline = get_timeline(mid)
            insert_deaths(mid, timeline)

            time.sleep(DELAY_SEC)

        print("\n✅ Importation terminée.")

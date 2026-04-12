# Create your views here.
from .services.riot_importer import (
    build_profile_icon_url,
    get_platform_region,
    get_summoner_profile_by_puuid,
    repair_incomplete_match_imports,
    run_match_import,
    run_find_puid
)
from .services.import_champions_items import RiotDataImporter
from .services.new_summoner_name import get_riot_id_by_puuid  # importe ta logique
from .models import *
from .serializers import (
    MatchSerializer,
    ParticipantSerializer,
    TeamSerializer,
    BanSerializer,
    ObjectiveSerializer,
    DeathSerializer,
    PredictRequestSerializer,
    PredictResponseSerializer,
)
import threading
from rest_framework import viewsets, views, status
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime, timedelta
from collections import defaultdict
from django.core.cache import cache

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
from pathlib import Path
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.conf import settings
from .ml_service import get_model
import csv
matplotlib.use('Agg')

#region variable globale
running_imports = {}
SIDE_MAP = {100: "BLUE", 200: "RED"}
RECENT_RIOT_IDS_CACHE_KEY = "recent_riot_ids"
RECENT_RIOT_IDS_LIMIT = 8
RECENT_RIOT_IDS_TTL = 60 * 60 * 24 * 7
QUEUE_NAMES = {
    400: "Normal Blind Pick",
    420: "Ranked Solo/Duo",
    430: "Normal Draft",
    440: "Ranked Flex",
    450: "ARAM",
    480: "SWIFTPLAY",
    490: "Quickplay",
    700: "Clash",
    830: "Intro Bot",
    840: "Beginner Bot",
    850: "Intermediate Bot",
    900: "URF",
    920: "Poro King",
    1020: "One for All",
    1400: "ULTBOOK",
    1700: "CHERRY",
    1810: "STRAWBERRY A",
    1820: "STRAWBERRY B",
    1830: "STRAWBERRY C",
    1840: "STRAWBERRY D",
    2000: "Tutorial 1",
    2010: "Tutorial 2",
    2020: "Tutorial 3",
}
RANK_TIER_SCORES = {
    "IRON": 0,
    "BRONZE": 400,
    "SILVER": 800,
    "GOLD": 1200,
    "PLATINUM": 1600,
    "EMERALD": 2000,
    "DIAMOND": 2400,
    "MASTER": 2800,
    "GRANDMASTER": 3200,
    "CHALLENGER": 3600,
}
RANK_DIVISION_SCORES = {
    "IV": 0,
    "III": 100,
    "II": 200,
    "I": 300,
}

#EndOfRegion Variable Global


def _store_recent_riot_id(riot_id):
    normalized = (riot_id or "").strip()
    if not normalized:
        return

    recent_ids = cache.get(RECENT_RIOT_IDS_CACHE_KEY, [])
    recent_ids = [value for value in recent_ids if value.lower() != normalized.lower()]
    recent_ids.insert(0, normalized)
    cache.set(RECENT_RIOT_IDS_CACHE_KEY, recent_ids[:RECENT_RIOT_IDS_LIMIT], RECENT_RIOT_IDS_TTL)


def _get_recent_riot_ids():
    return cache.get(RECENT_RIOT_IDS_CACHE_KEY, [])


def _get_player_filters(request):
    puuid = request.GET.get("puuid")
    riot_name = request.GET.get("riot_name")

    if not puuid and not riot_name:
        return None, Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'."}, status=400)

    filters = {}
    if puuid:
        filters["puuid"] = puuid
    if riot_name:
        _store_recent_riot_id(riot_name)
        filters["riot_name__iexact"] = riot_name
    return filters, None


def _build_asset_url(request, asset_type, resource_name):
    if not resource_name:
        return None
    filename = f"{resource_name}.png"
    return request.build_absolute_uri(f"/api/assets/{asset_type}/{asset_type}/{filename}")


def _serialize_item_slot(request, item):
    if not item:
        return {"id": None, "name": None, "image_url": None}
    return {
        "id": item.item_id,
        "name": item.name,
        "image_url": _build_asset_url(request, "items", item.item_id),
    }


def _format_rank_label(participant):
    if not participant.rank_tier:
        return None

    parts = [participant.rank_tier]
    if participant.rank_division:
        parts.append(participant.rank_division)

    label = " ".join(parts)
    if participant.rank_lp is not None:
        label = f"{label} - {participant.rank_lp} LP"
    return label


def _build_rank_icon_name(rank_tier):
    if not rank_tier:
        return None
    normalized_tier = rank_tier.strip().title()
    return f"Rank={normalized_tier}"


def _build_player_profile_icon_url(participant):
    if not participant:
        return None

    platform_region = get_platform_region(participant.match.match_id)
    summoner_profile = get_summoner_profile_by_puuid(participant.puuid, platform_region)
    profile_icon_id = summoner_profile.get("profileIconId")
    return build_profile_icon_url(profile_icon_id)


def _build_rank_summary(request, tier, rank_division, league_points):
    if not tier:
        return None

    participant = type(
        "RankSummary",
        (),
        {"rank_tier": tier, "rank_division": rank_division, "rank_lp": league_points},
    )()
    return {
        "label": _format_rank_label(participant),
        "tier": tier,
        "rank_division": rank_division,
        "lp": league_points,
        "icon_url": _build_asset_url(request, "elo", _build_rank_icon_name(tier)),
    }


def _build_rank_label(tier, rank_division, league_points):
    if not tier:
        return None

    parts = [tier]
    if rank_division:
        parts.append(rank_division)

    label = " ".join(parts)
    if league_points is not None:
        label = f"{label} - {league_points} LP"
    return label


def _build_rank_elo_score(tier, rank_division, league_points):
    normalized_tier = (tier or "").strip().upper()
    if normalized_tier not in RANK_TIER_SCORES:
        return league_points

    base_score = RANK_TIER_SCORES[normalized_tier]
    lp_score = league_points or 0

    if normalized_tier in {"MASTER", "GRANDMASTER", "CHALLENGER"}:
        return base_score + lp_score

    normalized_division = (rank_division or "").strip().upper()
    return base_score + RANK_DIVISION_SCORES.get(normalized_division, 0) + lp_score


def _build_player_rank_overview(request, filters, latest_ranked_participant):
    snapshot_filters = {}
    if filters.get("puuid"):
        snapshot_filters["puuid"] = filters["puuid"]
    if filters.get("riot_name__iexact"):
        snapshot_filters["riot_name__iexact"] = filters["riot_name__iexact"]

    latest_snapshots = {}
    for snapshot in (
        RankSnapshot.objects.filter(**snapshot_filters)
        .select_related("match")
        .order_by("queue_type", "-match__game_creation", "-captured_at")
    ):
        latest_snapshots.setdefault(snapshot.queue_type, snapshot)

    solo_snapshot = latest_snapshots.get("RANKED_SOLO_5x5")
    flex_snapshot = latest_snapshots.get("RANKED_FLEX_SR")

    if solo_snapshot or flex_snapshot:
        return {
            "solo": _build_rank_summary(
                request,
                solo_snapshot.tier if solo_snapshot else None,
                solo_snapshot.rank_division if solo_snapshot else None,
                solo_snapshot.league_points if solo_snapshot else None,
            ),
            "flex": _build_rank_summary(
                request,
                flex_snapshot.tier if flex_snapshot else None,
                flex_snapshot.rank_division if flex_snapshot else None,
                flex_snapshot.league_points if flex_snapshot else None,
            ),
        }

    return {
        "solo": _build_rank_summary(
            request,
            latest_ranked_participant.rank_tier if latest_ranked_participant and latest_ranked_participant.rank_queue == "RANKED_SOLO_5x5" else None,
            latest_ranked_participant.rank_division if latest_ranked_participant and latest_ranked_participant.rank_queue == "RANKED_SOLO_5x5" else None,
            latest_ranked_participant.rank_lp if latest_ranked_participant and latest_ranked_participant.rank_queue == "RANKED_SOLO_5x5" else None,
        ),
        "flex": _build_rank_summary(
            request,
            latest_ranked_participant.rank_tier if latest_ranked_participant and latest_ranked_participant.rank_queue == "RANKED_FLEX_SR" else None,
            latest_ranked_participant.rank_division if latest_ranked_participant and latest_ranked_participant.rank_queue == "RANKED_FLEX_SR" else None,
            latest_ranked_participant.rank_lp if latest_ranked_participant and latest_ranked_participant.rank_queue == "RANKED_FLEX_SR" else None,
        ),
    }


def _serialize_participant_details(request, participant):
    return {
        "riot_name": participant.riot_name,
        "champion": participant.champion_name,
        "champion_image_url": _build_asset_url(request, "champions", participant.champion_name),
        "team_id": participant.team_id,
        "position": participant.team_position,
        "lane": participant.lane,
        "kills": participant.kills,
        "deaths": participant.deaths,
        "assists": participant.assists,
        "rank_queue": participant.rank_queue,
        "rank_tier": participant.rank_tier,
        "rank_division": participant.rank_division,
        "rank_lp": participant.rank_lp,
        "rank_label": _format_rank_label(participant),
        "vision_score": participant.vision_score,
        "wards_placed": participant.wards_placed,
        "detector_wards_placed": participant.detector_wards_placed,
        "vision_wards_bought_in_game": participant.vision_wards_bought_in_game,
        "wards_killed": participant.wards_killed,
        "stealth_wards_placed": participant.stealth_wards_placed,
        "vision_score_advantage_lane_opponent": participant.vision_score_advantage_lane_opponent,
        "total_damage_dealt_champs": participant.total_damage_dealt_champs,
        "damage_self_mitigated": participant.damage_self_mitigated,
        "total_heal": participant.total_heal,
        "total_damage_shielded_on_teammates": participant.total_damage_shielded_on_teammates,
        "total_heals_on_teammates": participant.total_heals_on_teammates,
        "total_damage_taken": participant.total_damage_taken,
        "damage_dealt_to_objectives": participant.damage_dealt_to_objectives,
        "damage_dealt_to_turrets": participant.damage_dealt_to_turrets,
        "turret_kills": participant.turret_kills,
        "inhibitor_kills": participant.inhibitor_kills,
        "inhibitor_takedowns": participant.inhibitor_takedowns,
        "turrets_lost": participant.turrets_lost,
        "objectives_stolen": participant.objectives_stolen,
        "objectives_stolen_assists": participant.objectives_stolen_assists,
        "solo_kills": participant.solo_kills,
        "largest_killing_spree": participant.largest_killing_spree,
        "killing_sprees": participant.killing_sprees,
        "largest_multi_kill": participant.largest_multi_kill,
        "gold_earned": participant.gold_earned,
        "gold_spent": participant.gold_spent,
        "gold_per_minute": participant.gold_per_minute,
        "damage_per_minute": participant.damage_per_minute,
        "total_minions_killed": participant.total_minions_killed,
        "neutral_minions_killed": participant.neutral_minions_killed,
        "lane_minions_first_10_minutes": participant.lane_minions_first_10_minutes,
        "jungle_cs_before_10_minutes": participant.jungle_cs_before_10_minutes,
        "time_played": participant.time_played,
        "longest_time_spent_living": participant.longest_time_spent_living,
        "time_ccing_others": participant.time_ccing_others,
        "total_time_cc_dealt": participant.total_time_cc_dealt,
        "champ_level": participant.champ_level,
        "champ_experience": participant.champ_experience,
        "champion_transform": participant.champion_transform,
        "team_early_surrendered": participant.team_early_surrendered,
        "game_ended_in_early_surrender": participant.game_ended_in_early_surrender,
        "game_ended_in_surrender": participant.game_ended_in_surrender,
        "bait_pings": participant.bait_pings,
        "danger_pings": participant.danger_pings,
        "get_back_pings": participant.get_back_pings,
        "ping_stats": participant.ping_stats,
        "perks": participant.perks,
        "primary_rune_style": participant.primary_rune_style,
        "secondary_rune_style": participant.secondary_rune_style,
        "primary_rune_selections": participant.primary_rune_selections,
        "secondary_rune_selections": participant.secondary_rune_selections,
        "stat_perks": participant.stat_perks,
        "skill_order": participant.skill_order,
    }


def _build_match_details(request, filters):
    user_participants = (
        Participant.objects.filter(**filters)
        .select_related("match", "champion", "item0", "item1", "item2", "item3", "item4", "item5", "item6")
        .order_by("-match__game_creation")
    )

    if not user_participants.exists():
        return []

    match_ids = [p.match_id for p in user_participants]
    all_participants = Participant.objects.filter(match_id__in=match_ids)

    match_participants_map = defaultdict(list)
    team_kills_map = defaultdict(lambda: defaultdict(int))

    for participant in all_participants:
        match_participants_map[participant.match_id].append(participant)
        team_kills_map[participant.match_id][participant.team_id] += participant.kills

    results = []

    for participant in user_participants:
        match = participant.match
        match_id = match.match_id
        team_kills = team_kills_map[match_id][participant.team_id]
        participants_list = match_participants_map[match_id]

        kda_ratio = (participant.kills + participant.assists) / max(1, participant.deaths)
        kill_participation = (participant.kills + participant.assists) / max(1, team_kills)

        results.append({
            "match_id": match_id,
            "champion": participant.champion_name,
            "champion_image_url": _build_asset_url(request, "champions", participant.champion_name),
            "position": participant.team_position,
            "rank_queue": participant.rank_queue,
            "rank_tier": participant.rank_tier,
            "rank_division": participant.rank_division,
            "rank_lp": participant.rank_lp,
            "rank_label": _format_rank_label(participant),
            "win": participant.win,
            "team_id": participant.team_id,
            "queue_name": QUEUE_NAMES.get(match.queue_id, f"Unknown ({match.queue_id})"),
            "game_duration": match.game_duration,
            "summoner_spells": [participant.summoner1_id, participant.summoner2_id],
            "kills": participant.kills,
            "deaths": participant.deaths,
            "assists": participant.assists,
            "kda_ratio": round(kda_ratio, 2),
            "kill_participation": round(kill_participation * 100, 1),
            "items": [
                _serialize_item_slot(request, participant.item0),
                _serialize_item_slot(request, participant.item1),
                _serialize_item_slot(request, participant.item2),
                _serialize_item_slot(request, participant.item3),
                _serialize_item_slot(request, participant.item4),
                _serialize_item_slot(request, participant.item5),
                _serialize_item_slot(request, participant.item6),
            ],
            "wards_placed": participant.wards_placed,
            "wards_destroyed": max(0, participant.vision_score - participant.wards_placed),
            "vision_score": participant.vision_score,
            "advanced_stats": _serialize_participant_details(request, participant),
            "start_time": datetime.fromtimestamp(match.game_creation / 1000).isoformat(),
            "end_time": datetime.fromtimestamp(match.game_end_ts / 1000).isoformat(),
            "participant_id": participant.participant_id,
            "participants": [
                _serialize_participant_details(request, teammate)
                for teammate in participants_list
            ],
        })

    return results


def _build_champion_pool(request, filters):
    participants = Participant.objects.filter(
        **filters, match__queue_id__in=[400, 420, 430, 440]
    ).select_related("match", "champion")

    if not participants.exists():
        return []

    match_ids = [p.match_id for p in participants]
    all_participants = Participant.objects.filter(match_id__in=match_ids)
    team_kills_map = defaultdict(lambda: defaultdict(int))
    for participant in all_participants:
        team_kills_map[participant.match_id][participant.team_id] += participant.kills

    stats = {}
    for participant in participants:
        role = (participant.team_position or "").upper()
        if role in ["", "UNKNOWN"]:
            continue

        champion_stats = stats.setdefault(
            participant.champion_name,
            {
                "games": 0,
                "wins": 0,
                "total_kills": 0,
                "total_deaths": 0,
                "total_assists": 0,
                "total_damage": 0,
                "total_minions": 0,
                "total_time": 0,
                "total_kp_ratio": 0.0,
            },
        )
        champion_stats["games"] += 1
        champion_stats["wins"] += int(participant.win)
        champion_stats["total_kills"] += participant.kills
        champion_stats["total_deaths"] += participant.deaths
        champion_stats["total_assists"] += participant.assists
        champion_stats["total_damage"] += participant.total_damage_dealt_champs
        champion_stats["total_minions"] += participant.total_minions_killed + participant.neutral_minions_killed
        champion_stats["total_time"] += participant.time_played

        team_kills = team_kills_map[participant.match.match_id][participant.team_id]
        if team_kills > 0:
            champion_stats["total_kp_ratio"] += (participant.kills + participant.assists) / team_kills

    result = []
    for champion, data in stats.items():
        games = data["games"]
        time_minutes = data["total_time"] / 60 if data["total_time"] > 0 else 1
        result.append(
            {
                "champion": champion,
                "champion_image_url": _build_asset_url(request, "champions", champion),
                "games": games,
                "win_rate": round((data["wins"] / games) * 100, 1),
                "kda": round((data["total_kills"] + data["total_assists"]) / max(1, data["total_deaths"]), 2),
                "cs_per_min": round(data["total_minions"] / time_minutes, 2),
                "dpm": round(data["total_damage"] / time_minutes, 2),
                "kp": round((data["total_kp_ratio"] / games) * 100, 1),
            }
        )

    return sorted(result, key=lambda item: item["games"], reverse=True)


def _build_global_overview(request, filters):
    participants = list(
        Participant.objects.filter(**filters).select_related("match").order_by("match__game_creation")
    )
    if not participants:
        return None

    total_games = len(participants)
    total_wins = sum(1 for participant in participants if participant.win)
    latest_ranked_participant = next(
        (participant for participant in reversed(participants) if participant.rank_tier),
        None,
    )
    latest_participant = participants[-1]
    player_rank_overview = _build_player_rank_overview(request, filters, latest_ranked_participant)
    first_match = datetime.utcfromtimestamp(participants[0].match.game_creation // 1000)
    last_match = datetime.utcfromtimestamp(participants[-1].match.game_end_ts // 1000)
    total_time_played_sec = sum(participant.time_played for participant in participants)
    total_days_range = max(1, (last_match - first_match).days + 1)

    def format_duration(seconds):
        duration = timedelta(seconds=seconds)
        days = duration.days
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}d:{hours:02}h"

    user_puuid = participants[0].puuid
    match_ids = [participant.match_id for participant in participants]
    all_match_participants = list(
        Participant.objects.filter(match_id__in=match_ids).only("match_id", "team_id", "puuid")
    )
    by_match = defaultdict(list)
    for participant in all_match_participants:
        by_match[participant.match_id].append(participant)

    total_players_met = (
        Participant.objects.filter(match_id__in=match_ids)
        .exclude(puuid=user_puuid)
        .values("puuid")
        .distinct()
        .count()
    )

    per_game_coop = defaultdict(set)
    for participant in participants:
        allies = [
            ally.puuid
            for ally in by_match[participant.match_id]
            if ally.team_id == participant.team_id and ally.puuid != participant.puuid
        ]
        per_game_coop[participant.match.match_id].update(allies)

    unique_seen = set()
    new_per_game = 0
    old_per_game = 0
    for puuids in per_game_coop.values():
        new_per_game += len([value for value in puuids if value not in unique_seen])
        old_per_game += len([value for value in puuids if value in unique_seen])
        unique_seen.update(puuids)

    return {
        "games_analyzed": total_games,
        "winrate": round((total_wins / total_games) * 100, 1) if total_games else 0,
        "player_elo": _format_rank_label(latest_ranked_participant) if latest_ranked_participant else None,
        "player_elo_icon_url": _build_asset_url(request, "elo", _build_rank_icon_name(latest_ranked_participant.rank_tier)) if latest_ranked_participant else None,
        "player_profile_icon_url": _build_player_profile_icon_url(latest_participant),
        "player_ranks": player_rank_overview,
        "oldest_match": first_match.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        "most_recent_match": last_match.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        "total_time_played": format_duration(total_time_played_sec),
        "avg_time_per_day": str(timedelta(seconds=int(total_time_played_sec / total_days_range))),
        "avg_games_per_day": round(total_games / total_days_range, 2),
        "percent_time_played": f"{round(((total_time_played_sec / total_days_range) / (24 * 3600)) * 100, 2)}%",
        "people_met": total_players_met,
        "avg_new_people_per_game": round(new_per_game / total_games, 2),
        "avg_old_friends_per_game": round(old_per_game / total_games, 2),
    }


def _build_mode_stats(filters):
    participants = Participant.objects.filter(**filters).select_related("match")
    if not participants.exists():
        return []

    mode_stats = defaultdict(
        lambda: {
            "queue": None,
            "total_games": 0,
            "wins": 0,
            "losses": 0,
            "surrenders": 0,
            "total_time_played": 0,
        }
    )

    for participant in participants:
        qid = participant.match.queue_id
        data = mode_stats[qid]
        data["queue"] = qid
        data["total_games"] += 1
        data["total_time_played"] += participant.time_played
        if participant.win:
            data["wins"] += 1
        else:
            data["losses"] += 1
            if participant.time_played < 600:
                data["surrenders"] += 1

    total_games_all_modes = sum(entry["total_games"] for entry in mode_stats.values())
    result = []
    for qid, data in sorted(mode_stats.items()):
        total = data["total_games"]
        avg_duration_sec = data["total_time_played"] / total if total else 0
        result.append(
            {
                "queue": qid,
                "queue_name": QUEUE_NAMES.get(qid, f"Unknown ({qid})"),
                "total_games": total,
                "percent_share": round((total / total_games_all_modes) * 100, 2) if total_games_all_modes else 0,
                "wins": data["wins"],
                "losses": data["losses"],
                "surrenders": data["surrenders"],
                "winrate": round((data["wins"] / total) * 100, 2) if total else 0,
                "avg_game_duration": str(timedelta(seconds=int(avg_duration_sec))),
                "total_time_spent": str(timedelta(seconds=data["total_time_played"])),
            }
        )
    return result


def _build_cs_evolution(filters):
    participants = (
        Participant.objects.filter(**filters).select_related("match").order_by("match__game_creation")
    )
    if not participants.exists():
        return []

    result = []
    for participant in participants:
        cs_total = participant.total_minions_killed + participant.neutral_minions_killed
        time_minutes = participant.time_played / 60 if participant.time_played else 1
        result.append(
            {
                "match_id": participant.match.match_id,
                "date": datetime.fromtimestamp(participant.match.game_creation / 1000).strftime("%Y-%m-%d %H:%M"),
                "champion": participant.champion_name,
                "cs": cs_total,
                "duration_min": round(time_minutes, 2),
                "cs_per_min": round(cs_total / time_minutes, 2),
                "position": participant.team_position,
            }
        )
    return result


def _build_lp_evolution(filters):
    snapshot_filters = {}
    if filters.get("puuid"):
        snapshot_filters["puuid"] = filters["puuid"]

    if filters.get("riot_name__iexact"):
        snapshot_filters["riot_name__iexact"] = filters["riot_name__iexact"]

    snapshots = list(
        RankSnapshot.objects.filter(**snapshot_filters)
        .select_related("match")
        .order_by("match__game_creation", "captured_at")
    )
    if not snapshots:
        return []

    ranked_snapshots = [snapshot for snapshot in snapshots if snapshot.league_points is not None and snapshot.tier]
    if not ranked_snapshots:
        return []

    queue_types = {snapshot.queue_type for snapshot in ranked_snapshots}
    if "RANKED_SOLO_5x5" in queue_types:
        selected_queue_type = "RANKED_SOLO_5x5"
    elif "RANKED_FLEX_SR" in queue_types:
        selected_queue_type = "RANKED_FLEX_SR"
    else:
        selected_queue_type = ranked_snapshots[-1].queue_type

    return [
        {
            "match_id": snapshot.match.match_id,
            "date": datetime.fromtimestamp(snapshot.match.game_end_ts / 1000).strftime("%Y-%m-%d %H:%M"),
            "lp": snapshot.league_points,
            "elo_score": _build_rank_elo_score(snapshot.tier, snapshot.rank_division, snapshot.league_points),
            "rank_label": _build_rank_label(snapshot.tier, snapshot.rank_division, snapshot.league_points),
            "tier": snapshot.tier,
            "rank_division": snapshot.rank_division,
            "queue_type": snapshot.queue_type,
            "wins": snapshot.wins,
            "losses": snapshot.losses,
        }
        for snapshot in ranked_snapshots
        if snapshot.queue_type == selected_queue_type
    ]

class MatchViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les objets Match.
    """
    queryset = Match.objects.all()
    serializer_class = MatchSerializer

class ParticipantViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les objets Participant.
    """
    queryset = Participant.objects.all()
    serializer_class = ParticipantSerializer

class TeamViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les objets Team.
    """
    queryset = Team.objects.all()
    serializer_class = TeamSerializer

class BanViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les objets Ban.
    """
    queryset = Ban.objects.all()
    serializer_class = BanSerializer

class ObjectiveViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les objets Objective.
    """
    queryset = Objective.objects.all()
    serializer_class = ObjectiveSerializer

class DeathViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les objets Death.
    """
    queryset = Death.objects.all()
    serializer_class = DeathSerializer


class RiotAssetView(views.APIView):
    """
    Expose local Riot images through internal API routes.
    """

    def get(self, request, asset_type, filename):
        allowed_types = {"champions", "items", "spells", "passives", "elo"}
        if asset_type not in allowed_types:
            raise Http404("Unknown asset type")

        relative_path = Path(filename)
        if relative_path.parts and relative_path.parts[0] != asset_type:
            raise Http404("Invalid asset path")

        file_path = (settings.RIOT_IMAGES_ROOT / relative_path).resolve()
        try:
            file_path.relative_to(settings.RIOT_IMAGES_ROOT.resolve())
        except ValueError as error:
            raise Http404("Invalid asset path") from error

        if not file_path.exists() or not file_path.is_file():
            raise Http404("Asset not found")

        return FileResponse(file_path.open("rb"))


class FrontDashboardView(views.APIView):
    """
    Endpoint frontend local-only: agrège les statistiques depuis la base locale.
    """

    @swagger_auto_schema(
        operation_description="Retourne le dashboard frontend depuis la base locale uniquement.",
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur"),
        ],
    )
    def get(self, request):
        filters, error_response = _get_player_filters(request)
        if error_response:
            return error_response

        overview = _build_global_overview(request, filters)
        if overview is None:
            return Response({"message": "Aucune donnée trouvée.", "source": "local_db"}, status=200)

        return Response(
            {
                "source": "local_db",
                "overview": overview,
                "modes": _build_mode_stats(filters),
                "champions": _build_champion_pool(request, filters),
                "cs_evolution": _build_cs_evolution(filters),
                "lp_evolution": _build_lp_evolution(filters),
            },
            status=200,
        )


class FrontMatchesView(views.APIView):
    """
    Endpoint frontend local-only: liste paginée des matchs depuis la base locale.
    """

    @swagger_auto_schema(
        operation_description="Retourne la liste des matchs frontend depuis la base locale uniquement.",
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur"),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Numéro de page"),
        ],
    )
    def get(self, request):
        filters, error_response = _get_player_filters(request)
        if error_response:
            return error_response

        results = _build_match_details(request, filters)
        paginator = PageNumberPagination()
        paginated_results = paginator.paginate_queryset(results, request)
        response = paginator.get_paginated_response(paginated_results)
        response.data["source"] = "local_db"
        return response


class RecentRiotIdsView(views.APIView):
    @swagger_auto_schema(
        operation_description="Retourne les Riot ID recherches recemment depuis le cache.",
        responses={200: openapi.Response(description="Liste des Riot ID recents")},
    )
    def get(self, request):
        return Response({"results": _get_recent_riot_ids()}, status=200)

#bloc des statistiques
class TriggerMatchImportViewSet(views.APIView):
    """
    Déclenche l'importation d'un match depuis Riot Games via un thread.
    """

    @swagger_auto_schema(
        operation_description="Lancer l'importation d'un match depuis Riot Games.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["riot_id", "region"],
            properties={
                "riot_id": openapi.Schema(type=openapi.TYPE_STRING, description="Riot ID du joueur (ex: proctologue#urgot)"),
                "region": openapi.Schema(type=openapi.TYPE_STRING, description="Région du joueur (ex: europe,americas,asia,sea)"),
            },
        ),
        responses={
            202: openapi.Response(description="Import lancé avec succès."),
            500: openapi.Response(description="Erreur serveur.")
        }
    )
    def post(self, request, **kwargs):
        try:
            riot_id = request.data.get("riot_id", "proctologue#urgot")
            region = request.data.get("region", "europe")
            _store_recent_riot_id(riot_id)
            existing_thread = running_imports.get(riot_id)
            if existing_thread and existing_thread.is_alive():
                return Response(
                    {"message": f"Un import est déjà en cours pour {riot_id}"},
                    status=status.HTTP_409_CONFLICT,
                )

            def import_task():
                try:
                    run_match_import(riot_id, region)
                finally:
                    running_imports.pop(riot_id, None)
            thread = threading.Thread(target=import_task, daemon=True)
            running_imports[riot_id] = thread
            thread.start()
            return Response({"message": f"Import lancé pour {riot_id} ({region})"}, status=202)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ImportStatusView(views.APIView):
    @swagger_auto_schema(
        operation_description="Récupérer le statut d'import.",
        manual_parameters=[
            openapi.Parameter(
                'summoner_name', openapi.IN_QUERY, description="Nom Riot du joueur", type=openapi.TYPE_STRING
            ),
        ],
        responses={
            200: openapi.Response(
                description="statut d'import",
                examples={"application/json": {"total_matches": 42}}
            )
        }
    )
    def get(self, request):
        riot_id = request.GET.get("summoner_name")
        if not riot_id :
            return Response({"status": "veuillez rajouter id dans le GET"}, status=200)
        thread = running_imports.get(riot_id)
        if thread and thread.is_alive():
            return Response({"status": "en cours"}, status=200)
        else:
            return Response({"status": "terminé ou inconnu"}, status=200)

class RepairStoredImportsView(views.APIView):
    """
    Verifie les imports incomplets et les complete depuis Match.objet_complet.
    """

    @swagger_auto_schema(
        operation_description="Verifie les imports incomplets et les complete depuis la colonne objet_complet.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "match_id": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Optionnel: reparer un match precis.",
                ),
            },
        ),
        responses={
            200: openapi.Response(description="Verification terminee."),
            500: openapi.Response(description="Erreur serveur."),
        }
    )
    def post(self, request, **kwargs):
        try:
            match_id = request.data.get("match_id")
            result = repair_incomplete_match_imports(match_id=match_id)
            return Response(result, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MatchcountViewSet(views.APIView):
    """
    Retourne le nombre total de matchs enregistrés en base.
    """

    @swagger_auto_schema(
        operation_description="Récupérer le nombre total de matchs enregistrés.",
        responses={
            200: openapi.Response(
                description="Nombre total de matchs",
                examples={"application/json": {"total_matches": 42}}
            )
        }
    )
    def get(self, request, *args, **kwargs):
        count = Match.objects.count()
        return Response({"total_matches": count})

class PositionStatsView(views.APIView):
    """
    Vue pour récupérer les rôles joués par un joueur au cours des 60 derniers jours.
    """

    @swagger_auto_schema(
        operation_description="Retourne les postes joués par un joueur (par riot_name ou puuid) sur les 60 derniers jours.",
        manual_parameters=[
            openapi.Parameter(
                'puuid', openapi.IN_QUERY, description="Identifiant PUUID du joueur", type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'riot_name', openapi.IN_QUERY, description="Nom Riot du joueur", type=openapi.TYPE_STRING
            ),
        ],
        responses={
            200: openapi.Response("Succès", examples={
                "application/json": {
                    "TOP": 5,
                    "JUNGLE": 3,
                    "MIDDLE": 7,
                    "BOTTOM": 4,
                    "UTILITY": 2,
                    "UNKNOWN": 1
                }
            }),
            400: "Paramètre manquant"
        }
    )
    def get(self, request):
        puuid = request.GET.get('puuid')
        riot_name = request.GET.get('riot_name')

        if not puuid and not riot_name:
            return Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'"}, status=400)

        # Date limite : 60 jours en arrière
        cutoff_date = datetime.now() - timedelta(days=60)

        # Récupérer les participants du joueur
        filters = {}
        if puuid:
            filters['puuid'] = puuid
        if riot_name:
            filters['riot_name__iexact'] = riot_name

        cutoff_ts_ms = int(cutoff_date.timestamp() * 1000)
        participants = Participant.objects.filter(**filters, match__game_end_ts__gte=cutoff_ts_ms)

        if not participants:
            return Response({"message": "Aucune donnée trouvée pour ce joueur."}, status=200)

        # Compter les positions
        position_counts = {}
        for p in participants:
            pos = (p.team_position or "UNKNOWN").upper()
            position_counts[pos] = position_counts.get(pos, 0) + 1

        return Response(dict(sorted(position_counts.items(), key=lambda item: item[1], reverse=True)), status=200)

class YearlyWinLossByPositionView(views.APIView):
    """
    Vue qui retourne le nombre de victoires et défaites par poste, classé par année et mois, pour un joueur donné.
    """
    @swagger_auto_schema(
    operation_description="Retourne le nombre de victoires et de défaites par poste, classé par année et mois pour un joueur donné (via riot_name ou puuid).",
    manual_parameters=[
        openapi.Parameter(
            'puuid',
            openapi.IN_QUERY,
            description="Identifiant PUUID du joueur",
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'riot_name',
            openapi.IN_QUERY,
            description="Nom Riot du joueur (ex: proctologue#urgot)",
            type=openapi.TYPE_STRING
        ),
    ],
    responses={
        200: openapi.Response(
            description="Statistiques par position, mois et année",
            examples={
                "application/json": {
                    "2025": {
                        "07": {
                            "TOP": {"wins": 3, "losses": 2},
                            "JUNGLE": {"wins": 1, "losses": 1}
                        }
                    },
                    "2024": {
                        "12": {
                            "BOTTOM": {"wins": 4, "losses": 3}
                        }
                    }
                }
            }
        ),
        400: openapi.Response(description="Paramètre manquant"),
        }
    )

    def get(self, request):
        riot_name = request.GET.get("riot_name")
        puuid = request.GET.get("puuid")

        if not riot_name and not puuid:
            return Response({"error": "Veuillez fournir 'riot_name' ou 'puuid'."}, status=400)

        filters = {}
        if puuid:
            filters['puuid'] = puuid
        if riot_name:
            filters['riot_name__iexact'] = riot_name

        participants = Participant.objects.filter(**filters).select_related('match')

        if not participants:
            return Response({"message": "Aucune donnée trouvée."}, status=200)

        results = {}

        for p in participants:
            # Convert timestamp (epoch seconds) to datetime
            end_time = datetime.fromtimestamp(p.match.game_end_ts/ 1000)
            year = str(end_time.year)
            month = f"{end_time.month:02d}"
            position = (p.team_position or "UNKNOWN").upper()
            outcome = "wins" if p.win else "losses"

            results.setdefault(year, {}).setdefault(month, {}).setdefault(position, {"wins": 0, "losses": 0})
            results[year][month][position][outcome] += 1

        return Response(results, status=200)
    
class DetailedMatchStatsView(views.APIView):
    """
    Vue qui retourne les matchs avec les stats détaillées pour un joueur.
    """
    @swagger_auto_schema(
    operation_description="Retourne la liste des matchs joués par un joueur avec les statistiques détaillées (KDA, rôle, items, sorts, vision, participants).",
    manual_parameters=[
        openapi.Parameter(
            name='puuid',
            in_=openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="Identifiant PUUID du joueur",
            required=False
        ),
        openapi.Parameter(
            name='riot_name',
            in_=openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="Nom Riot du joueur (ex: proctologue#urgot)",
            required=False
        ),
    ],
    responses={
        200: openapi.Response(
            description="Liste de matchs avec statistiques détaillées",
            examples={
                "application/json": [
                    {
                        "match_id": "EUW1_1234567890",
                        "champion": "Darius",
                        "position": "TOP",
                        "summoner_spells": [4, 12],
                        "kills": 8,
                        "deaths": 3,
                        "assists": 6,
                        "kda_ratio": 4.67,
                        "kill_participation": 70.0,
                        "items": [3078, 3111, 3053, 3065, 0, 0, 3363],
                        "wards_placed": 9,
                        "vision_score": 20,
                        "participant_id": 1,
                        "participants": [
                            {
                                "riot_name": "proctologue#urgot",
                                "champion": "Darius",
                                "team_id": 100,
                                "kills": 8,
                                "deaths": 3,
                                "assists": 6
                            },
                            {
                                "riot_name": "teammate#1234",
                                "champion": "Amumu",
                                "team_id": 100,
                                "kills": 2,
                                "deaths": 5,
                                "assists": 9
                            }
                            # ...
                        ]
                    }
                ]
            }
        ),
        400: openapi.Response(description="Paramètre manquant ou invalide"),
        }
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")

        if not puuid and not riot_name:
            return Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'."}, status=400)

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        if riot_name:
            filters["riot_name__iexact"] = riot_name

        # Récupère les participations du joueur
        user_participants = Participant.objects.filter(**filters).select_related("match")

        if not user_participants.exists():
            return Response({"message": "Aucun match trouvé."}, status=200)

        match_ids = [p.match_id for p in user_participants]

        # Récupère tous les participants des matchs concernés
        all_participants = Participant.objects.filter(match_id__in=match_ids)

        # Regroupement pour éviter les requêtes dans la boucle
        match_participants_map = defaultdict(list)
        team_kills_map = defaultdict(lambda: defaultdict(int))

        for p in all_participants:
            match_participants_map[p.match_id].append(p)
            team_kills_map[p.match_id][p.team_id] += p.kills

        results = []

        for p in user_participants:
            match = p.match
            match_id = match.match_id
            team_kills = team_kills_map[match_id][p.team_id]
            participants_list = match_participants_map[match_id]

            kda_ratio = (p.kills + p.assists) / max(1, p.deaths)
            kill_participation = (p.kills + p.assists) / max(1, team_kills)

            results.append({
                "match_id": match_id,
                "champion": p.champion_name,
                "position": p.team_position,
                "summoner_spells": [p.summoner1_id, p.summoner2_id],
                "kills": p.kills,
                "deaths": p.deaths,
                "assists": p.assists,
                "kda_ratio": round(kda_ratio, 2),
                "kill_participation": round(kill_participation * 100, 1),
                "items": [p.item0, p.item1, p.item2, p.item3, p.item4, p.item5, p.item6],
                "wards_placed": p.wards_placed,
                "wards_destroyed": max(0, p.vision_score - p.wards_placed),
                "vision_score": p.vision_score,
                "start_time": datetime.fromtimestamp(match.game_creation / 1000).isoformat(),
                "end_time": datetime.fromtimestamp(match.game_end_ts / 1000).isoformat(),
                "participant_id": p.participant_id,
                "participants": [
                    {
                        "riot_name": mp.riot_name,
                        "champion": mp.champion_name,
                        "team_id": mp.team_id,
                        "kills": mp.kills,
                        "deaths": mp.deaths,
                        "assists": mp.assists
                    }
                    for mp in participants_list
                ]
            })

        # Pagination DRF
        paginator = PageNumberPagination()
        paginated_results = paginator.paginate_queryset(results, request)
        return paginator.get_paginated_response(paginated_results)
    
class RoleChampionStatsView(views.APIView):
    """
    Vue enrichie : retourne les statistiques par champion pour un rôle donné
    (KDA, CS/M, DPM, KP, WR, etc.) uniquement sur les parties classiques.
    """

    @swagger_auto_schema(
        operation_description="Retourne les statistiques enrichies par champion pour un rôle spécifique ou tous les rôles (classique uniquement).",
        manual_parameters=[
            openapi.Parameter('puuid', openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter('riot_name', openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur"),
            openapi.Parameter('role', openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Rôle (TOP, JUNGLE, etc. ou ALL)", required=False),
        ],
        responses={200: openapi.Response(description="Statistiques enrichies par champion")}
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")
        selected_role = request.GET.get("role", "ALL").upper()

        if not puuid and not riot_name:
            return Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'."}, status=400)

        filters = {"match__queue_id__in": [400,420, 430, 440]}  # jeux classiques uniquement
        if puuid:
            filters["puuid"] = puuid
        if riot_name:
            filters["riot_name__iexact"] = riot_name
        user_participants = Participant.objects.filter(**filters).select_related("match")

        if not user_participants.exists():
            return Response({"message": "Aucune donnée trouvée."}, status=200)

        # Récupération de tous les participants pour calculer le kill participation
        match_ids = [p.match_id for p in user_participants]
        all_participants = Participant.objects.filter(match_id__in=match_ids)

        team_kills_map = defaultdict(lambda: defaultdict(int))  # match_id -> team_id -> kills
        for p in all_participants:
            team_kills_map[p.match_id][p.team_id] += p.kills

        stats = {}
        for p in user_participants:
            role = (p.team_position or "").upper()
            if role in ["", "UNKNOWN"]:
                continue
            if selected_role and selected_role != "ALL" and role != selected_role:
                continue

            champ = p.champion_name
            champ_data = stats.setdefault(champ, {
                "games": 0,
                "wins": 0,
                "total_kills": 0,
                "total_deaths": 0,
                "total_assists": 0,
                "total_damage": 0,
                "total_minions": 0,
                "total_time": 0,
                "total_kp_ratio": 0.0,
            })

            champ_data["games"] += 1
            champ_data["wins"] += int(p.win)
            champ_data["total_kills"] += p.kills
            champ_data["total_deaths"] += p.deaths
            champ_data["total_assists"] += p.assists
            champ_data["total_damage"] += p.total_damage_dealt_champs
            champ_data["total_minions"] += p.total_minions_killed + p.neutral_minions_killed
            champ_data["total_time"] += p.time_played

            team_kills = team_kills_map[p.match.match_id][p.team_id]
            if team_kills > 0:
                champ_data["total_kp_ratio"] += (p.kills + p.assists) / team_kills
            else:
                champ_data["total_kp_ratio"] += 0

        # Calcul des moyennes
        result = {}
        for champ, data in stats.items():
            games = data["games"]
            time_minutes = data["total_time"] / 60 if data["total_time"] > 0 else 1

            avg_kills = data["total_kills"] / games
            avg_deaths = data["total_deaths"] / games
            avg_assists = data["total_assists"] / games
            kda = (data["total_kills"] + data["total_assists"]) / max(1, data["total_deaths"])
            cs_per_min = data["total_minions"] / time_minutes
            dpm = data["total_damage"] / time_minutes
            kp_percent = (data["total_kp_ratio"] / games) * 100
            win_rate = (data["wins"] / games) * 100

            result[champ] = {
                "games": games,
                "win_rate": round(win_rate, 1),
                "kda": round(kda, 2),
                "cs_per_min": round(cs_per_min, 2),
                "dpm": round(dpm, 2),
                "kp": round(kp_percent, 1),
            }

        return Response(result, status=200)
    
class GlobalStatsView(views.APIView):
    """
    Vue qui retourne les statistiques globales d’un joueur (temps de jeu, winrate, placement, etc.).
    """

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur")
        ]
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        elif riot_name:
            filters["riot_name__iexact"] = riot_name
        else:
            return Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'."}, status=400)

        participants = list(
            Participant.objects.filter(**filters)
            .select_related("match")
            .order_by("match__game_creation")
        )

        if not participants:
            return Response({"message": "Aucune donnée trouvée."}, status=200)

        total_games = len(participants)
        first_match_ts = participants[0].match.game_creation // 1000
        last_match_ts = participants[-1].match.game_end_ts // 1000

        first_match = datetime.utcfromtimestamp(first_match_ts)
        last_match = datetime.utcfromtimestamp(last_match_ts)

        total_time_played_sec = sum(p.time_played for p in participants)
        total_days_range = max(1, (last_match - first_match).days + 1)

        avg_games_per_day = round(total_games / total_days_range, 2)
        avg_time_per_day_sec = total_time_played_sec / total_days_range
        percent_time_playing = round((avg_time_per_day_sec / (24 * 3600)) * 100, 2)

        def format_duration(seconds):
            td = timedelta(seconds=seconds)
            days = td.days
            hours, remainder = divmod(td.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{days}d:{hours:02}h:{minutes:02}m:{seconds:02}s"

        # Nombre de personnes rencontrées (hors soi-même)
        user_puuid = puuid or participants[0].puuid
        match_ids = [p.match_id for p in participants]
        all_match_participants = list(
            Participant.objects.filter(match_id__in=match_ids).only("match_id", "team_id", "puuid")
        )
        by_match = defaultdict(list)
        for participant in all_match_participants:
            by_match[participant.match_id].append(participant)

        total_players_met = (
            Participant.objects.filter(match_id__in=match_ids)
            .exclude(puuid=user_puuid)
            .values("puuid")
            .distinct()
            .count()
        )

        # Moyenne de nouveaux et anciens joueurs rencontrés
        per_game_coop = defaultdict(set)
        for p in participants:
            allies = [
                ally.puuid
                for ally in by_match[p.match_id]
                if ally.team_id == p.team_id and ally.puuid != p.puuid
            ]
            per_game_coop[p.match.match_id].update(allies)

        coop_counts = list(per_game_coop.values())
        unique_seen = set()
        new_per_game, old_per_game = 0, 0
        for puuids in coop_counts:
            new = len([x for x in puuids if x not in unique_seen])
            old = len([x for x in puuids if x in unique_seen])
            unique_seen.update(puuids)
            new_per_game += new
            old_per_game += old
        avg_new = round(new_per_game / total_games, 2)
        avg_old = round(old_per_game / total_games, 2)

        # Stat par map et side
        map_stats = {
            11: {"name": "Summoner's Rift", "blue": {"W": 0, "L": 0}, "red": {"W": 0, "L": 0}},
            12: {"name": "Howling Abyss ARAM", "blue": {"W": 0, "L": 0}, "red": {"W": 0, "L": 0}},
        }

        for p in participants:
            map_id = p.match.map_id
            if map_id not in map_stats:
                continue
            side = "blue" if p.team_id == 100 else "red"
            result = "W" if p.win else "L"
            map_stats[map_id][side][result] += 1

        def build_side_record(data):
            total = data["W"] + data["L"]
            return f'{data["W"]}W {data["L"]}L ({round(100 * data["W"] / max(1, total), 2)}%)', total

        result = {
            "games_analyzed": total_games,
            "oldest_match": first_match.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "most_recent_match": last_match.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "total_time_played": format_duration(total_time_played_sec),
            "avg_time_per_day": str(timedelta(seconds=int(avg_time_per_day_sec))),
            "avg_games_per_day": avg_games_per_day,
            "percent_time_played": f"{percent_time_playing}%",
            "people_met": total_players_met,
            "avg_new_people_per_game": avg_new,
            "avg_old_friends_per_game": avg_old,
        }

        for map_id, mdata in map_stats.items():
            map_name = mdata["name"]
            blue_record, blue_total = build_side_record(mdata["blue"])
            red_record, red_total = build_side_record(mdata["red"])

            result[f"{map_name} team placement"] = f"{blue_total} games (Blue) / {red_total} games (Red)"
            result[f"W-L Record on {map_name} Blue side"] = blue_record
            result[f"W-L Record on {map_name} Red side"] = red_record

        # Streaks (optionnel - lourd)
        wins = [p.win for p in participants]
        longest_streak = 0
        current_streak = 0
        total_streaks = 0
        streak_count = 0

        for win in wins:
            if win:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
            else:
                if current_streak > 0:
                    total_streaks += current_streak
                    streak_count += 1
                current_streak = 0
        if current_streak > 0:
            total_streaks += current_streak
            streak_count += 1

        avg_streak = round(total_streaks / max(1, streak_count), 3)

        result["average_winning_streak"] = avg_streak
        result["longest_winning_streak"] = longest_streak

        return Response(result, status=200)

class GameModesPlayedStatsView(views.APIView):
    """
    Vue qui retourne les statistiques par mode de jeu (queue_id) pour un joueur donné.
    """

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur"),
        ],
        responses={200: openapi.Response(description="Statistiques par mode de jeu")}
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        elif riot_name:
            filters["riot_name__iexact"] = riot_name
        else:
            return Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'."}, status=400)

        participants = Participant.objects.filter(**filters).select_related("match")

        if not participants.exists():
            return Response({"message": "Aucune donnée trouvée."}, status=200)

        mode_stats = defaultdict(lambda: {
            "queue": None,
            "total_games": 0,
            "wins": 0,
            "losses": 0,
            "surrenders": 0,
            "total_time_played": 0,
        })

        for p in participants:
            qid = p.match.queue_id
            data = mode_stats[qid]
            data["queue"] = qid
            data["total_games"] += 1
            data["total_time_played"] += p.time_played

            if p.win:
                data["wins"] += 1
            else:
                data["losses"] += 1
                if p.time_played < 600:  # 10 minutes = early surrender
                    data["surrenders"] += 1

        total_games_all_modes = sum([d["total_games"] for d in mode_stats.values()])
        
        result = []
        for qid, data in sorted(mode_stats.items()):
            total = data["total_games"]
            wins = data["wins"]
            losses = data["losses"]
            surrenders = data["surrenders"]
            time_total = data["total_time_played"]

            avg_duration_sec = time_total / total if total else 0
            queue_name = QUEUE_NAMES.get(qid, f"Unknown ({qid})")
            result.append({
                "queue": qid,
                "total_games": total,
                "queue_name": queue_name,
                "percent_share": round((total / total_games_all_modes) * 100, 2),
                "wins": wins,
                "losses": losses,
                "surrenders": surrenders,
                "winrate": round((wins / total) * 100, 2) if total > 0 else 0.0,
                "avg_game_duration": str(timedelta(seconds=int(avg_duration_sec))),
                "total_time_spent": str(timedelta(seconds=time_total)),
            })

        return Response(result, status=200)

class DeathTimelineView(views.APIView):
    """
    Retourne l’évolution des morts par joueur dans un match donné, groupées par minute, avec les coordonnées.
    """

    @swagger_auto_schema(
        operation_description="Retourne, pour un match donné, l'évolution des morts groupées par minute pour chaque joueur avec coordonnées (x, y).",
        manual_parameters=[
            openapi.Parameter(
                'match_id',
                openapi.IN_QUERY,
                description="Identifiant du match (ex: EUW1_1234567890)",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Morts par joueur avec coordonnées",
                examples={
                    "application/json": {
                        "teemo#yordle": [
                            {
                                "minute": 3,
                                "deaths": 2,
                                "positions": [{"x": 1200, "y": 2200}, {"x": 1225, "y": 2250}]
                            }
                        ]
                    }
                }
            ),
            400: "Paramètre manquant"
        }
    )
    def get(self, request):
        match_id = request.GET.get("match_id")
        if not match_id:
            return Response({"error": "Paramètre 'match_id' requis."}, status=400)

        deaths = Death.objects.filter(match__match_id=match_id).order_by("timestamp")
        if not deaths.exists():
            return Response({"message": "Aucune mort trouvée pour ce match."}, status=200)

        # Pré-chargement des participants
        participants = Participant.objects.filter(match__match_id=match_id)
        participant_map = {
            (p.participant_id, p.match.match_id): p.riot_name for p in participants
        }

        # Structure : riot_name -> minute -> list of positions
        grouped = defaultdict(lambda: defaultdict(list))

        for death in deaths:
            key = (death.participant_id, death.match.match_id)
            riot_name = participant_map.get(key, f"Participant {death.participant_id}")
            minute = death.timestamp // 60000
            grouped[riot_name][minute].append({"x": death.x, "y": death.y})

        # Formattage final
        result = {}
        for riot_name, minute_data in grouped.items():
            result[riot_name] = [
                {
                    "minute": minute,
                    "positions": coords
                }
                for minute, coords in sorted(minute_data.items())
            ]

        return Response(result)
    
class GameDurationOutcomeDistributionView(views.APIView):
    """
    Retourne, pour un joueur donné, la distribution des parties par durée (en minutes), 
    avec le nombre de wins, losses, surrenders à chaque durée.
    """

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur")
        ],
        responses={200: openapi.Response(description="Distribution des parties par durée (minutes) avec issues")}
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")

        if not puuid and not riot_name:
            return Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'."}, status=400)

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        else:
            filters["riot_name__iexact"] = riot_name

        participants = Participant.objects.filter(**filters).select_related("match")

        if not participants.exists():
            return Response({"message": "Aucune donnée trouvée."}, status=200)

        dist = defaultdict(lambda: {"wins": 0, "losses": 0, "surrenders": 0})

        for p in participants:
            duration_min = round(p.time_played / 60)  # en minutes
            if p.time_played < 600:  # moins de 10 minutes
                dist[duration_min]["surrenders"] += 1
            elif p.win:
                dist[duration_min]["wins"] += 1
            else:
                dist[duration_min]["losses"] += 1

        result = [
            {"duration_min": dur, **vals}
            for dur, vals in sorted(dist.items())
        ]

        return Response(result)
    
class FindPuidView(views.APIView):
    @swagger_auto_schema(
        operation_description="Récupérer le puid a partir du summoner name",
        manual_parameters=[
            openapi.Parameter( 'riot_id', openapi.IN_QUERY, description="riot_id", type=openapi.TYPE_STRING ),
            openapi.Parameter( 'region', openapi.IN_QUERY, description="region", type=openapi.TYPE_STRING ),
        ],
        responses={
            200: openapi.Response(
                description="user puid",
                examples={"application/json": {"riot_id": 'ilanizer123#EUW'}}
            )
        }
    )
    def get(self, request):
        try:
            riot_id = request.GET.get("riot_id")
            region = request.GET.get("region")
            print(riot_id)
            if not riot_id :
                return Response({"status": "veuillez rajouter riot_id dans le GET"}, status=200)
            resultat = run_find_puid(riot_id,region)
            return Response({"puid":  resultat}, status=200)
        except:
            return Response({"status": "une erreur a eu lieu"}, status=404)
class FindNewUsernameView(views.APIView):
    @swagger_auto_schema(
        operation_description="Récupérer le nouveau summoner name",
        manual_parameters=[
            openapi.Parameter( 'puuid', openapi.IN_QUERY, description="puuid", type=openapi.TYPE_STRING ),
            openapi.Parameter( 'region', openapi.IN_QUERY, description="region", type=openapi.TYPE_STRING ),
        ],
        responses={
            200: openapi.Response(
                description="new summoner name",
                examples={"application/json": {"summoner_name": 'ilanizer123#EUW'}}
            )
        }
    )
    def get(self, request):
        try:
            puuid = request.GET.get("puuid")
            region = request.GET.get("region")
            if not puuid :
                return Response({"status": "veuillez rajouter puuid dans le GET"}, status=200)
            resultat = get_riot_id_by_puuid(puuid,region)
            return Response({"summoner_name": "#".join(resultat)}, status=200)
        except:
            return Response({"status": "une erreur a eu lieu"}, status=404)

class DeathMapImageView(views.APIView):
    @swagger_auto_schema(
        operation_description="Retourne, pour un match donné, l'évolution des morts groupées par minute pour chaque joueur avec coordonnées (x, y).",
        manual_parameters=[
            openapi.Parameter(
                'match_id',
                openapi.IN_QUERY,
                description="Identifiant du match (ex: EUW1_1234567890)",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            400: "Paramètre manquant"
        }
    )
    def get(self, request, **kwargs):
        match_id = request.GET.get("match_id")
        deaths = Death.objects.filter(match__match_id=match_id).order_by("timestamp")
        if not deaths.exists():
            return HttpResponse("Aucune mort trouvée", status=404)

        # Participants pour nommer les joueurs
        participants = Participant.objects.filter(match__match_id=match_id).order_by('participant_id')
        participant_map = {
            (p.participant_id, p.match.match_id): p.riot_name for p in participants
        }
        # Groupement comme dans DeathTimelineView
        grouped = defaultdict(lambda: defaultdict(list))
        for death in deaths:
            key = (death.participant_id, death.match.match_id)
            riot_name = participant_map.get(key, f"Participant {death.participant_id}")
            minute = death.timestamp // 60000
            grouped[riot_name][minute].append({"x": death.x, "y": death.y})

        # ---- Matplotlib : préparation de l'image
        fig, ax = plt.subplots(figsize=(10, 10))

        # Réserve de l'espace à droite pour la légende
        fig.subplots_adjust(right=0.75)

        try:
            map_image = plt.imread("static/summoners_rift_map.jpg")
            ax.imshow(map_image, extent=[0, 15000, 0, 15000])
        except Exception:
            ax.set_facecolor('gray')
            ax.set_title("Carte manquante (image non chargée)")

        # Palette de couleurs
        colors = [
            "red", "blue", "green", "orange", "purple", "pink", "cyan", "lime", "gold", "brown"
        ]
        color_map = {}
        i = 0

        for riot_name, minute_data in grouped.items():
            if riot_name not in color_map:
                color_map[riot_name] = colors[i % len(colors)]
                i += 1

            first_point = True  # ✅ Flag pour afficher une seule fois le label

            for minute, coords in minute_data.items():
                x = [c["x"] for c in coords]
                y = [15000 - c["y"] for c in coords]

                if first_point:
                    ax.scatter(x, y, s=80, c=color_map[riot_name], label=riot_name)
                    first_point = False
                else:
                    ax.scatter(x, y, s=80, c=color_map[riot_name])


        ax.set_title(f"Morts par joueur – Match {match_id}")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

        # Déplace la légende à droite
        ax.legend(
            loc='center left',
            bbox_to_anchor=(1.02, 0.5),  # (x, y) en coordonnées de la figure
            borderaxespad=0,
            fontsize='small'
        )

        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')  # `tight` pour que la légende soit incluse dans l’image
        plt.close(fig)
        buffer.seek(0)

        return HttpResponse(buffer.read(), content_type='image/png')

class DeathMapImageByUserView(views.APIView):
    @swagger_auto_schema(
        operation_description="Affiche la carte des morts d’un joueur pour un match donné.",
        manual_parameters=[
            openapi.Parameter('match_id', openapi.IN_QUERY, description="ID du match (ex: EUW1_1234567890)", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('riot_name', openapi.IN_QUERY, description="Nom Riot du joueur", type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('puuid', openapi.IN_QUERY, description="PUUID du joueur", type=openapi.TYPE_STRING, required=False),
        ],
        responses={400: "Paramètre manquant ou invalide"}
    )
    def get(self, request, **kwargs):
        match_id = request.GET.get("match_id")
        riot_name = request.GET.get("riot_name")
        puuid = request.GET.get("puuid")

        if not match_id:
            return HttpResponse("Paramètre 'match_id' requis.", status=400)
        if not riot_name and not puuid:
            return HttpResponse("Veuillez fournir 'riot_name' ou 'puuid'", status=400)

        # Trouver le participant correspondant
        filters = {"match__match_id": match_id}
        if riot_name:
            filters["riot_name__iexact"] = riot_name
        if puuid:
            filters["puuid"] = puuid

        try:
            participant = Participant.objects.get(**filters)
        except Participant.DoesNotExist:
            return HttpResponse("Aucun participant trouvé pour ce match.", status=404)

        # Récupérer ses morts
        deaths = Death.objects.filter(match__match_id=match_id, participant_id=participant.participant_id).order_by("timestamp")
        if not deaths.exists():
            return HttpResponse("Aucune mort trouvée pour ce joueur.", status=404)

        # Préparation des coordonnées
        coords = [{"x": d.x, "y": d.y} for d in deaths]
        x = [c["x"] for c in coords]
        y = [15000 - c["y"] for c in coords]  # inversion Y

        # ---- Matplotlib ----
        fig, ax = plt.subplots(figsize=(10, 10))
        fig.subplots_adjust(right=0.85)

        try:
            map_image = plt.imread("static/summoners_rift_map.jpg")
            ax.imshow(map_image, extent=[0, 15000, 0, 15000])
        except Exception:
            ax.set_facecolor('gray')
            ax.set_title("Carte manquante (image non chargée)")

        ax.scatter(x, y, s=80, c="red", label=participant.riot_name or participant.puuid)

        ax.set_title(f"Morts de {participant.riot_name or participant.puuid} – Match {match_id}")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), borderaxespad=0, fontsize='small')

        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        plt.close(fig)
        buffer.seek(0)

        return HttpResponse(buffer.read(), content_type='image/png')

class CSPerMinuteEvolutionView(views.APIView):
    """
    Retourne l'évolution des CS par minute pour un joueur donné, avec options de filtre par poste et champion.
    """
    @swagger_auto_schema(
        operation_description="Retourne l'évolution des CS/min pour un joueur, avec filtre possible par poste et champion.",
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur"),
            openapi.Parameter("position", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Poste joué (TOP, JUNGLE, etc.)"),
            openapi.Parameter("champion_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom du champion (ex: Darius)"),
        ]
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")
        position = request.GET.get("position", "").upper()
        champion_name = request.GET.get("champion_name", "")

        if not puuid and not riot_name:
            return Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'."}, status=400)

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        else:
            filters["riot_name__iexact"] = riot_name

        if position:
            filters["team_position__iexact"] = position
        if champion_name:
            filters["champion_name__iexact"] = champion_name

        participants = Participant.objects.filter(**filters).select_related("match").order_by("match__game_creation")

        if not participants.exists():
            return Response({"message": "Aucune donnée trouvée."}, status=200)

        result = []
        for p in participants:
            cs_total = p.total_minions_killed + p.neutral_minions_killed
            time_minutes = p.time_played / 60 if p.time_played else 1
            cs_per_min = cs_total / time_minutes

            result.append({
                "match_id": p.match.match_id,
                "date": datetime.fromtimestamp(p.match.game_creation / 1000).strftime('%Y-%m-%d %H:%M'),
                "champion": p.champion_name,
                "cs": cs_total,
                "cs_objectif_7":round(time_minutes, 0)*7,
                "cs_objectif_8":round(time_minutes, 0)*8,
                "cs_objectif_9":round(time_minutes, 0)*9,
                "cs_objectif_10":round(time_minutes, 0)*10,
                "duration_min": round(time_minutes, 2),
                "cs_per_min": round(cs_per_min, 2),
                "position": p.team_position
            })

        return Response(result, status=200)

class CSPerMinuteGraphView(views.APIView): 
    """
    Affiche un graphique de l'évolution des CS par minute pour un joueur donné,
    avec filtres facultatifs par poste et champion, sans chevauchement des points.
    """
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur"),
            openapi.Parameter("position", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Poste joué (TOP, JUNGLE, etc.)"),
            openapi.Parameter("champion_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom du champion (ex: Darius)"),
        ]
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")
        position = request.GET.get("position", "").upper()
        champion_name = request.GET.get("champion_name", "")

        if not puuid and not riot_name:
            return HttpResponse("Veuillez fournir 'puuid' ou 'riot_name'", status=400)

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        else:
            filters["riot_name__iexact"] = riot_name
        if position:
            filters["team_position__iexact"] = position
        if champion_name:
            filters["champion_name__iexact"] = champion_name

        participants = Participant.objects.filter(**filters).select_related("match").order_by("match__game_creation")
        if not participants.exists():
            return HttpResponse("Aucune donnée trouvée.", status=404)

        # Préparation des données
        cs_per_min_values = []
        labels = []

        for p in participants:
            if p.time_played < 600:
                continue  # on ignore les parties de moins de 10 min

            time_minutes = p.time_played / 60
            cs_total = p.total_minions_killed + p.neutral_minions_killed
            cs_per_min = cs_total / time_minutes

            match_time = datetime.fromtimestamp(p.match.game_creation / 1000)
            cs_per_min_values.append(cs_per_min)
            labels.append(f"{match_time.strftime('%d/%m')}")

        if not cs_per_min_values:
            return HttpResponse("Aucune partie >10min trouvée.", status=200)

        x_indexes = list(range(1, len(cs_per_min_values) + 1))

        # Tracé
        plt.figure(figsize=(30, 6))
        plt.plot(x_indexes, cs_per_min_values, marker='o', linestyle='-', linewidth=2, color="#1f77b4", label="CS/min")
        plt.fill_between(x_indexes, cs_per_min_values, alpha=0.1, color="#1f77b4")

        # Moyenne
        avg_value = np.mean(cs_per_min_values)
        plt.axhline(avg_value, color='gray', linestyle='--', linewidth=1, label=f"Moyenne : {avg_value:.2f}")

        plt.xticks(x_indexes, labels, rotation=45, ha='right', fontsize=9)
        plt.title("Évolution des CS/min par partie", fontsize=14)
        plt.xlabel("Date", fontsize=12)
        plt.ylabel("CS par minute", fontsize=12)
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.legend()
        plt.tight_layout()

        # Export PNG
        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        plt.close()
        buffer.seek(0)

        return HttpResponse(buffer.read(), content_type="image/png")

class CSPerMinuteLast10GamesGraphView(views.APIView):
    """
    Graphique de l’évolution des CS/min pour un joueur, sans superposition (1 point par partie).
    """
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur"),
            openapi.Parameter("position", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Poste joué (TOP, JUNGLE, etc.)"),
            openapi.Parameter("champion_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom du champion (ex: Darius)"),
            openapi.Parameter("nb_game", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Nombre de parties"),
        ]
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")
        position = request.GET.get("position", "").upper()
        champion_name = request.GET.get("champion_name", "")
        nb_game = int(request.GET.get("nb_game", 10))

        if not puuid and not riot_name:
            return HttpResponse("Veuillez fournir 'puuid' ou 'riot_name'", status=400)

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        else:
            filters["riot_name__iexact"] = riot_name
        if position:
            filters["team_position__iexact"] = position
        if champion_name:
            filters["champion_name__iexact"] = champion_name

        participants = Participant.objects.filter(**filters).select_related("match").order_by("-match__game_creation")[:nb_game * 2]
        if not participants.exists():
            return HttpResponse("Aucune donnée trouvée.", status=404)

        # Garde seulement les parties de plus de 10 minutes
        filtered_participants = []
        for p in participants:
            if p.time_played >= 600:
                filtered_participants.append(p)
            if len(filtered_participants) == nb_game:
                break
        if not filtered_participants:
            return Response({"message": "Aucune partie valide (>10min) trouvée."}, status=200)

        cs_per_min_values = []
        labels = []

        for p in reversed(filtered_participants):  # ancien -> récent
            time_minutes = p.time_played / 60
            cs_total = p.total_minions_killed + p.neutral_minions_killed
            cs_per_min = cs_total / time_minutes
            date_str = datetime.fromtimestamp(p.match.game_creation / 1000).strftime("%d/%m")
            cs_per_min_values.append(cs_per_min)
            labels.append(f"{p.champion_name}\n{date_str}")

        x_indexes = list(range(1, len(cs_per_min_values) + 1))

        # --- Matplotlib Styling ---
        plt.figure(figsize=(14, 6))
        plt.plot(x_indexes, cs_per_min_values, marker='o', linestyle='-', linewidth=2, color="#1f77b4", label="CS/min")
        plt.fill_between(x_indexes, cs_per_min_values, alpha=0.1, color="#1f77b4")

        avg_cs = np.mean(cs_per_min_values)
        plt.axhline(avg_cs, linestyle='--', color='gray', linewidth=1, label=f"Moyenne : {avg_cs:.2f}")

        plt.xticks(x_indexes, labels, rotation=45, ha="right", fontsize=9)
        plt.title("Évolution des CS/min sur les 10 dernières parties (>10min)", fontsize=14)
        plt.xlabel("Partie (Champion & Date)")
        plt.ylabel("CS par minute")
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.legend()
        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        plt.close()
        buffer.seek(0)

        return HttpResponse(buffer.read(), content_type="image/png")

class AverageCsPerMinByChampionView(views.APIView):
    """
    Retourne la moyenne des CS/min par champion sur les 10 dernières parties d’un joueur donné.
    """
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur"),
        ]
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")

        if not puuid and not riot_name:
            return Response({"error": "Veuillez fournir 'puuid' ou 'riot_name'."}, status=400)

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        else:
            filters["riot_name__iexact"] = riot_name

        participants = Participant.objects.filter(**filters).select_related("match").order_by("-match__game_creation")[:10]

        if not participants.exists():
            return Response({"message": "Aucune donnée trouvée."}, status=200)

        champ_stats = defaultdict(lambda: {"cs": 0, "duration": 0, "games": 0})

        for p in participants:
            cs_total = p.total_minions_killed + p.neutral_minions_killed
            time_minutes = p.time_played / 60 if p.time_played else 1

            champ_stats[p.champion_name]["cs"] += cs_total
            champ_stats[p.champion_name]["duration"] += time_minutes
            champ_stats[p.champion_name]["games"] += 1

        result = {}
        for champ, stats in champ_stats.items():
            if stats["duration"] > 0:
                avg_cs_per_min = stats["cs"] / stats["duration"]
                result[champ] = {
                    "games": stats["games"],
                    "avg_cs_per_min": round(avg_cs_per_min, 2)
                }

        return Response(result, status=200)

class TriggerChampionItemImportViewSet(views.APIView):
    """
    Déclenche l'importation des champions et/ou items depuis Riot Games via un thread.
    """

    @swagger_auto_schema(
        operation_description="Lancer l'importation des champions et/ou des items depuis Riot Games.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=[],
            properties={
                "champions": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="Importer les champions ? (true/false)"
                ),
                "items": openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="Importer les items ? (true/false)"
                ),
            },
        ),
        responses={
            202: openapi.Response(description="Import lancé avec succès."),
            500: openapi.Response(description="Erreur serveur.")
        }
    )
    def post(self, request, **kwargs):
        champions = request.data.get("champions", False)
        items = request.data.get("items", False)

        try:
            def import_task():
                importer = RiotDataImporter()
                if champions:
                    importer.import_champions()
                if items:
                    importer.import_items()

            thread = threading.Thread(target=import_task)
            thread.start()

            return Response(
                {"message": "Import lancé en arrière-plan", "champions": champions, "items": items},
                status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _compose_row(user_p, all_participants):
    """Construit une ligne CSV pour le participant utilisateur."""
    match = user_p.match

    allies = [p for p in all_participants if p.team_id == user_p.team_id and p.participant_id != user_p.participant_id]
    enemies = [p for p in all_participants if p.team_id != user_p.team_id]

    allies_sorted = sorted(allies, key=lambda x: x.participant_id)[:4]
    enemies_sorted = sorted(enemies, key=lambda x: x.participant_id)[:5]

    ts_utc = datetime.fromtimestamp(match.game_creation / 1000).isoformat() + "Z"

    row = {
        "match_id": match.match_id,
        "timestamp_utc": ts_utc,
        "win": 1 if user_p.win else 0,
        "queue_type": str(match.queue_id),
        "patch": match.game_version,
        "duration_sec": match.game_duration or user_p.time_played,
        "side": SIDE_MAP.get(user_p.team_id, "UNKNOWN"),
        "rank_tier": user_p.rank_tier or "",
        "lane": (user_p.team_position or user_p.individual_position or "UNKNOWN").upper(),
        "champion": user_p.champion_name,
        "k": user_p.kills, "d": user_p.deaths, "a": user_p.assists,
        "cs": user_p.total_minions_killed + user_p.neutral_minions_killed,
        "gold": user_p.gold_earned,
        "vision_score": user_p.vision_score,
    }

    for i, ally in enumerate(allies_sorted, start=1):
        row[f"ally_champ{i}"] = ally.champion_name
    for i in range(len(allies_sorted) + 1, 5):
        row[f"ally_champ{i}"] = ""

    for i, enemy in enumerate(enemies_sorted, start=1):
        row[f"enemy_champ{i}"] = enemy.champion_name
    for i in range(len(enemies_sorted) + 1, 6):
        row[f"enemy_champ{i}"] = ""

    row.update({
        "kills_10": "", "deaths_10": "", "assists_10": "",
        "gold_10": "", "cs_10": ""
    })
    return row

class ExportMatchesCSVView(views.APIView):
    # permission_classes = [IsAuthenticatedOrReadOnly]
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("puuid", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="PUUID du joueur"),
            openapi.Parameter("riot_name", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="Nom Riot du joueur")
        ],
        responses={200: openapi.Response(description="export les partie en csv pour train une ia")}
    )
    def get(self, request):
        puuid = request.GET.get("puuid")
        riot_name = request.GET.get("riot_name")
        if not puuid and not riot_name:
            return StreamingHttpResponse("Missing puuid or riot_name", status=400)

        filters = {}
        if puuid:
            filters["puuid"] = puuid
        if riot_name:
            filters["riot_name__iexact"] = riot_name

        user_qs = Participant.objects.filter(**filters).select_related("match")
        if not user_qs.exists():
            return StreamingHttpResponse("No data found", status=404)

        match_ids = list(user_qs.values_list("match__match_id", flat=True))
        all_participants = list(
            Participant.objects.filter(match__match_id__in=match_ids).select_related("match")
        )
        by_match = {}
        for p in all_participants:
            by_match.setdefault(p.match.match_id, []).append(p)

        # colonnes fixes
        columns = [
            "match_id","timestamp_utc","win","queue_type","patch","duration_sec",
            "side","rank_tier","lane","champion",
            "k","d","a","cs","gold","vision_score",
            "ally_champ1","ally_champ2","ally_champ3","ally_champ4",
            "enemy_champ1","enemy_champ2","enemy_champ3","enemy_champ4","enemy_champ5",
            "kills_10","deaths_10","assists_10","gold_10","cs_10"
        ]

        # construit toutes les lignes
        rows = []
        for user_p in user_qs:
            rows.append(_compose_row(user_p, by_match[user_p.match.match_id]))

        # generator qui yield les lignes
        def row_iter():
            yield columns
            for r in rows:
                yield [r.get(c, "") for c in columns]

        class Echo:
            def write(self, value): return value

        writer = csv.writer(Echo())
        response = StreamingHttpResponse((writer.writerow(r) for r in row_iter()),
                                         content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="matches.csv"'
        return response
    
class PredictView(views.APIView):
    @swagger_auto_schema(
        operation_description="Prédiction à partir d'un vecteur de features",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["features"],
            properties={
                "features": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_NUMBER),
                    description="Vecteur: [x1, x2, ...]"
                )
            },
            example={"features": [1.2, 3.4, 5.6]}
        ),
        responses={
            200: openapi.Response(
                description="OK",
                schema=PredictResponseSerializer,
                examples={
                    "application/json": {"prediction": 0.73, "proba": 0.88}
                },
            ),
            400: "Requête invalide",
        }
    )

    def post(self, request):
        ser = PredictRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        
        X = np.array(ser.validated_data["features"]).reshape(1, -1)
        print (X)
        model = get_model()
        try:
            y = model.predict(X)
            data = {"prediction": float(y[0])}
            if hasattr(model, "predict_proba"):
                data["proba"] = float(model.predict_proba(X).max(axis=1)[0])

            out = PredictResponseSerializer(data=data)
            out.is_valid(raise_exception=True)
            return Response(out.data)

        except Exception as e:
            return Response({"detail": f"Inference error: {e}"},
                            status=status.HTTP_400_BAD_REQUEST)

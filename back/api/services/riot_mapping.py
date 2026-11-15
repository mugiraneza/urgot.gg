"""
Correspondance unique entre le JSON brut Riot (match-v5, stocke dans Match.objet_complet)
et les colonnes des modeles.

Ce module est utilise a la fois par l'import (riot_importer) et par la reprise de donnees
(commande `backfill_objet_complet`) : toute nouvelle donnee Riot se mappe ici, une seule fois.

Les fonctions sont pures (aucun acces base ni reseau), donc testables et rejouables.
"""
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- Match

# colonne du modele -> cle dans info
MATCH_INFO_FIELDS = {
    "game_id": "gameId",
    "game_name": "gameName",
    "game_start_ts": "gameStartTimestamp",
    "platform_id": "platformId",
    "end_of_game_result": "endOfGameResult",
}


def match_raw_fields(stored_match: Dict[str, Any]) -> Dict[str, Any]:
    """Champs Match ajoutes pour couvrir tout le JSON (hors champs historiques)."""
    info = stored_match.get("info") or {}
    metadata = stored_match.get("metadata") or {}
    fields = {column: info.get(key) for column, key in MATCH_INFO_FIELDS.items()}
    fields["game_mode_mutators"] = info.get("gameModeMutators") or []
    fields["data_version"] = metadata.get("dataVersion")
    return fields


MATCH_BACKFILL_FIELDS = list(MATCH_INFO_FIELDS) + ["game_mode_mutators", "data_version"]


# --------------------------------------------------------------------------- Team

def team_raw_fields(team: Dict[str, Any]) -> Dict[str, Any]:
    # Les objectifs (atakhan, horde, voidGator, ...) sont deja tous dans la table Objective.
    return {"feats": team.get("feats") or {}}


TEAM_BACKFILL_FIELDS = ["feats"]


# --------------------------------------------------------------------------- Participant

# Champs de premier niveau non mappes jusqu'ici : colonne -> cle Riot
PARTICIPANT_TOP_LEVEL_FIELDS = {
    # identite
    "riot_id_game_name": "riotIdGameName",
    "riot_id_tagline": "riotIdTagline",
    "summoner_id": "summonerId",
    "summoner_name": "summonerName",
    "summoner_level": "summonerLevel",
    "profile_icon": "profileIcon",
    "position_assigned_by_matchmaking": "positionAssignedByMatchmaking",
    "selected_role_preferences": "selectedRolePreferences",
    # combat / multikills
    "double_kills": "doubleKills",
    "triple_kills": "tripleKills",
    "unreal_kills": "unrealKills",
    "largest_critical_strike": "largestCriticalStrike",
    "bounty_level": "bountyLevel",
    "first_blood_assist": "firstBloodAssist",
    "first_tower_assist": "firstTowerAssist",
    "total_time_spent_dead": "totalTimeSpentDead",
    "total_units_healed": "totalUnitsHealed",
    # degats detailles
    "total_damage_dealt": "totalDamageDealt",
    "physical_damage_dealt": "physicalDamageDealt",
    "physical_damage_dealt_to_champions": "physicalDamageDealtToChampions",
    "physical_damage_taken": "physicalDamageTaken",
    "magic_damage_dealt": "magicDamageDealt",
    "magic_damage_dealt_to_champions": "magicDamageDealtToChampions",
    "magic_damage_taken": "magicDamageTaken",
    "true_damage_dealt": "trueDamageDealt",
    "true_damage_dealt_to_champions": "trueDamageDealtToChampions",
    "true_damage_taken": "trueDamageTaken",
    "damage_dealt_to_buildings": "damageDealtToBuildings",
    "damage_dealt_to_epic_monsters": "damageDealtToEpicMonsters",
    # objectifs / structures
    "baron_kills": "baronKills",
    "dragon_kills": "dragonKills",
    "turret_takedowns": "turretTakedowns",
    "inhibitors_lost": "inhibitorsLost",
    "nexus_kills": "nexusKills",
    "nexus_lost": "nexusLost",
    "nexus_takedowns": "nexusTakedowns",
    # farm / vision / objets
    "total_ally_jungle_minions_killed": "totalAllyJungleMinionsKilled",
    "total_enemy_jungle_minions_killed": "totalEnemyJungleMinionsKilled",
    "sight_wards_bought_in_game": "sightWardsBoughtInGame",
    "items_purchased": "itemsPurchased",
    "consumables_purchased": "consumablesPurchased",
    "role_bound_item": "roleBoundItem",
    # sorts
    "spell1_casts": "spell1Casts",
    "spell2_casts": "spell2Casts",
    "spell3_casts": "spell3Casts",
    "spell4_casts": "spell4Casts",
    "summoner1_casts": "summoner1Casts",
    "summoner2_casts": "summoner2Casts",
    # modes Arena / Swarm
    "placement": "placement",
    "subteam_placement": "subteamPlacement",
    "player_subteam_id": "playerSubteamId",
    # fin de partie / comportement
    "eligible_for_progression": "eligibleForProgression",
    "game_ended_in_ignb_surrender": "gameEndedInIGNBSurrender",
    "team_ignb_surrendered": "teamIGNBSurrendered",
    "caused_game_end_from_ignb_surrender": "causedGameEndFromIGNBSurrender",
    "was_afk": "wasAfk",
    "was_premade_with_ignb_game_end_causer": "wasPremadeWithIGNBGameEndCauser",
    "was_premade_with_severe_transgressor": "wasPremadeWithSevereTransgressor",
    "was_severe_transgressor": "wasSevereTransgressor",
}

# Valeurs de `challenges` promues en colonnes car utiles pour trier / filtrer.
# Le dictionnaire complet reste disponible dans Participant.challenges.
PARTICIPANT_CHALLENGE_FIELDS = {
    # correction : ces deux valeurs sont dans `challenges`, pas au premier niveau
    "solo_kills": "soloKills",
    "stealth_wards_placed": "stealthWardsPlaced",
    # ajouts
    "kill_participation": "killParticipation",
    "team_damage_percentage": "teamDamagePercentage",
    "damage_taken_on_team_percentage": "damageTakenOnTeamPercentage",
    "vision_score_per_minute": "visionScorePerMinute",
    "control_wards_placed": "controlWardsPlaced",
    "turret_plates_taken": "turretPlatesTaken",
    "skillshots_hit": "skillshotsHit",
    "skillshots_dodged": "skillshotsDodged",
    "ability_uses": "abilityUses",
    "effective_heal_and_shielding": "effectiveHealAndShielding",
    "max_cs_advantage_on_lane_opponent": "maxCsAdvantageOnLaneOpponent",
    "laning_phase_gold_exp_advantage": "laningPhaseGoldExpAdvantage",
    "early_laning_phase_gold_exp_advantage": "earlyLaningPhaseGoldExpAdvantage",
}

AUGMENT_KEYS = [f"playerAugment{index}" for index in range(1, 7)]


def _player_augments(participant: Dict[str, Any]) -> List[int]:
    # Riot met 0 dans les emplacements vides : on ne garde que les vrais augments.
    return [participant[key] for key in AUGMENT_KEYS if participant.get(key)]


def participant_raw_fields(participant: Dict[str, Any]) -> Dict[str, Any]:
    """
    Champs Participant derives du JSON brut, en plus des champs historiques de l'import.
    `PlayerScore0..11` ne sont pas stockes a part : ce sont les memes valeurs que `missions`.
    """
    challenges: Dict[str, Any] = participant.get("challenges") or {}
    fields: Dict[str, Optional[Any]] = {
        column: participant.get(key) for column, key in PARTICIPANT_TOP_LEVEL_FIELDS.items()
    }
    fields.update({column: challenges.get(key) for column, key in PARTICIPANT_CHALLENGE_FIELDS.items()})
    fields["challenges"] = challenges
    fields["missions"] = participant.get("missions") or {}
    fields["player_behavior"] = participant.get("PlayerBehavior") or {}
    fields["player_augments"] = _player_augments(participant)
    return fields


PARTICIPANT_BACKFILL_FIELDS = (
    list(PARTICIPANT_TOP_LEVEL_FIELDS)
    + list(PARTICIPANT_CHALLENGE_FIELDS)
    + ["challenges", "missions", "player_behavior", "player_augments"]
)

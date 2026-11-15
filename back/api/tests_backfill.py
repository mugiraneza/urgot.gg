from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from api.models import Match, Participant, Team
from api.services.riot_importer import insert_participants, insert_teams
from api.services.riot_mapping import (
    MATCH_BACKFILL_FIELDS,
    PARTICIPANT_BACKFILL_FIELDS,
    match_raw_fields,
    participant_raw_fields,
    team_raw_fields,
)

MATCH_ID = "EUW1_4242"


def build_raw_participant(participant_id=1, team_id=100):
    return {
        "participantId": participant_id,
        "puuid": f"player-{participant_id}",
        "riotIdGameName": f"player{participant_id}",
        "riotIdTagline": "euw",
        "teamId": team_id,
        "championId": "Urgot",
        "championName": "Urgot",
        "individualPosition": "TOP",
        "role": "SOLO",
        "summoner1Id": 4,
        "summoner2Id": 12,
        "kills": 10,
        "deaths": 2,
        "assists": 8,
        "totalDamageDealtToChampions": 25000,
        "damageSelfMitigated": 12000,
        "totalHeal": 1000,
        "totalDamageTaken": 18000,
        "largestKillingSpree": 6,
        "pentaKills": 0,
        "quadraKills": 1,
        "visionScore": 30,
        "wardsPlaced": 12,
        "totalMinionsKilled": 210,
        "neutralMinionsKilled": 12,
        "timeCCingOthers": 45,
        **{f"item{slot}": 0 for slot in range(7)},
        "goldEarned": 15000,
        "goldSpent": 14000,
        "champLevel": 18,
        "champExperience": 18000,
        "win": True,
        "firstBloodKill": False,
        "firstTowerKill": True,
        "teamPosition": "TOP",
        "timePlayed": 1800,
        # champs non mappes avant la migration 0014
        "doubleKills": 3,
        "tripleKills": 1,
        "magicDamageDealtToChampions": 4000,
        "trueDamageTaken": 900,
        "spell4Casts": 7,
        "summonerLevel": 312,
        "firstBloodAssist": True,
        "wasAfk": False,
        "playerAugment1": 55,
        "playerAugment2": 0,
        "missions": {"playerScore0": 1.0},
        "PlayerBehavior": {"PlayerBehavior_IsHeroInCombat": 1},
        "challenges": {
            "soloKills": 2,
            "stealthWardsPlaced": 7,
            "killParticipation": 0.64,
            "teamDamagePercentage": 0.31,
            "turretPlatesTaken": 3,
            "SWARM_KillEnemy": 0,
            "legendaryItemUsed": [6631, 3071],
        },
    }


def build_raw_match():
    return {
        "metadata": {"dataVersion": "2", "matchId": MATCH_ID},
        "info": {
            "gameId": 4242,
            "gameName": "teambuilder-match-4242",
            "gameStartTimestamp": 1000,
            "platformId": "EUW1",
            "endOfGameResult": "GameComplete",
            "gameModeMutators": ["mapskin_ha_bilgewater"],
            "teams": [
                {
                    "teamId": 100,
                    "win": True,
                    "bans": [],
                    "feats": {"FIRST_BLOOD": {"featState": 1}},
                    "objectives": {
                        "baron": {"first": True, "kills": 1},
                        "dragon": {"first": False, "kills": 2},
                        "tower": {"first": True, "kills": 7},
                    },
                }
            ],
            "participants": [build_raw_participant(1), build_raw_participant(2)],
        },
    }


class RiotMappingTests(SimpleTestCase):
    def test_participant_fields_cover_top_level_challenges_and_json_blocks(self):
        fields = participant_raw_fields(build_raw_participant())

        self.assertEqual(set(fields), set(PARTICIPANT_BACKFILL_FIELDS))
        self.assertEqual(fields["double_kills"], 3)
        self.assertEqual(fields["magic_damage_dealt_to_champions"], 4000)
        self.assertIs(fields["first_blood_assist"], True)
        # corrige : lus dans `challenges`, plus au premier niveau
        self.assertEqual(fields["solo_kills"], 2)
        self.assertEqual(fields["stealth_wards_placed"], 7)
        self.assertEqual(fields["kill_participation"], 0.64)
        # le dictionnaire complet est conserve
        self.assertEqual(fields["challenges"]["legendaryItemUsed"], [6631, 3071])
        self.assertEqual(fields["missions"], {"playerScore0": 1.0})
        self.assertEqual(fields["player_behavior"], {"PlayerBehavior_IsHeroInCombat": 1})
        # les emplacements d'augment vides (0) sont ignores
        self.assertEqual(fields["player_augments"], [55])
        # cle absente du JSON -> None, pas d'erreur
        self.assertIsNone(fields["nexus_lost"])

    def test_match_and_team_fields(self):
        raw = build_raw_match()
        match_fields = match_raw_fields(raw)
        self.assertEqual(set(match_fields), set(MATCH_BACKFILL_FIELDS))
        self.assertEqual(match_fields["game_id"], 4242)
        self.assertEqual(match_fields["data_version"], "2")
        self.assertEqual(match_fields["game_mode_mutators"], ["mapskin_ha_bilgewater"])
        self.assertEqual(team_raw_fields(raw["info"]["teams"][0])["feats"]["FIRST_BLOOD"]["featState"], 1)


class BackfillObjetCompletCommandTests(TestCase):
    def setUp(self):
        raw = build_raw_match()
        # Simule une donnee importee avant la migration : colonnes historiques seulement.
        Match.objects.create(
            match_id=MATCH_ID,
            game_creation=1,
            game_end_ts=2,
            game_duration=1800,
            game_mode="CLASSIC",
            game_type="MATCHED_GAME",
            game_version="1.0",
            map_id=11,
            queue_id=420,
            objet_complet=raw,
        )
        insert_teams(MATCH_ID, raw["info"]["teams"])
        with patch("api.services.riot_importer.get_rank_entry_for_puuid", return_value={}):
            insert_participants(MATCH_ID, raw["info"]["participants"])
        Participant.objects.update(**{field: None for field in PARTICIPANT_BACKFILL_FIELDS})
        Team.objects.update(feats=None)

    def run_command(self, *args):
        output = StringIO()
        call_command("backfill_objet_complet", *args, stdout=output)
        return output.getvalue()

    def test_dry_run_writes_nothing(self):
        output = self.run_command("--dry-run")

        self.assertIn("2 participants calcules", output)
        self.assertIsNone(Match.objects.get(pk=MATCH_ID).data_version)
        self.assertIsNone(Participant.objects.get(participant_id=1).challenges)

    def test_backfill_fills_new_columns_and_is_idempotent(self):
        self.run_command()

        match = Match.objects.get(pk=MATCH_ID)
        participant = Participant.objects.get(match=match, participant_id=1)
        self.assertEqual(match.data_version, "2")
        self.assertEqual(match.platform_id, "EUW1")
        self.assertEqual(Team.objects.get(match=match).feats["FIRST_BLOOD"]["featState"], 1)
        self.assertEqual(participant.solo_kills, 2)
        self.assertEqual(participant.triple_kills, 1)
        self.assertEqual(participant.challenges["turretPlatesTaken"], 3)
        self.assertEqual(participant.player_augments, [55])

        # Deuxieme passage : plus rien a reprendre.
        self.assertIn("0 match(s) a reprendre", self.run_command())

    def test_reports_participants_missing_from_database(self):
        Participant.objects.filter(participant_id=2).delete()

        output = self.run_command()

        self.assertIn("1 match(s) incomplets", output)
        self.assertIn("joueur 2", output)
        self.assertEqual(Participant.objects.get(participant_id=1).solo_kills, 2)

    def test_importer_fills_new_columns_directly(self):
        raw_participant = build_raw_participant(3)
        with patch("api.services.riot_importer.get_rank_entry_for_puuid", return_value={}):
            insert_participants(MATCH_ID, [raw_participant])

        participant = Participant.objects.get(participant_id=3)
        self.assertEqual(participant.solo_kills, 2)
        self.assertEqual(participant.spell4_casts, 7)
        self.assertEqual(participant.missions, {"playerScore0": 1.0})

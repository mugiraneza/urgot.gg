from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Champion, Item, Match, Participant
from .views import running_imports


def participant_defaults(**overrides):
    data = {
        "puuid": "player-1",
        "riot_name": "player#euw",
        "team_id": 100,
        "champion_name": "Urgot",
        "individual_position": "TOP",
        "role": "SOLO",
        "summoner1_id": 4,
        "summoner2_id": 12,
        "kills": 1,
        "deaths": 1,
        "assists": 1,
        "total_damage_dealt_champs": 1000,
        "damage_self_mitigated": 1000,
        "total_heal": 0,
        "total_damage_taken": 1000,
        "largest_killing_spree": 1,
        "penta_kills": 0,
        "quadra_kills": 0,
        "vision_score": 10,
        "wards_placed": 5,
        "total_minions_killed": 100,
        "neutral_minions_killed": 0,
        "time_ccing_others": 0,
        "gold_earned": 10000,
        "gold_spent": 9000,
        "champ_level": 15,
        "champ_experience": 10000,
        "win": True,
        "first_blood_kill": False,
        "first_tower_kill": False,
        "team_position": "TOP",
        "time_played": 1800,
    }
    data.update(overrides)
    return data


class PositionStatsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_only_last_60_days_are_counted(self):
        now_ms = int(timezone.now().timestamp() * 1000)
        old_ms = int((timezone.now() - timedelta(days=90)).timestamp() * 1000)

        recent_match = Match.objects.create(
            match_id="EUW1_1",
            game_creation=now_ms,
            game_end_ts=now_ms,
            game_duration=1800,
            game_mode="CLASSIC",
            game_type="MATCHED_GAME",
            game_version="1.0",
            map_id=11,
            queue_id=420,
        )
        old_match = Match.objects.create(
            match_id="EUW1_2",
            game_creation=old_ms,
            game_end_ts=old_ms,
            game_duration=1800,
            game_mode="CLASSIC",
            game_type="MATCHED_GAME",
            game_version="1.0",
            map_id=11,
            queue_id=420,
        )

        Participant.objects.create(
            match=recent_match, participant_id=1, **participant_defaults(team_position="TOP")
        )
        Participant.objects.create(
            match=old_match, participant_id=1, **participant_defaults(team_position="JUNGLE")
        )

        response = self.client.get(reverse("poste-last-60-day"), {"puuid": "player-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"TOP": 1})


class TriggerMatchImportViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        running_imports.clear()

    def tearDown(self):
        running_imports.clear()

    @patch("api.views.threading.Thread")
    def test_import_is_started_only_once(self, thread_cls):
        thread = thread_cls.return_value
        thread.is_alive.return_value = False

        response = self.client.post(
            reverse("import-matches"),
            {"riot_id": "player#euw", "region": "europe"},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        thread_cls.assert_called_once()
        thread.start.assert_called_once()


class GlobalStatsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_people_met_excludes_current_player_when_filtering_by_riot_name(self):
        now_ms = int(timezone.now().timestamp() * 1000)
        match = Match.objects.create(
            match_id="EUW1_3",
            game_creation=now_ms,
            game_end_ts=now_ms,
            game_duration=1800,
            game_mode="CLASSIC",
            game_type="MATCHED_GAME",
            game_version="1.0",
            map_id=11,
            queue_id=420,
        )

        Participant.objects.create(
            match=match,
            participant_id=1,
            **participant_defaults(puuid="player-1", riot_name="player#euw", team_id=100),
        )
        Participant.objects.create(
            match=match,
            participant_id=2,
            **participant_defaults(puuid="ally-1", riot_name="ally#euw", team_id=100),
        )
        Participant.objects.create(
            match=match,
            participant_id=3,
            **participant_defaults(puuid="enemy-1", riot_name="enemy#euw", team_id=200),
        )

        response = self.client.get(reverse("global-stats"), {"riot_name": "player#euw"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["people_met"], 2)


class FrontApiViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.champion = Champion.objects.create(
            champion_id="Urgot",
            key="6",
            name="Urgot",
            title="the Dreadnought",
            image_full="Urgot.png",
            image_sprite="champion4.png",
            image_group="champion",
            image_x=0,
            image_y=0,
            image_w=48,
            image_h=48,
            lore="lore",
            blurb="blurb",
            partype="Mana",
        )
        self.item = Item.objects.create(
            item_id="1001",
            name="Boots of Speed",
            description="desc",
            colloq="boots",
            plaintext="plain",
            image_full="1001.png",
            image_sprite="item0.png",
            image_group="item",
            image_x=0,
            image_y=0,
            image_w=48,
            image_h=48,
        )
        now_ms = int(timezone.now().timestamp() * 1000)
        self.match = Match.objects.create(
            match_id="EUW1_4",
            game_creation=now_ms,
            game_end_ts=now_ms,
            game_duration=1800,
            game_mode="CLASSIC",
            game_type="MATCHED_GAME",
            game_version="1.0",
            map_id=11,
            queue_id=420,
        )
        Participant.objects.create(
            match=self.match,
            participant_id=1,
            **participant_defaults(
                puuid="player-1",
                riot_name="player#euw",
                team_id=100,
                champion=self.champion,
                item0=self.item,
                rank_tier="GOLD",
                rank_division="II",
                rank_lp=47,
            ),
        )
        Participant.objects.create(
            match=self.match,
            participant_id=2,
            **participant_defaults(
                puuid="ally-1",
                riot_name="ally#euw",
                team_id=100,
                champion=self.champion,
                rank_tier="SILVER",
                rank_division="I",
                rank_lp=12,
            ),
        )
        Participant.objects.create(
            match=self.match,
            participant_id=3,
            **participant_defaults(
                puuid="enemy-1",
                riot_name="enemy#euw",
                team_id=200,
                champion=self.champion,
                rank_tier="PLATINUM",
                rank_division="IV",
                rank_lp=88,
            ),
        )

    def test_front_dashboard_reads_local_db(self):
        response = self.client.get(reverse("front-dashboard"), {"riot_name": "player#euw"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "local_db")
        self.assertIn("overview", payload)
        self.assertIn("champions", payload)
        self.assertIn("modes", payload)
        self.assertIn("cs_evolution", payload)

    def test_front_matches_reads_local_db(self):
        response = self.client.get(reverse("front-matches"), {"riot_name": "player#euw"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "local_db")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["match_id"], "EUW1_4")
        self.assertEqual(
            payload["results"][0]["champion_image_url"],
            "http://testserver/api/assets/champions/champions/Urgot.png",
        )
        self.assertEqual(
            payload["results"][0]["items"][0]["image_url"],
            "http://testserver/api/assets/items/items/1001.png",
        )
        self.assertEqual(payload["results"][0]["rank_label"], "GOLD II - 47 LP")
        participant_ranks = {participant["riot_name"]: participant["rank_label"] for participant in payload["results"][0]["participants"]}
        self.assertEqual(participant_ranks["player#euw"], "GOLD II - 47 LP")
        self.assertEqual(participant_ranks["ally#euw"], "SILVER I - 12 LP")

from datetime import timedelta
import requests
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient

from .models import Ban, Champion, Item, Match, Objective, Participant, RankSnapshot, Team, TrackedSummoner
from .services.riot_importer import (
    BoundedCache,
    _get_json,
    find_accounts_by_riot_id,
    get_account_by_riot_id,
    get_rank_entry_for_puuid,
    get_puuid,
    insert_participants,
    insert_skill_orders,
    normalize_account_region,
    repair_incomplete_match_imports,
    store_rank_snapshot,
)
from .services.tracked_imports import import_all_tracked_summoners
from .views import running_imports


class FakeRiotResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.response = self

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


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


class RiotHttpClientTests(TestCase):
    def test_bounded_cache_evicts_oldest_entry(self):
        cache_store = BoundedCache(max_size=2)

        cache_store.set("first", {"value": 1})
        cache_store.set("second", {"value": 2})
        cache_store.set("third", {"value": 3})

        self.assertIsNone(cache_store.get("first"))
        self.assertEqual(cache_store.get("second"), {"value": 2})
        self.assertEqual(cache_store.get("third"), {"value": 3})

    def test_bounded_cache_refreshes_recently_used_entry(self):
        cache_store = BoundedCache(max_size=2)

        cache_store.set("first", {"value": 1})
        cache_store.set("second", {"value": 2})
        self.assertEqual(cache_store.get("first"), {"value": 1})

        cache_store.set("third", {"value": 3})

        self.assertEqual(cache_store.get("first"), {"value": 1})
        self.assertIsNone(cache_store.get("second"))
        self.assertEqual(cache_store.get("third"), {"value": 3})

    @patch("api.services.riot_importer._get_json", return_value={"puuid": "player-puuid"})
    def test_get_puuid_normalizes_platform_region_to_account_cluster(self, mock_get_json):
        puuid = get_puuid("player", "EUW", "euw1")

        self.assertEqual(puuid, "player-puuid")
        mock_get_json.assert_called_once_with(
            "https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/player/EUW"
        )

    @patch(
        "api.services.riot_importer._get_json",
        return_value={"puuid": "player-puuid", "gameName": "player", "tagLine": "EUW"},
    )
    def test_get_account_by_riot_id_returns_account_payload_with_region(self, mock_get_json):
        account = get_account_by_riot_id("player", "EUW", "euw1")

        self.assertEqual(
            account,
            {
                "region": "europe",
                "puuid": "player-puuid",
                "gameName": "player",
                "tagLine": "EUW",
            },
        )
        mock_get_json.assert_called_once()

    @patch("api.services.riot_importer._get_json", return_value={"puuid": "encoded-puuid"})
    def test_get_puuid_url_encodes_riot_id_parts(self, mock_get_json):
        puuid = get_puuid("The Player", "EU/W", "europe")

        self.assertEqual(puuid, "encoded-puuid")
        mock_get_json.assert_called_once_with(
            "https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/The%20Player/EU%2FW"
        )

    def test_normalize_account_region_rejects_unknown_value(self):
        with self.assertRaises(ValueError):
            normalize_account_region("unknown")

    @patch("api.services.riot_importer.get_account_by_riot_id")
    def test_find_accounts_by_riot_id_collects_accounts_across_regions(self, mock_get_account):
        def side_effect(_name, _tag, region):
            if region == "europe":
                return {"region": "europe", "puuid": "eu-puuid", "gameName": "player", "tagLine": "EUW"}
            if region == "americas":
                return {"region": "americas", "puuid": "na-puuid", "gameName": "player", "tagLine": "EUW"}
            raise requests.HTTPError(response=FakeRiotResponse(status_code=404))

        mock_get_account.side_effect = side_effect

        matches = find_accounts_by_riot_id("player", "EUW")

        self.assertEqual(
            matches,
            [
                {"region": "europe", "puuid": "eu-puuid", "gameName": "player", "tagLine": "EUW"},
                {"region": "americas", "puuid": "na-puuid", "gameName": "player", "tagLine": "EUW"},
            ],
        )

    @patch("api.services.riot_importer.REQUEST_MAX_RETRIES", 3)
    @patch("api.services.riot_importer.REQUEST_RETRY_BASE_DELAY", 0.1)
    @patch("api.services.riot_importer.time.sleep")
    @patch("api.services.riot_importer.requests.get")
    def test_get_json_retries_transient_connection_errors(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            requests.ConnectionError("network unreachable"),
            FakeRiotResponse(payload={"ok": True}),
        ]

        payload = _get_json("https://europe.api.riotgames.com/test")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("api.services.riot_importer.REQUEST_MAX_RETRIES", 3)
    @patch("api.services.riot_importer.REQUEST_RETRY_BASE_DELAY", 0.1)
    @patch("api.services.riot_importer.time.sleep")
    @patch("api.services.riot_importer.requests.get")
    def test_get_json_raises_after_retry_budget_is_exhausted(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.ConnectionError("network unreachable")

        with self.assertRaises(requests.ConnectionError):
            _get_json("https://europe.api.riotgames.com/test")

        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("api.services.riot_importer.REQUEST_MAX_RETRIES", 2)
    @patch("api.services.riot_importer.time.sleep")
    @patch("api.services.riot_importer.requests.get")
    def test_get_json_uses_retry_after_for_rate_limits(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            FakeRiotResponse(status_code=429, headers={"Retry-After": "7"}),
            FakeRiotResponse(payload={"ok": True}),
        ]

        payload = _get_json("https://europe.api.riotgames.com/test")

        self.assertEqual(payload, {"ok": True})
        mock_sleep.assert_called_once_with(7.0)


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
        cache.clear()

    def tearDown(self):
        running_imports.clear()
        cache.clear()

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

    @patch("api.views.threading.Thread")
    def test_import_stores_recent_riot_id_in_cache(self, thread_cls):
        thread = thread_cls.return_value
        thread.is_alive.return_value = False

        self.client.post(
            reverse("import-matches"),
            {"riot_id": "Recent#EUW", "region": "europe"},
            format="json",
        )

        response = self.client.get(reverse("front-recent-riot-ids"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0], "Recent#EUW")

    @patch("api.views.threading.Thread")
    def test_import_registers_tracked_summoner(self, thread_cls):
        thread = thread_cls.return_value
        thread.is_alive.return_value = False

        self.client.post(
            reverse("import-matches"),
            {"riot_id": "Tracked#EUW", "region": "europe"},
            format="json",
        )

        self.assertTrue(
            TrackedSummoner.objects.filter(riot_name="Tracked#EUW", region="europe", is_active=True).exists()
        )


class FindPuuidViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch(
        "api.views.run_find_puid",
        return_value={
            "region": "europe",
            "puuid": "resolved-puuid",
            "gameName": "player",
            "tagLine": "EUW",
        },
    )
    def test_find_puuid_view_returns_puuid_for_platform_region(self, mock_run_find_puid):
        response = self.client.get(
            reverse("findusmmoner-puid"),
            {"riot_id": "player#EUW", "region": "euw1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["puuid"], "resolved-puuid")
        self.assertEqual(response.json()["region"], "europe")
        mock_run_find_puid.assert_called_once_with("player#EUW", "euw1")


class TrackedImportsServiceTests(TestCase):
    @patch("api.services.tracked_imports.run_match_import")
    def test_import_all_tracked_summoners_processes_all_active_entries(self, mock_run_match_import):
        TrackedSummoner.objects.create(riot_name="player1#EUW", region="europe", is_active=True)
        TrackedSummoner.objects.create(riot_name="player2#NA1", region="americas", is_active=True)
        TrackedSummoner.objects.create(riot_name="inactive#EUW", region="europe", is_active=False)

        summary = import_all_tracked_summoners()

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["error"], 0)
        self.assertEqual(mock_run_match_import.call_count, 2)
        self.assertEqual(
            set(TrackedSummoner.objects.filter(last_import_status="success").values_list("riot_name", flat=True)),
            {"player1#EUW", "player2#NA1"},
        )


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
        cache.clear()
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
        RankSnapshot.objects.create(
            match=self.match,
            puuid="player-1",
            riot_name="player#euw",
            queue_type="RANKED_SOLO_5x5",
            tier="GOLD",
            rank_division="II",
            league_points=47,
            wins=12,
            losses=9,
        )

        response = self.client.get(reverse("front-dashboard"), {"riot_name": "player#euw"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "local_db")
        self.assertIn("overview", payload)
        self.assertIn("champions", payload)
        self.assertIn("modes", payload)
        self.assertIn("cs_evolution", payload)
        self.assertEqual(payload["lp_evolution"][0]["lp"], 47)
        self.assertEqual(payload["lp_evolution"][0]["elo_score"], 1447)
        self.assertEqual(payload["lp_evolution"][0]["rank_label"], "GOLD II - 47 LP")

    def test_front_dashboard_includes_solo_and_flex_ranks(self):
        RankSnapshot.objects.create(
            match=self.match,
            puuid="player-1",
            riot_name="player#euw",
            queue_type="RANKED_SOLO_5x5",
            tier="GOLD",
            rank_division="II",
            league_points=47,
            wins=12,
            losses=9,
        )
        RankSnapshot.objects.create(
            match=self.match,
            puuid="player-1",
            riot_name="player#euw",
            queue_type="RANKED_FLEX_SR",
            tier="PLATINUM",
            rank_division="IV",
            league_points=23,
            wins=8,
            losses=7,
        )

        response = self.client.get(reverse("front-dashboard"), {"riot_name": "player#euw"})

        self.assertEqual(response.status_code, 200)
        ranks = response.json()["overview"]["player_ranks"]
        self.assertEqual(ranks["solo"]["label"], "GOLD II - 47 LP")
        self.assertEqual(ranks["solo"]["tier"], "GOLD")
        self.assertEqual(ranks["flex"]["label"], "PLATINUM IV - 23 LP")
        self.assertEqual(ranks["flex"]["tier"], "PLATINUM")

    def test_front_dashboard_lp_evolution_uses_rank_score_and_prefers_solo_queue(self):
        later_match = Match.objects.create(
            match_id="EUW1_5",
            game_creation=self.match.game_creation + 1000,
            game_end_ts=self.match.game_end_ts + 1000,
            game_duration=1800,
            game_mode="CLASSIC",
            game_type="MATCHED_GAME",
            game_version="1.0",
            map_id=11,
            queue_id=420,
        )
        RankSnapshot.objects.create(
            match=self.match,
            puuid="player-1",
            riot_name="player#euw",
            queue_type="RANKED_SOLO_5x5",
            tier="GOLD",
            rank_division="I",
            league_points=90,
        )
        RankSnapshot.objects.create(
            match=later_match,
            puuid="player-1",
            riot_name="player#euw",
            queue_type="RANKED_SOLO_5x5",
            tier="PLATINUM",
            rank_division="IV",
            league_points=10,
        )
        RankSnapshot.objects.create(
            match=later_match,
            puuid="player-1",
            riot_name="player#euw",
            queue_type="RANKED_FLEX_SR",
            tier="SILVER",
            rank_division="II",
            league_points=80,
        )

        response = self.client.get(reverse("front-dashboard"), {"riot_name": "player#euw"})

        self.assertEqual(response.status_code, 200)
        evolution = response.json()["lp_evolution"]
        self.assertEqual([entry["queue_type"] for entry in evolution], ["RANKED_SOLO_5x5", "RANKED_SOLO_5x5"])
        self.assertEqual([entry["elo_score"] for entry in evolution], [1590, 1610])

    @patch("api.views.build_profile_icon_url", return_value="https://ddragon.leagueoflegends.com/cdn/15.1.1/img/profileicon/1234.png")
    @patch("api.views.get_summoner_profile_by_puuid", return_value={"profileIconId": 1234})
    def test_front_dashboard_includes_profile_icon_url(self, get_summoner_profile_mock, _build_profile_icon_url_mock):
        response = self.client.get(reverse("front-dashboard"), {"riot_name": "player#euw"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["overview"]["player_profile_icon_url"],
            "https://ddragon.leagueoflegends.com/cdn/15.1.1/img/profileicon/1234.png",
        )
        get_summoner_profile_mock.assert_called_once_with("player-1", "euw1")

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
        self.assertIn("advanced_stats", payload["results"][0])
        self.assertIn("skill_order", payload["results"][0]["advanced_stats"])
        participant_ranks = {participant["riot_name"]: participant["rank_label"] for participant in payload["results"][0]["participants"]}
        self.assertEqual(participant_ranks["player#euw"], "GOLD II - 47 LP")
        self.assertEqual(participant_ranks["ally#euw"], "SILVER I - 12 LP")

    def test_front_dashboard_stores_recent_riot_ids(self):
        self.client.get(reverse("front-dashboard"), {"riot_name": "player#euw"})
        self.client.get(reverse("front-dashboard"), {"riot_name": "ally#euw"})
        self.client.get(reverse("front-dashboard"), {"riot_name": "player#euw"})

        response = self.client.get(reverse("front-recent-riot-ids"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], ["player#euw", "ally#euw"])


class RiotImporterAdvancedFieldsTests(TestCase):
    def setUp(self):
        self.match = Match.objects.create(
            match_id="EUW1_999",
            game_creation=1,
            game_end_ts=2,
            game_duration=1800,
            game_mode="CLASSIC",
            game_type="MATCHED_GAME",
            game_version="1.0",
            map_id=11,
            queue_id=420,
        )

    @patch("api.services.riot_importer.get_rank_entry_for_puuid", return_value={})
    def test_insert_participants_stores_advanced_stats_build_and_pings(self, _mock_rank):
        insert_participants(
            self.match.match_id,
            [
                {
                    "participantId": 1,
                    "puuid": "player-1",
                    "riotIdGameName": "player",
                    "riotIdTagline": "euw",
                    "teamId": 100,
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
                    "totalDamageShieldedOnTeammates": 2000,
                    "totalHealsOnTeammates": 1500,
                    "totalDamageTaken": 18000,
                    "damageDealtToObjectives": 9000,
                    "damageDealtToTurrets": 4500,
                    "largestKillingSpree": 6,
                    "killingSprees": 3,
                    "largestMultiKill": 2,
                    "pentaKills": 0,
                    "quadraKills": 0,
                    "turretKills": 2,
                    "inhibitorKills": 1,
                    "inhibitorTakedowns": 2,
                    "turretsLost": 3,
                    "objectivesStolen": 1,
                    "objectivesStolenAssists": 1,
                    "soloKills": 2,
                    "visionScore": 30,
                    "wardsPlaced": 12,
                    "detectorWardsPlaced": 3,
                    "visionWardsBoughtInGame": 2,
                    "wardsKilled": 4,
                    "stealthWardsPlaced": 7,
                    "totalMinionsKilled": 210,
                    "neutralMinionsKilled": 12,
                    "timeCCingOthers": 45,
                    "item0": 0,
                    "item1": 0,
                    "item2": 0,
                    "item3": 0,
                    "item4": 0,
                    "item5": 0,
                    "item6": 0,
                    "goldEarned": 15000,
                    "goldSpent": 14000,
                    "champLevel": 18,
                    "champExperience": 18000,
                    "lane": "TOP",
                    "championTransform": 0,
                    "win": True,
                    "firstBloodKill": False,
                    "firstTowerKill": True,
                    "teamPosition": "TOP",
                    "teamEarlySurrendered": False,
                    "gameEndedInEarlySurrender": False,
                    "gameEndedInSurrender": True,
                    "longestTimeSpentLiving": 800,
                    "totalTimeCCDealt": 120,
                    "timePlayed": 1800,
                    "baitPings": 1,
                    "dangerPings": 2,
                    "getBackPings": 3,
                    "allInPings": 4,
                    "perks": {
                        "styles": [
                            {"style": 8000, "selections": [{"perk": 8010}, {"perk": 9111}]},
                            {"style": 8400, "selections": [{"perk": 8444}, {"perk": 8451}]},
                        ],
                        "statPerks": {"offense": 5005, "flex": 5008, "defense": 5011},
                    },
                    "challenges": {
                        "visionScoreAdvantageLaneOpponent": 1.4,
                        "laneMinionsFirst10Minutes": 79.5,
                        "jungleCsBefore10Minutes": 0.0,
                        "goldPerMinute": 510.2,
                        "damagePerMinute": 880.4,
                    },
                }
            ],
        )

        participant = Participant.objects.get(match=self.match, participant_id=1)
        self.assertEqual(participant.total_damage_shielded_on_teammates, 2000)
        self.assertEqual(participant.damage_dealt_to_objectives, 9000)
        self.assertEqual(participant.detector_wards_placed, 3)
        self.assertEqual(participant.vision_score_advantage_lane_opponent, 1.4)
        self.assertEqual(participant.lane, "TOP")
        self.assertEqual(participant.gold_per_minute, 510.2)
        self.assertEqual(participant.game_ended_in_surrender, True)
        self.assertEqual(participant.bait_pings, 1)
        self.assertEqual(participant.ping_stats["allInPings"], 4)
        self.assertEqual(participant.primary_rune_style, 8000)
        self.assertEqual(participant.secondary_rune_style, 8400)
        self.assertEqual(participant.primary_rune_selections, [8010, 9111])
        self.assertEqual(participant.secondary_rune_selections, [8444, 8451])
        self.assertEqual(participant.stat_perks["offense"], 5005)

    @patch("api.services.riot_importer._get_json")
    def test_get_rank_entry_skips_bot_puuid(self, mock_get_json):
        self.assertEqual(get_rank_entry_for_puuid("BOT", "euw1"), {})
        mock_get_json.assert_not_called()

    def test_insert_skill_orders_stores_timeline_progression(self):
        Participant.objects.create(
            match=self.match,
            participant_id=1,
            **participant_defaults(),
        )

        insert_skill_orders(
            self.match.match_id,
            {
                "info": {
                    "frames": [
                        {
                            "events": [
                                {"type": "SKILL_LEVEL_UP", "participantId": 1, "skillSlot": 1},
                                {"type": "SKILL_LEVEL_UP", "participantId": 1, "skillSlot": 3},
                                {"type": "SKILL_LEVEL_UP", "participantId": 1, "skillSlot": 1},
                            ]
                        }
                    ]
                }
            },
        )

        participant = Participant.objects.get(match=self.match, participant_id=1)
        self.assertEqual(participant.skill_order, [1, 3, 1])

    @patch(
        "api.services.riot_importer.get_rank_entry_for_puuid",
        return_value={
            "queueType": "RANKED_SOLO_5x5",
            "tier": "PLATINUM",
            "rank": "IV",
            "leaguePoints": 23,
            "wins": 40,
            "losses": 35,
        },
    )
    def test_store_rank_snapshot_persists_current_rank_state(self, _mock_rank):
        store_rank_snapshot(self.match.match_id, "player-1", "player#euw")

        snapshot = RankSnapshot.objects.get(match=self.match, puuid="player-1")
        self.assertEqual(snapshot.queue_type, "RANKED_SOLO_5x5")
        self.assertEqual(snapshot.tier, "PLATINUM")
        self.assertEqual(snapshot.rank_division, "IV")
        self.assertEqual(snapshot.league_points, 23)


class RepairStoredImportsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.match = Match.objects.create(
            match_id="EUW1_555",
            game_creation=1,
            game_end_ts=2,
            game_duration=1800,
            game_mode="CLASSIC",
            game_type="MATCHED_GAME",
            game_version="1.0",
            map_id=11,
            queue_id=420,
            objet_complet={
                "metadata": {"matchId": "EUW1_555"},
                "info": {
                    "gameCreation": 1,
                    "gameEndTimestamp": 2,
                    "gameDuration": 1800,
                    "gameMode": "CLASSIC",
                    "gameType": "MATCHED_GAME",
                    "gameVersion": "1.0",
                    "mapId": 11,
                    "queueId": 420,
                    "participants": [
                        {
                            "participantId": 1,
                            "puuid": "player-1",
                            "riotIdGameName": "player",
                            "riotIdTagline": "euw",
                            "teamId": 100,
                            "championId": "Urgot",
                            "championName": "Urgot",
                            "individualPosition": "TOP",
                            "role": "SOLO",
                            "summoner1Id": 4,
                            "summoner2Id": 12,
                            "kills": 5,
                            "deaths": 3,
                            "assists": 7,
                            "totalDamageDealtToChampions": 15000,
                            "damageSelfMitigated": 10000,
                            "totalHeal": 250,
                            "totalDamageTaken": 12000,
                            "largestKillingSpree": 3,
                            "pentaKills": 0,
                            "quadraKills": 0,
                            "visionScore": 20,
                            "wardsPlaced": 8,
                            "totalMinionsKilled": 180,
                            "neutralMinionsKilled": 12,
                            "timeCCingOthers": 10,
                            "item0": 0,
                            "item1": 0,
                            "item2": 0,
                            "item3": 0,
                            "item4": 0,
                            "item5": 0,
                            "item6": 0,
                            "goldEarned": 12000,
                            "goldSpent": 11000,
                            "champLevel": 16,
                            "champExperience": 14000,
                            "win": True,
                            "firstBloodKill": False,
                            "firstTowerKill": False,
                            "teamPosition": "TOP",
                            "timePlayed": 1800,
                            "challenges": {},
                        },
                        {
                            "participantId": 2,
                            "puuid": "player-2",
                            "riotIdGameName": "ally",
                            "riotIdTagline": "euw",
                            "teamId": 200,
                            "championId": "Urgot",
                            "championName": "Urgot",
                            "individualPosition": "TOP",
                            "role": "SOLO",
                            "summoner1Id": 4,
                            "summoner2Id": 12,
                            "kills": 2,
                            "deaths": 5,
                            "assists": 4,
                            "totalDamageDealtToChampions": 9000,
                            "damageSelfMitigated": 8000,
                            "totalHeal": 100,
                            "totalDamageTaken": 14000,
                            "largestKillingSpree": 2,
                            "pentaKills": 0,
                            "quadraKills": 0,
                            "visionScore": 10,
                            "wardsPlaced": 5,
                            "totalMinionsKilled": 130,
                            "neutralMinionsKilled": 3,
                            "timeCCingOthers": 5,
                            "item0": 0,
                            "item1": 0,
                            "item2": 0,
                            "item3": 0,
                            "item4": 0,
                            "item5": 0,
                            "item6": 0,
                            "goldEarned": 9000,
                            "goldSpent": 8500,
                            "champLevel": 14,
                            "champExperience": 11000,
                            "win": False,
                            "firstBloodKill": False,
                            "firstTowerKill": False,
                            "teamPosition": "TOP",
                            "timePlayed": 1800,
                            "challenges": {},
                        },
                    ],
                    "teams": [
                        {
                            "teamId": 100,
                            "win": True,
                            "bans": [{"pickTurn": 1, "championId": "Urgot"}],
                            "objectives": {
                                "baron": {"first": False, "kills": 0},
                                "dragon": {"first": True, "kills": 2},
                                "tower": {"first": True, "kills": 8},
                            },
                        },
                        {
                            "teamId": 200,
                            "win": False,
                            "bans": [{"pickTurn": 1, "championId": "Urgot"}],
                            "objectives": {
                                "baron": {"first": False, "kills": 0},
                                "dragon": {"first": False, "kills": 1},
                                "tower": {"first": False, "kills": 3},
                            },
                        },
                    ],
                },
            },
        )

    @patch("api.services.riot_importer.get_rank_entry_for_puuid", return_value={})
    def test_repair_incomplete_match_imports_restores_missing_relations(self, _mock_rank):
        result = repair_incomplete_match_imports(match_id=self.match.match_id)

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["repaired"], 1)
        self.assertEqual(Participant.objects.filter(match=self.match).count(), 2)
        self.assertEqual(Team.objects.filter(match=self.match).count(), 2)
        self.assertEqual(Ban.objects.filter(match=self.match).count(), 2)
        self.assertEqual(Objective.objects.filter(match=self.match).count(), 6)

    @patch("api.views.repair_incomplete_match_imports")
    def test_repair_endpoint_returns_service_summary(self, repair_mock):
        repair_mock.return_value = {"checked": 1, "repaired": 1, "ok": 0, "skipped": 0, "details": []}

        response = self.client.post(
            reverse("repair-stored-imports"),
            {"match_id": self.match.match_id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["repaired"], 1)
        repair_mock.assert_called_once_with(match_id=self.match.match_id)

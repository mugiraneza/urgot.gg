from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

class Match(models.Model):
    match_id = models.CharField(primary_key=True, max_length=100)
    game_creation = models.BigIntegerField()
    game_end_ts = models.BigIntegerField()
    game_duration = models.IntegerField()
    game_mode = models.CharField(max_length=50)
    game_type = models.CharField(max_length=50)
    game_version = models.CharField(max_length=50)
    map_id = models.IntegerField()
    queue_id = models.IntegerField()
    tournament_code = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.match_id


class Participant(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    participant_id = models.IntegerField()
    puuid = models.CharField(max_length=100)
    riot_name = models.CharField(max_length=100)
    team_id = models.IntegerField()
    champion_id = models.IntegerField()
    champion_name = models.CharField(max_length=100)
    individual_position = models.CharField(max_length=50)
    role = models.CharField(max_length=50)
    summoner1_id = models.IntegerField()
    summoner2_id = models.IntegerField()
    kills = models.IntegerField()
    deaths = models.IntegerField()
    assists = models.IntegerField()
    total_damage_dealt_champs = models.IntegerField()
    damage_self_mitigated = models.IntegerField()
    total_heal = models.IntegerField()
    total_damage_taken = models.IntegerField()
    largest_killing_spree = models.IntegerField()
    penta_kills = models.IntegerField()
    quadra_kills = models.IntegerField()
    vision_score = models.IntegerField()
    wards_placed = models.IntegerField()
    total_minions_killed = models.IntegerField()
    neutral_minions_killed = models.IntegerField()
    time_ccing_others = models.IntegerField()
    item0 = models.IntegerField()
    item1 = models.IntegerField()
    item2 = models.IntegerField()
    item3 = models.IntegerField()
    item4 = models.IntegerField()
    item5 = models.IntegerField()
    item6 = models.IntegerField()
    gold_earned = models.IntegerField()
    gold_spent = models.IntegerField()
    champ_level = models.IntegerField()
    champ_experience = models.IntegerField()
    win = models.BooleanField()
    first_blood_kill = models.BooleanField()
    first_tower_kill = models.BooleanField()
    team_position = models.CharField(max_length=50)
    time_played = models.IntegerField()

    class Meta:
        unique_together = ('match', 'participant_id')


class Team(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team_id = models.IntegerField()
    win = models.BooleanField()
    baron_first = models.BooleanField()
    baron_kills = models.IntegerField()
    dragon_first = models.BooleanField()
    dragon_kills = models.IntegerField()
    tower_first = models.BooleanField()
    tower_kills = models.IntegerField()

    class Meta:
        unique_together = ('match', 'team_id')


class Ban(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team_id = models.IntegerField()
    pick_turn = models.IntegerField()
    champion_id = models.IntegerField()

    class Meta:
        unique_together = ('match', 'team_id', 'pick_turn')


class Objective(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team_id = models.IntegerField()
    type = models.CharField(max_length=50)
    first = models.BooleanField()
    kills = models.IntegerField()

    class Meta:
        unique_together = ('match', 'team_id', 'type')


class Death(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    timestamp = models.BigIntegerField()
    participant_id = models.IntegerField()
    killer_id = models.IntegerField()
    assisting_participant_ids = models.TextField()
    x = models.IntegerField()
    y = models.IntegerField()

    class Meta:
        unique_together = ('match', 'timestamp', 'participant_id')



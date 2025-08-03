from django.db import models


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
    champion = models.ForeignKey('Champion', on_delete=models.SET_NULL, null=True, related_name='participants')
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
    item0 = models.ForeignKey('Item', null=True, blank=True, on_delete=models.SET_NULL, related_name='used_as_item0')
    item1 = models.ForeignKey('Item', null=True, blank=True, on_delete=models.SET_NULL, related_name='used_as_item1')
    item2 = models.ForeignKey('Item', null=True, blank=True, on_delete=models.SET_NULL, related_name='used_as_item2')
    item3 = models.ForeignKey('Item', null=True, blank=True, on_delete=models.SET_NULL, related_name='used_as_item3')
    item4 = models.ForeignKey('Item', null=True, blank=True, on_delete=models.SET_NULL, related_name='used_as_item4')
    item5 = models.ForeignKey('Item', null=True, blank=True, on_delete=models.SET_NULL, related_name='used_as_item5')
    item6 = models.ForeignKey('Item', null=True, blank=True, on_delete=models.SET_NULL, related_name='used_as_item6')
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



class Champion(models.Model):
    # Identifiants
    champion_id = models.CharField(max_length=50, unique=True)  # "Urgot"
    key = models.CharField(max_length=10)  # "6"
    name = models.CharField(max_length=100)  # "Urgot"
    title = models.CharField(max_length=200)  # "the Dreadnought"
    
    # Image principale
    image_full = models.CharField(max_length=100)  # "Urgot.png"
    image_sprite = models.CharField(max_length=100)  # "champion4.png"
    image_group = models.CharField(max_length=50)  # "champion"
    image_x = models.IntegerField()
    image_y = models.IntegerField()
    image_w = models.IntegerField()
    image_h = models.IntegerField()
    
    # Lore et description
    lore = models.TextField()
    blurb = models.TextField()
    
    # Conseils (stockés en JSON pour simplicité)
    ally_tips = models.JSONField(default=list)
    enemy_tips = models.JSONField(default=list)
    
    # Tags et type
    tags = models.JSONField(default=list)  # ["Fighter", "Tank"]
    partype = models.CharField(max_length=50)  # "Mana"
    
    # Métadonnées de version
    version = models.CharField(max_length=20, default="15.15.1")
    data_format = models.CharField(max_length=50, default="standAloneComplex")
    data_type = models.CharField(max_length=50, default="champion")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.title}"
    
    class Meta:
        db_table = 'champions'


class ChampionInfo(models.Model):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='info')
    attack = models.IntegerField()
    defense = models.IntegerField()
    magic = models.IntegerField()
    difficulty = models.IntegerField()
    
    def __str__(self):
        return f"Info for {self.champion.name}"
    
    class Meta:
        db_table = 'champion_info'


class ChampionStats(models.Model):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='stats')
    
    # Stats de base
    hp = models.FloatField()
    hp_per_level = models.FloatField()
    mp = models.FloatField()
    mp_per_level = models.FloatField()
    move_speed = models.FloatField()
    armor = models.FloatField()
    armor_per_level = models.FloatField()
    spell_block = models.FloatField()
    spell_block_per_level = models.FloatField()
    attack_range = models.FloatField()
    hp_regen = models.FloatField()
    hp_regen_per_level = models.FloatField()
    mp_regen = models.FloatField()
    mp_regen_per_level = models.FloatField()
    crit = models.FloatField()
    crit_per_level = models.FloatField()
    attack_damage = models.FloatField()
    attack_damage_per_level = models.FloatField()
    attack_speed_per_level = models.FloatField()
    attack_speed = models.FloatField()
    
    def __str__(self):
        return f"Stats for {self.champion.name}"
    
    class Meta:
        db_table = 'champion_stats'


class ChampionSkin(models.Model):
    champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name='skins')
    skin_id = models.CharField(max_length=20)  # "6000"
    num = models.IntegerField()  # 0
    name = models.CharField(max_length=100)  # "default"
    chromas = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.champion.name} - {self.name}"
    
    class Meta:
        db_table = 'champion_skins'
        unique_together = ('champion', 'num')


class ChampionSpell(models.Model):
    champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name='spells')
    spell_id = models.CharField(max_length=50)  # "UrgotQ"
    name = models.CharField(max_length=100)  # "Corrosive Charge"
    description = models.TextField()
    tooltip = models.TextField()
    max_rank = models.IntegerField()
    
    # Cooldowns (stockés en JSON car c'est un array)
    cooldown = models.JSONField(default=list)  # [10, 9.5, 9, 8.5, 8]
    cooldown_burn = models.CharField(max_length=100)  # "10/9.5/9/8.5/8"
    
    # Coûts
    cost = models.JSONField(default=list)  # [70, 70, 70, 70, 70]
    cost_burn = models.CharField(max_length=100)  # "70"
    cost_type = models.CharField(max_length=100)  # " {{ abilityresourcename }}"
    
    # Range
    spell_range = models.JSONField(default=list)  # [800, 800, 800, 800, 800]
    range_burn = models.CharField(max_length=100)  # "800"
    
    # Effects (array complexe)
    effect = models.JSONField(default=list)
    effect_burn = models.JSONField(default=list)
    vars = models.JSONField(default=list)
    
    # Image
    image_full = models.CharField(max_length=100)
    image_sprite = models.CharField(max_length=100)
    image_group = models.CharField(max_length=50)
    image_x = models.IntegerField()
    image_y = models.IntegerField()
    image_w = models.IntegerField()
    image_h = models.IntegerField()
    
    # Autres
    max_ammo = models.CharField(max_length=10, default="-1")
    resource = models.CharField(max_length=100)
    data_values = models.JSONField(default=dict)
    
    # Ordre des sorts
    order = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.champion.name} - {self.name}"
    
    class Meta:
        db_table = 'champion_spells'
        ordering = ['order']


class ChampionSpellLevelTip(models.Model):
    spell = models.OneToOneField(ChampionSpell, on_delete=models.CASCADE, related_name='level_tip')
    label = models.JSONField(default=list)  # ["Cooldown", "Damage", "Slow"]
    effect = models.JSONField(default=list)  # ["{{ cooldown }} -> {{ cooldownNL }}", ...]
    
    def __str__(self):
        return f"LevelTip for {self.spell.name}"
    
    class Meta:
        db_table = 'champion_spell_level_tips'


class ChampionPassive(models.Model):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='passive')
    name = models.CharField(max_length=100)  # "Echoing Flames"
    description = models.TextField()
    
    # Image
    image_full = models.CharField(max_length=100)
    image_sprite = models.CharField(max_length=100)
    image_group = models.CharField(max_length=50)
    image_x = models.IntegerField()
    image_y = models.IntegerField()
    image_w = models.IntegerField()
    image_h = models.IntegerField()
    
    def __str__(self):
        return f"{self.champion.name} - {self.name}"
    
    class Meta:
        db_table = 'champion_passives'


# Modèle pour stocker les recommandations (bien que vide dans l'exemple)
class ChampionRecommendation(models.Model):
    champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name='recommendations')
    recommendation_data = models.JSONField(default=dict)
    
    def __str__(self):
        return f"Recommendations for {self.champion.name}"
    
    class Meta:
        db_table = 'champion_recommendations'


# À ajouter dans votre models.py


class Item(models.Model):
    item_id = models.CharField(max_length=20, unique=True)  # "1001"
    name = models.CharField(max_length=100)  # "Boots of Speed"
    description = models.TextField()
    colloq = models.CharField(max_length=200, blank=True)  # "boots;brown"
    plaintext = models.TextField(blank=True)  # "Slightly increases Movement Speed"
    
    # Or (coût)
    gold_base = models.IntegerField(default=0)
    gold_purchasable = models.BooleanField(default=True)
    gold_total = models.IntegerField(default=0)
    gold_sell = models.IntegerField(default=0)
    
    # Image
    image_full = models.CharField(max_length=100)
    image_sprite = models.CharField(max_length=100)
    image_group = models.CharField(max_length=50)
    image_x = models.IntegerField()
    image_y = models.IntegerField()
    image_w = models.IntegerField()
    image_h = models.IntegerField()
    
    # Propriétés de l'objet
    tags = models.JSONField(default=list)  # ["Boots"]
    maps = models.JSONField(default=dict)  # {"11": true, "12": true}
    stats = models.JSONField(default=dict)  # {"FlatMovementSpeedMod": 25}
    
    # Métadonnées
    version = models.CharField(max_length=20, default="15.15.1")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'items'


class ItemFrom(models.Model):
    """Objets requis pour créer cet objet"""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='from_items')
    from_item_id = models.CharField(max_length=20)
    
    class Meta:
        db_table = 'item_from'
        unique_together = ('item', 'from_item_id')


class ItemInto(models.Model):
    """Objets qui peuvent être créés avec cet objet"""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='into_items')
    into_item_id = models.CharField(max_length=20)
    
    class Meta:
        db_table = 'item_into'
        unique_together = ('item', 'into_item_id')


class Ban(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team_id = models.IntegerField()
    pick_turn = models.IntegerField()
    champion_id = models.ForeignKey(Champion, on_delete=models.SET_NULL, null=True, related_name='bans')

    class Meta:
        unique_together = ('match', 'team_id', 'pick_turn')

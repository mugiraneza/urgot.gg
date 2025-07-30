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





class DamageType(models.TextChoices):
    PHYSICAL_DAMAGE = "PHYSICAL_DAMAGE", "Physical Damage"
    MAGIC_DAMAGE = "MAGIC_DAMAGE", "Magic Damage"
    TRUE_DAMAGE = "TRUE_DAMAGE", "True Damage"
    PURE_DAMAGE = "PURE_DAMAGE", "Pure Damage"
    MIXED_DAMAGE = "MIXED_DAMAGE", "Mixed Damage"
    OTHER_DAMAGE = "OTHER_DAMAGE", "Other Damage"


class Resource(models.TextChoices):
    NO_COST = "NO_COST", "No Cost"
    MANA = "MANA", "Mana"
    ENERGY = "ENERGY", "Energy"
    RAGE = "RAGE", "Rage"
    FURY = "FURY", "Fury"
    FEROCITY = "FEROCITY", "Ferocity"
    HEALTH = "HEALTH", "Health"
    MAXIMUM_HEALTH = "MAXIMUM_HEALTH", "Maximum Health"
    CURRENT_HEALTH = "CURRENT_HEALTH", "Current Health"
    HEALTH_PER_SECOND = "HEALTH_PER_SECOND", "Health Per Second"
    MANA_PER_SECOND = "MANA_PER_SECOND", "Mana Per Second"
    CHARGE = "CHARGE", "Charge"
    COURAGE = "COURAGE", "Courage"
    HEAT = "HEAT", "Heat"
    GRIT = "GRIT", "Grit"
    FLOW = "FLOW", "Flow"
    SHIELD = "SHIELD", "Shield"
    OTHER = "OTHER", "Other"
    NONE = "NONE", "None"
    SOUL_UNBOUND = "SOUL_UNBOUND", "Soul Unbound"
    BLOOD_WELL = "BLOOD_WELL", "Blood Well"
    CRIMSON_RUSH = "CRIMSON_RUSH", "Crimson Rush"
    FRENZY = "FRENZY", "Frenzy"


class AttackType(models.TextChoices):
    MELEE = "MELEE", "Melee"
    RANGED = "RANGED", "Ranged"


class Position(models.TextChoices):
    TOP = "TOP", "Top"
    JUNGLE = "JUNGLE", "Jungle"
    MIDDLE = "MIDDLE", "Middle"
    BOTTOM = "BOTTOM", "Bottom"
    SUPPORT = "SUPPORT", "Support"


class Role(models.TextChoices):
    TANK = "TANK", "Tank"
    FIGHTER = "FIGHTER", "Fighter"
    MAGE = "MAGE", "Mage"
    MARKSMAN = "MARKSMAN", "Marksman"
    SUPPORT = "SUPPORT", "Support"
    WARDEN = "WARDEN", "Warden"
    VANGUARD = "VANGUARD", "Vanguard"
    JUGGERNAUT = "JUGGERNAUT", "Juggernaut"
    CONTROLLER = "CONTROLLER", "Controller"
    SKIRMISHER = "SKIRMISHER", "Skirmisher"
    DIVER = "DIVER", "Diver"
    SLAYER = "SLAYER", "Slayer"
    BURST = "BURST", "Burst"
    BATTLEMAGE = "BATTLEMAGE", "Battlemage"
    ENCHANTER = "ENCHANTER", "Enchanter"
    CATCHER = "CATCHER", "Catcher"
    ASSASSIN = "ASSASSIN", "Assassin"
    SPECIALIST = "SPECIALIST", "Specialist"
    ARTILLERY = "ARTILLERY", "Artillery"


class ItemAttributes(models.TextChoices):
    TANK = "TANK", "Tank"
    SUPPORT = "SUPPORT", "Support"
    MAGE = "MAGE", "Mage"
    MOVEMENT = "MOVEMENT", "Movement"
    ATTACK_SPEED = "ATTACK_SPEED", "Attack Speed"
    ONHIT_EFFECTS = "ONHIT_EFFECTS", "On-Hit Effects"
    FIGHTER = "FIGHTER", "Fighter"
    MARKSMAN = "MARKSMAN", "Marksman"
    ASSASSIN = "ASSASSIN", "Assassin"
    ARMOR_PEN = "ARMOR_PEN", "Armor Penetration"
    MANA_AND_REG = "MANA_AND_REG", "Mana and Regeneration"
    HEALTH_AND_REG = "HEALTH_AND_REG", "Health and Regeneration"
    LIFESTEAL_VAMP = "LIFESTEAL_VAMP", "Lifesteal and Vamp"
    MAGIC_PEN = "MAGIC_PEN", "Magic Penetration"
    ABILITY_POWER = "ABILITY_POWER", "Ability Power"
    ATTACK_DAMAGE = "ATTACK_DAMAGE", "Attack Damage"
    CRITICAL_STRIKE = "CRITICAL_STRIKE", "Critical Strike"
    ABILITY_HASTE = "ABILITY_HASTE", "Ability Haste"


class ItemRanks(models.TextChoices):
    MYTHIC = "MYTHIC", "Mythic"
    LEGENDARY = "LEGENDARY", "Legendary"
    EPIC = "EPIC", "Epic"
    BASIC = "BASIC", "Basic"
    STARTER = "STARTER", "Starter"
    CONSUMABLE = "CONSUMABLE", "Consumable"
    POTION = "POTION", "Potion"
    BOOTS = "BOOTS", "Boots"
    TRINKET = "TRINKET", "Trinket"
    DISTRIBUTED = "DISTRIBUTED", "Distributed"
    MINION = "MINION", "Minion"
    TURRET = "TURRET", "Turret"
    SPECIAL = "SPECIAL", "Special"


# Base Stat Model
class BaseStat(models.Model):
    flat = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    percent = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    per_level = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    percent_per_level = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    percent_base = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    percent_bonus = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)

    class Meta:
        abstract = True

    @staticmethod
    def _grow_stat(base, per_level, level):
        """Grow a base stat based on the level of the champion."""
        return base + per_level * (level - 1) * (Decimal('0.7025') + Decimal('0.0175') * (level - 1))

    def total(self, level: int):
        """Calculate the total stat value given all its attributes."""
        base = self._grow_stat(self.flat, self.per_level, level)
        total = ((base * (1 + self.percent_base)) + self.flat + (self.per_level * level)) * (
            1 + self.percent + (self.percent_per_level * level)
        )
        bonus = total - base
        total += self.percent_bonus * bonus
        return total


# Champion Models
class Champion(models.Model):
    id = models.IntegerField(primary_key=True)
    key = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    full_name = models.CharField(max_length=200)
    icon = models.URLField()
    resource = models.CharField(max_length=20, choices=Resource.choices)
    attack_type = models.CharField(max_length=10, choices=AttackType.choices)
    adaptive_type = models.CharField(max_length=20, choices=DamageType.choices)
    release_date = models.CharField(max_length=50)
    release_patch = models.CharField(max_length=20)
    patch_last_changed = models.CharField(max_length=20)
    lore = models.TextField()
    faction = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} - {self.title}"


class ChampionPosition(models.Model):
    champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name='champion_positions')
    position = models.CharField(max_length=10, choices=Position.choices)

    class Meta:
        unique_together = ['champion', 'position']


class ChampionRole(models.Model):
    champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name='champion_roles')
    role = models.CharField(max_length=15, choices=Role.choices)

    class Meta:
        unique_together = ['champion', 'role']


class ChampionPrice(models.Model):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='price')
    blue_essence = models.IntegerField()
    rp = models.IntegerField()
    sale_rp = models.IntegerField()


class ChampionAttributeRatings(models.Model):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='attribute_ratings')
    damage = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    toughness = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    control = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    mobility = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    utility = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    ability_reliance = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    difficulty = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])


# Champion Stats Models
class ChampionHealth(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='health')


class ChampionHealthRegen(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='health_regen')


class ChampionMana(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='mana')


class ChampionManaRegen(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='mana_regen')


class ChampionArmor(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='armor')


class ChampionMagicResistance(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='magic_resistance')


class ChampionAttackDamage(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='attack_damage')


class ChampionMovespeed(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='movespeed')


class ChampionAttackSpeed(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='attack_speed')


class ChampionAttackRange(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='attack_range')


class ChampionAcquisitionRadius(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='acquisition_radius')


class ChampionSelectionRadius(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='selection_radius')


class ChampionPathingRadius(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='pathing_radius')


class ChampionGameplayRadius(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='gameplay_radius')


class ChampionCriticalStrikeDamage(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='critical_strike_damage')


class ChampionCriticalStrikeDamageModifier(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='critical_strike_damage_modifier')


class ChampionAttackSpeedRatio(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='attack_speed_ratio')


class ChampionAttackCastTime(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='attack_cast_time')


class ChampionAttackTotalTime(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='attack_total_time')


class ChampionAttackDelayOffset(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='attack_delay_offset')


# ARAM Stats
class ChampionAramDamageTaken(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='aram_damage_taken')


class ChampionAramDamageDealt(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='aram_damage_dealt')


class ChampionAramHealing(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='aram_healing')


class ChampionAramShielding(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='aram_shielding')


class ChampionAramTenacity(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='aram_tenacity')


class ChampionAramAbilityHaste(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='aram_ability_haste')


class ChampionAramAttackSpeed(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='aram_attack_speed')


class ChampionAramEnergyRegen(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='aram_energy_regen')


# URF Stats
class ChampionUrfDamageTaken(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='urf_damage_taken')


class ChampionUrfDamageDealt(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='urf_damage_dealt')


class ChampionUrfHealing(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='urf_healing')


class ChampionUrfShielding(BaseStat):
    champion = models.OneToOneField(Champion, on_delete=models.CASCADE, related_name='urf_shielding')


# Ability Models
class Ability(models.Model):
    champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name='abilities')
    ability_key = models.CharField(default='P',max_length=10)  # P, Q, W, E, R
    name = models.CharField(max_length=100)
    icon = models.URLField()
    targeting = models.CharField(max_length=200, blank=True)
    affects = models.CharField(max_length=200, blank=True)
    spellshieldable = models.CharField(max_length=200, blank=True)
    resource = models.CharField(max_length=20, choices=Resource.choices)
    damage_type = models.CharField(max_length=20, choices=DamageType.choices)
    spell_effects = models.CharField(max_length=200, blank=True)
    projectile = models.CharField(max_length=200, blank=True)
    on_hit_effects = models.CharField(max_length=200, blank=True)
    occurrence = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    blurb = models.TextField(blank=True)
    missile_speed = models.CharField(max_length=100, blank=True)
    recharge_rate = models.CharField(max_length=100, blank=True)
    collision_radius = models.CharField(max_length=100, blank=True)
    tether_radius = models.CharField(max_length=100, blank=True)
    on_target_cd_static = models.CharField(max_length=100, blank=True)
    inner_radius = models.CharField(max_length=100, blank=True)
    speed = models.CharField(max_length=100, blank=True)
    width = models.CharField(max_length=100, blank=True)
    angle = models.CharField(max_length=100, blank=True)
    cast_time = models.CharField(max_length=100, blank=True)
    effect_radius = models.CharField(max_length=100, blank=True)
    target_range = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ['champion', 'ability_key']


class AbilityCooldown(models.Model):
    ability = models.OneToOneField(Ability, on_delete=models.CASCADE, related_name='cooldown')
    affected_by_cdr = models.BooleanField(default=True)


class AbilityCost(models.Model):
    ability = models.OneToOneField(Ability, on_delete=models.CASCADE, related_name='cost')


class AbilityEffect(models.Model):
    ability = models.ForeignKey(Ability, on_delete=models.CASCADE, related_name='effects')
    description = models.TextField()


class Modifier(models.Model):
    cooldown = models.ForeignKey(AbilityCooldown, on_delete=models.CASCADE, related_name='modifiers', null=True, blank=True)
    cost = models.ForeignKey(AbilityCost, on_delete=models.CASCADE, related_name='modifiers', null=True, blank=True)
    leveling = models.ForeignKey('Leveling', on_delete=models.CASCADE, related_name='modifiers', null=True, blank=True)


class ModifierValue(models.Model):
    modifier = models.ForeignKey(Modifier, on_delete=models.CASCADE, related_name='values')
    value = models.DecimalField(max_digits=10, decimal_places=4)
    unit = models.CharField(max_length=50)


class Leveling(models.Model):
    effect = models.ForeignKey(AbilityEffect, on_delete=models.CASCADE, related_name='levelings')
    attribute = models.CharField(max_length=100)


# Skin Models
class Skin(models.Model):
    champion = models.ForeignKey(Champion, on_delete=models.CASCADE, related_name='skins')
    skin_id = models.IntegerField()
    name = models.CharField(max_length=100)
    is_base = models.BooleanField(default=False)
    availability = models.CharField(max_length=100)
    format_name = models.CharField(max_length=100)
    loot_eligible = models.BooleanField(default=True)
    cost = models.CharField(max_length=50)
    sale = models.IntegerField(default=0)
    distribution = models.CharField(max_length=100)
    rarity = models.CharField(max_length=50)
    lore = models.TextField(blank=True)
    release = models.FloatField()
    splash_path = models.URLField()
    uncentered_splash_path = models.URLField()
    tile_path = models.URLField()
    load_screen_path = models.URLField()
    load_screen_vintage_path = models.URLField()
    new_effects = models.BooleanField(default=False)
    new_animations = models.BooleanField(default=False)
    new_recall = models.BooleanField(default=False)
    new_voice = models.BooleanField(default=False)
    new_quotes = models.BooleanField(default=False)

    class Meta:
        unique_together = ['champion', 'skin_id']


class SkinSet(models.Model):
    skin = models.ForeignKey(Skin, on_delete=models.CASCADE, related_name='sets')
    set_name = models.CharField(max_length=100)


class SkinVoiceActor(models.Model):
    skin = models.ForeignKey(Skin, on_delete=models.CASCADE, related_name='voice_actors')
    voice_actor = models.CharField(max_length=100)


class SkinSplashArtist(models.Model):
    skin = models.ForeignKey(Skin, on_delete=models.CASCADE, related_name='splash_artists')
    artist = models.CharField(max_length=100)


class Chroma(models.Model):
    skin = models.ForeignKey(Skin, on_delete=models.CASCADE, related_name='chromas')
    chroma_id = models.IntegerField()
    name = models.CharField(max_length=100)
    chroma_path = models.URLField()

    class Meta:
        unique_together = ['skin', 'chroma_id']


class ChromaColor(models.Model):
    chroma = models.ForeignKey(Chroma, on_delete=models.CASCADE, related_name='colors')
    color = models.CharField(max_length=50)


class ChromaDescription(models.Model):
    chroma = models.ForeignKey(Chroma, on_delete=models.CASCADE, related_name='descriptions')
    description = models.TextField()
    region = models.CharField(max_length=10)


class ChromaRarity(models.Model):
    chroma = models.ForeignKey(Chroma, on_delete=models.CASCADE, related_name='rarities')
    rarity = models.IntegerField()
    region = models.CharField(max_length=10)


# Item Models
class Item(models.Model):
    item_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    tier = models.IntegerField()
    special_recipe = models.IntegerField(default=0)
    no_effects = models.BooleanField(default=False)
    removed = models.BooleanField(default=False)
    required_champion = models.CharField(max_length=50, blank=True)
    required_ally = models.CharField(max_length=50, blank=True)
    icon = models.URLField()
    simple_description = models.TextField()
    icon_overlay = models.URLField(blank=True)

    def __str__(self):
        return self.name


class ItemRank(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='ranks')
    rank = models.CharField(max_length=15, choices=ItemRanks.choices)

    class Meta:
        unique_together = ['item', 'rank']


class ItemBuildsFrom(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='builds_from_relations')
    component = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='builds_into_relations')

    class Meta:
        unique_together = ['item', 'component']


class ItemNickname(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='nicknames')
    nickname = models.CharField(max_length=100)


class ItemPrices(models.Model):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='prices')
    total = models.IntegerField()
    combined = models.IntegerField()
    sell = models.IntegerField()


class ItemShop(models.Model):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='shop')
    purchasable = models.BooleanField(default=True)


class ItemShopTag(models.Model):
    shop = models.ForeignKey(ItemShop, on_delete=models.CASCADE, related_name='tags')
    tag = models.CharField(max_length=50)


# Item Stats Models
class ItemHealth(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='health')


class ItemHealthRegen(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='health_regen')


class ItemMana(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='mana')


class ItemManaRegen(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='mana_regen')


class ItemArmor(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='armor')


class ItemMagicResistance(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='magic_resistance')


class ItemAttackDamage(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='attack_damage')


class ItemAbilityPower(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='ability_power')


class ItemMovespeed(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='movespeed')


class ItemCriticalStrikeChance(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='critical_strike_chance')


class ItemAttackSpeed(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='attack_speed')


class ItemLethality(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='lethality')


class ItemCooldownReduction(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='cooldown_reduction')


class ItemGoldPer10(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='gold_per_10')


class ItemHealAndShieldPower(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='heal_and_shield_power')


class ItemLifesteal(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='lifesteal')


class ItemMagicPenetration(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='magic_penetration')


class ItemArmorPenetration(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='armor_penetration')


class ItemAbilityHaste(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='ability_haste')


class ItemOmniVamp(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='omnivamp')


class ItemTenacity(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='tenacity')


class ItemCriticalStrikeDamage(BaseStat):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='critical_strike_damage')


# Item Passive and Active Effects
class ItemPassive(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='passives')
    unique = models.BooleanField(default=False)
    mythic = models.BooleanField(default=False)
    name = models.CharField(max_length=100)
    effects = models.TextField()
    range = models.IntegerField(default=0)
    cooldown = models.CharField(max_length=50, blank=True)


class ItemActive(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='actives')
    unique = models.BooleanField(default=False)
    name = models.CharField(max_length=100)
    effects = models.TextField()
    range = models.IntegerField(default=0)
    cooldown = models.FloatField(default=0.0)


# Passive Stats Models for Items
class ItemPassiveHealth(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='health')


class ItemPassiveHealthRegen(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='health_regen')


class ItemPassiveMana(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='mana')


class ItemPassiveManaRegen(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='mana_regen')


class ItemPassiveArmor(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='armor')


class ItemPassiveMagicResistance(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='magic_resistance')


class ItemPassiveAttackDamage(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='attack_damage')


class ItemPassiveAbilityPower(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='ability_power')


class ItemPassiveMovespeed(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='movespeed')


class ItemPassiveCriticalStrikeChance(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='critical_strike_chance')


class ItemPassiveAttackSpeed(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='attack_speed')


class ItemPassiveLethality(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='lethality')


class ItemPassiveCooldownReduction(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='cooldown_reduction')


class ItemPassiveGoldPer10(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='gold_per_10')


class ItemPassiveHealAndShieldPower(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='heal_and_shield_power')


class ItemPassiveLifesteal(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='lifesteal')


class ItemPassiveMagicPenetration(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='magic_penetration')


class ItemPassiveArmorPenetration(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='armor_penetration')


class ItemPassiveAbilityHaste(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='ability_haste')


class ItemPassiveOmniVamp(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='omnivamp')


class ItemPassiveTenacity(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='tenacity')


class ItemPassiveCriticalStrikeDamage(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='critical_strike_damage')


class ItemPassiveAttackRange(BaseStat):
    passive = models.OneToOneField(ItemPassive, on_delete=models.CASCADE, related_name='attack_range')


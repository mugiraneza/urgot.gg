from rest_framework import serializers
from .models import *

class MatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = '__all__'


class ParticipantSerializer(serializers.ModelSerializer):
    match_id = serializers.SlugRelatedField(slug_field='match_id', read_only=True)

    class Meta:
        model = Participant
        fields = '__all__'
        extra_kwargs = {
            'win': {'required': False},
            'first_blood_kill': {'required': False},
            'first_tower_kill': {'required': False},
        }


class TeamSerializer(serializers.ModelSerializer):
    match_id = serializers.SlugRelatedField(slug_field='match_id', read_only=True)

    class Meta:
        model = Team
        fields = '__all__'
        extra_kwargs = {
            'win': {'required': False},
        }


class BanSerializer(serializers.ModelSerializer):
    match_id = serializers.SlugRelatedField(slug_field='match_id', read_only=True)

    class Meta:
        model = Ban
        fields = '__all__'


class ObjectiveSerializer(serializers.ModelSerializer):
    match_id = serializers.SlugRelatedField(slug_field='match_id', read_only=True)

    class Meta:
        model = Objective
        fields = '__all__'


class DeathSerializer(serializers.ModelSerializer):
    match_id = serializers.SlugRelatedField(slug_field='match_id', read_only=True)

    class Meta:
        model = Death
        fields = '__all__'






class ChampionPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChampionPosition
        fields = ['position']


class ChampionRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChampionRole
        fields = ['role']


class ChampionPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChampionPrice
        fields = ['blue_essence', 'rp', 'sale_rp']


class ChampionAttributeRatingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChampionAttributeRatings
        fields = ['damage', 'toughness', 'control', 'mobility', 'utility', 'ability_reliance', 'difficulty']


class BaseStatSerializer(serializers.ModelSerializer):
    total_at_level_1 = serializers.SerializerMethodField()
    total_at_level_18 = serializers.SerializerMethodField()
    
    class Meta:
        fields = ['flat', 'percent', 'per_level', 'percent_per_level', 'percent_base', 'percent_bonus', 
                 'total_at_level_1', 'total_at_level_18']
    
    def get_total_at_level_1(self, obj):
        return float(obj.total(1))
    
    def get_total_at_level_18(self, obj):
        return float(obj.total(18))


class ChampionHealthSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionHealth


class ChampionHealthRegenSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionHealthRegen


class ChampionManaSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionMana


class ChampionManaRegenSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionManaRegen


class ChampionArmorSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionArmor


class ChampionMagicResistanceSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionMagicResistance


class ChampionAttackDamageSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionAttackDamage


class ChampionMovespeedSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionMovespeed


class ChampionAttackSpeedSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionAttackSpeed


class ChampionAttackRangeSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ChampionAttackRange


class AbilityEffectSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbilityEffect
        fields = ['description']


class ModifierValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModifierValue
        fields = ['value', 'unit']


class ModifierSerializer(serializers.ModelSerializer):
    values = ModifierValueSerializer(many=True, read_only=True)
    
    class Meta:
        model = Modifier
        fields = ['values']


class AbilityCooldownSerializer(serializers.ModelSerializer):
    modifiers = ModifierSerializer(many=True, read_only=True)
    
    class Meta:
        model = AbilityCooldown
        fields = ['affected_by_cdr', 'modifiers']


class AbilityCostSerializer(serializers.ModelSerializer):
    modifiers = ModifierSerializer(many=True, read_only=True)
    
    class Meta:
        model = AbilityCost
        fields = ['modifiers']


class LevelingSerializer(serializers.ModelSerializer):
    modifiers = ModifierSerializer(many=True, read_only=True)
    
    class Meta:
        model = Leveling
        fields = ['attribute', 'modifiers']


class AbilitySerializer(serializers.ModelSerializer):
    effects = AbilityEffectSerializer(many=True, read_only=True)
    cooldown = AbilityCooldownSerializer(read_only=True)
    cost = AbilityCostSerializer(read_only=True)
    
    class Meta:
        model = Ability
        fields = ['ability_key', 'name', 'icon', 'targeting', 'affects', 'spellshieldable', 
                 'resource', 'damage_type', 'spell_effects', 'projectile', 'on_hit_effects',
                 'occurrence', 'notes', 'blurb', 'missile_speed', 'recharge_rate',
                 'collision_radius', 'tether_radius', 'on_target_cd_static', 'inner_radius',
                 'speed', 'width', 'angle', 'cast_time', 'effect_radius', 'target_range',
                 'effects', 'cooldown', 'cost']


class SkinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skin
        fields = ['skin_id', 'name', 'is_base', 'availability', 'format_name', 'loot_eligible',
                 'cost', 'sale', 'distribution', 'rarity', 'lore', 'release', 'splash_path',
                 'uncentered_splash_path', 'tile_path', 'load_screen_path', 'load_screen_vintage_path',
                 'new_effects', 'new_animations', 'new_recall', 'new_voice', 'new_quotes']


class ChampionSerializer(serializers.ModelSerializer):
    positions = serializers.StringRelatedField(source='champion_positions', many=True, read_only=True)
    roles = serializers.StringRelatedField(source='champion_roles', many=True, read_only=True)
    price = ChampionPriceSerializer(read_only=True)
    attribute_ratings = ChampionAttributeRatingsSerializer(read_only=True)
    abilities = AbilitySerializer(many=True, read_only=True)
    skins = SkinSerializer(many=True, read_only=True)
    
    # Stats
    health = ChampionHealthSerializer(read_only=True)
    health_regen = ChampionHealthRegenSerializer(read_only=True)
    mana = ChampionManaSerializer(read_only=True)
    mana_regen = ChampionManaRegenSerializer(read_only=True)
    armor = ChampionArmorSerializer(read_only=True)
    magic_resistance = ChampionMagicResistanceSerializer(read_only=True)
    attack_damage = ChampionAttackDamageSerializer(read_only=True)
    movespeed = ChampionMovespeedSerializer(read_only=True)
    attack_speed = ChampionAttackSpeedSerializer(read_only=True)
    attack_range = ChampionAttackRangeSerializer(read_only=True)
    
    class Meta:
        model = Champion
        fields = ['id', 'key', 'name', 'title', 'full_name', 'icon', 'resource', 'attack_type',
                 'adaptive_type', 'release_date', 'release_patch', 'patch_last_changed', 'lore',
                 'faction', 'positions', 'roles', 'price', 'attribute_ratings', 'abilities', 'skins',
                 'health', 'health_regen', 'mana', 'mana_regen', 'armor', 'magic_resistance',
                 'attack_damage', 'movespeed', 'attack_speed', 'attack_range']


class ItemRankSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemRank
        fields = ['rank']


class ItemNicknameSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemNickname
        fields = ['nickname']


class ItemPricesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPrices
        fields = ['total', 'combined', 'sell']


class ItemShopTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemShopTag
        fields = ['tag']


class ItemShopSerializer(serializers.ModelSerializer):
    tags = ItemShopTagSerializer(many=True, read_only=True)
    
    class Meta:
        model = ItemShop
        fields = ['purchasable', 'tags']


class ItemPassiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPassive
        fields = ['unique', 'mythic', 'name', 'effects', 'range', 'cooldown']


class ItemActiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemActive
        fields = ['unique', 'name', 'effects', 'range', 'cooldown']


class ItemHealthSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ItemHealth


class ItemManaSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ItemMana


class ItemArmorSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ItemArmor


class ItemMagicResistanceSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ItemMagicResistance


class ItemAttackDamageSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ItemAttackDamage


class ItemAbilityPowerSerializer(BaseStatSerializer):
    class Meta(BaseStatSerializer.Meta):
        model = ItemAbilityPower


class ItemSerializer(serializers.ModelSerializer):
    ranks = ItemRankSerializer(many=True, read_only=True)
    nicknames = ItemNicknameSerializer(many=True, read_only=True)
    prices = ItemPricesSerializer(read_only=True)
    shop = ItemShopSerializer(read_only=True)
    passives = ItemPassiveSerializer(many=True, read_only=True)
    actives = ItemActiveSerializer(many=True, read_only=True)
    builds_from = serializers.SerializerMethodField()
    builds_into = serializers.SerializerMethodField()
    
    # Stats
    health = ItemHealthSerializer(read_only=True)
    mana = ItemManaSerializer(read_only=True)
    armor = ItemArmorSerializer(read_only=True)
    magic_resistance = ItemMagicResistanceSerializer(read_only=True)
    attack_damage = ItemAttackDamageSerializer(read_only=True)
    ability_power = ItemAbilityPowerSerializer(read_only=True)
    
    class Meta:
        model = Item
        fields = ['item_id', 'name', 'tier', 'special_recipe', 'no_effects', 'removed',
                 'required_champion', 'required_ally', 'icon', 'simple_description', 'icon_overlay',
                 'ranks', 'nicknames', 'prices', 'shop', 'passives', 'actives', 'builds_from',
                 'builds_into', 'health', 'mana', 'armor', 'magic_resistance', 'attack_damage',
                 'ability_power']
    
    def get_builds_from(self, obj):
        return [relation.component.item_id for relation in obj.builds_from_relations.all()]
    
    def get_builds_into(self, obj):
        return [relation.item.item_id for relation in obj.builds_into_relations.all()]

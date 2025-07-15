from rest_framework import serializers
from .models import Match, Participant, Team, Ban, Objective, Death

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

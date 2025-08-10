from django.db import migrations
from django.db.models import F, Value, CharField, Case, When
from django.db.models.functions import Substr, StrIndex

def forwards(apps, schema_editor):
    Match = apps.get_model('api', 'Match')
    expr = Case(
        When(
            match_id__contains='_',
            then=Substr(F('match_id'), 1, StrIndex(F('match_id'), Value('_')) - 1),
        ),
        default=None,
        output_field=CharField(max_length=10),
    )
    Match.objects.update(game_region=expr)


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0006_match_game_region'),  # adapte le nom
    ]
    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

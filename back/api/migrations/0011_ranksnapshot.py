from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_participant_bait_pings_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RankSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("puuid", models.CharField(db_index=True, max_length=100)),
                ("riot_name", models.CharField(db_index=True, max_length=100)),
                ("queue_type", models.CharField(blank=True, default="", max_length=50)),
                ("tier", models.CharField(blank=True, default="", max_length=20)),
                ("rank_division", models.CharField(blank=True, default="", max_length=10)),
                ("league_points", models.IntegerField(blank=True, null=True)),
                ("wins", models.IntegerField(blank=True, null=True)),
                ("losses", models.IntegerField(blank=True, null=True)),
                ("captured_at", models.DateTimeField(auto_now_add=True)),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rank_snapshots", to="api.match")),
            ],
            options={
                "unique_together": {("match", "puuid", "queue_type")},
            },
        ),
    ]

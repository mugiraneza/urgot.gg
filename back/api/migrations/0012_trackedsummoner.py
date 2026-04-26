from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0011_ranksnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrackedSummoner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("riot_name", models.CharField(max_length=100)),
                ("region", models.CharField(default="europe", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("last_import_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_import_finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_import_status", models.CharField(blank=True, default="", max_length=20)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["riot_name", "region"],
                "unique_together": {("riot_name", "region")},
            },
        ),
    ]

from collections import defaultdict, deque
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections, transaction
from django.db.models import AutoField, BigAutoField, ForeignKey, OneToOneField, SmallAutoField


DEFAULT_BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Reprend les donnees applicatives depuis SQLite vers la base par defaut, par lots."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="sqlite_import",
            help="Alias de base source Django. Par defaut: sqlite_import.",
        )
        parser.add_argument(
            "--target",
            default="default",
            help="Alias de base cible Django. Par defaut: default.",
        )
        parser.add_argument(
            "--sqlite-path",
            help="Chemin du fichier SQLite source. Ecrase SQLITE_IMPORT_PATH pour cette execution.",
        )
        parser.add_argument(
            "--app",
            action="append",
            dest="apps",
            help="Application a reprendre. Peut etre repete. Par defaut: api.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Taille des lots d'import. Par defaut: {DEFAULT_BATCH_SIZE}.",
        )
        parser.add_argument(
            "--flush-target",
            action="store_true",
            help="Vide la base cible avant import. A utiliser seulement sur une base neuve ou jetable.",
        )
        parser.add_argument(
            "--sequences-only",
            action="store_true",
            help="Ne fait que remettre a niveau les sequences PostgreSQL, sans recopier les donnees.",
        )

    def handle(self, *args, **options):
        source_db = options["source"]
        target_db = options["target"]
        app_labels = options["apps"] or ["api"]
        batch_size = max(1, int(options["batch_size"]))
        sqlite_path = options.get("sqlite_path")
        sequences_only = options["sequences_only"]

        self._configure_sqlite_source(source_db, sqlite_path)
        self._validate_databases(source_db, target_db)

        models_to_copy = self._collect_models(app_labels)
        ordered_models = self._order_models(models_to_copy)

        if sequences_only and options["flush_target"]:
            raise CommandError("--sequences-only ne peut pas etre utilise avec --flush-target.")

        if sequences_only:
            self._reset_sequences(target_db, ordered_models)
            self.stdout.write(self.style.SUCCESS("Sequences PostgreSQL remises a niveau."))
            return

        if options["flush_target"]:
            self.stdout.write(self.style.WARNING(f"Vidage de la base cible '{target_db}'..."))
            call_command("flush", database=target_db, interactive=False, verbosity=0)

        total_models = len(ordered_models)
        for index, model in enumerate(ordered_models, start=1):
            copied = self._copy_model(model, source_db, target_db, batch_size=batch_size)
            self.stdout.write(
                f"[{index}/{total_models}] {model._meta.label}: {copied} ligne(s) copiee(s)"
            )

        self._reset_sequences(target_db, ordered_models)
        self.stdout.write(
            self.style.SUCCESS(
                "Reprise terminee. Pense a relancer un import applicatif si tu veux rafraichir les donnees Riot."
            )
        )

    def _configure_sqlite_source(self, source_db, sqlite_path):
        if sqlite_path:
            sqlite_file = Path(sqlite_path)
            if not sqlite_file.is_absolute():
                sqlite_file = Path(settings.BASE_DIR) / sqlite_file
            connections.databases[source_db] = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": sqlite_file,
            }

        if source_db not in connections.databases:
            raise CommandError(
                f"Base source '{source_db}' introuvable. Configure SQLITE_IMPORT_PATH ou utilise --sqlite-path."
            )

    def _validate_databases(self, source_db, target_db):
        if source_db == target_db:
            raise CommandError("La base source et la base cible doivent etre differentes.")

        source_settings = connections[source_db].settings_dict
        target_settings = connections[target_db].settings_dict

        if source_settings["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("La source doit etre une base SQLite.")

        if target_settings["ENGINE"] == "django.db.backends.sqlite3":
            raise CommandError(
                "La cible est encore en SQLite. Configure PostgreSQL sur la base 'default' avant la reprise."
            )

    def _collect_models(self, app_labels):
        models_to_copy = []
        for app_label in app_labels:
            app_config = apps.get_app_config(app_label)
            models_to_copy.extend(list(app_config.get_models()))

        if not models_to_copy:
            raise CommandError("Aucun modele a reprendre.")

        return models_to_copy

    def _order_models(self, models_to_copy):
        model_set = set(models_to_copy)
        dependency_graph = defaultdict(set)
        reverse_graph = defaultdict(set)
        indegree = {model: 0 for model in models_to_copy}

        for model in models_to_copy:
            dependencies = {
                field.remote_field.model
                for field in model._meta.get_fields()
                if isinstance(field, (ForeignKey, OneToOneField))
                and field.concrete
                and field.remote_field
                and field.remote_field.model in model_set
                and not field.null
            }
            for dependency in dependencies:
                if model not in reverse_graph[dependency]:
                    reverse_graph[dependency].add(model)
                    dependency_graph[model].add(dependency)
                    indegree[model] += 1

        queue = deque([model for model, degree in indegree.items() if degree == 0])
        ordered_models = []

        while queue:
            model = queue.popleft()
            ordered_models.append(model)
            for child in reverse_graph[model]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

        if len(ordered_models) != len(models_to_copy):
            remaining = [model._meta.label for model, degree in indegree.items() if degree > 0]
            raise CommandError(
                "Impossible d'ordonner les dependances de reprise pour: " + ", ".join(sorted(remaining))
            )

        return ordered_models

    def _copy_model(self, model, source_db, target_db, batch_size):
        field_names = [field.attname for field in model._meta.concrete_fields]

        source_queryset = model.objects.using(source_db).order_by(model._meta.pk.attname).iterator(
            chunk_size=batch_size
        )
        model.objects.using(target_db).all().delete()

        total = 0
        batch = []

        for source_obj in source_queryset:
            payload = {field_name: getattr(source_obj, field_name) for field_name in field_names}
            batch.append(model(**payload))
            if len(batch) >= batch_size:
                total += self._flush_batch(model, target_db, batch, batch_size)
                batch = []

        if batch:
            total += self._flush_batch(model, target_db, batch, batch_size)

        return total

    def _flush_batch(self, model, target_db, batch, batch_size):
        with transaction.atomic(using=target_db):
            model.objects.using(target_db).bulk_create(batch, batch_size=batch_size)
        return len(batch)

    def _reset_sequences(self, database, models_to_copy):
        with connections[database].cursor() as cursor:
            for model in models_to_copy:
                pk_field = model._meta.pk
                if not isinstance(pk_field, (AutoField, BigAutoField, SmallAutoField)):
                    continue

                table_name = model._meta.db_table
                pk_column = pk_field.column
                quoted_table_name = connections[database].ops.quote_name(table_name)
                quoted_pk_column = connections[database].ops.quote_name(pk_column)

                cursor.execute(
                    f"SELECT COALESCE(MAX({quoted_pk_column}), 1) FROM {quoted_table_name}"
                )
                max_pk = cursor.fetchone()[0] or 1

                cursor.execute("SELECT pg_get_serial_sequence(%s, %s)", [table_name, pk_column])
                sequence_name = cursor.fetchone()[0]
                if not sequence_name:
                    continue

                cursor.execute("SELECT setval(%s, %s, true)", [sequence_name, max_pk])

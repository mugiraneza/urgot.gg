"""
Reprise de donnees : remplit les colonnes ajoutees (migration 0014) a partir de
Match.objet_complet, sans aucun appel a l'API Riot.

    python manage.py backfill_objet_complet --dry-run      # simulation, rien n'est ecrit
    python manage.py backfill_objet_complet                # reprise des matchs pas encore traites
    python manage.py backfill_objet_complet --force        # retraite tous les matchs
    python manage.py backfill_objet_complet --match-id EUW1_123

- Traitement par lots, une transaction par lot : un arret en cours de route ne laisse
  jamais un match a moitie repris, et relancer la commande reprend la ou elle s'est arretee.
- Un match est considere comme repris quand Match.data_version est renseigne
  (ecrit dans la meme transaction que ses equipes et participants).
- Les participants/equipes presents dans le JSON mais absents en base sont signales :
  ils relevent de l'endpoint de reparation `import/repair-stored-imports/`.
"""
import json
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from api.models import Match, Participant, Team
from api.services.riot_mapping import (
    MATCH_BACKFILL_FIELDS,
    PARTICIPANT_BACKFILL_FIELDS,
    TEAM_BACKFILL_FIELDS,
    match_raw_fields,
    participant_raw_fields,
    team_raw_fields,
)


class Command(BaseCommand):
    help = "Remplit les nouvelles colonnes Match/Team/Participant depuis Match.objet_complet."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Nombre de matchs par lot (defaut 100).")
        parser.add_argument("--match-id", help="Ne traiter qu'un seul match.")
        parser.add_argument("--limit", type=int, help="Nombre maximum de matchs a traiter.")
        parser.add_argument("--force", action="store_true", help="Retraiter aussi les matchs deja repris.")
        parser.add_argument("--dry-run", action="store_true", help="Calculer sans rien ecrire en base.")

    def handle(self, *args, **options):
        batch_size = max(1, options["batch_size"])
        dry_run = options["dry_run"]

        queryset = Match.objects.filter(objet_complet__isnull=False)
        if options["match_id"]:
            queryset = queryset.filter(match_id=options["match_id"])
        elif not options["force"]:
            queryset = queryset.filter(data_version__isnull=True)

        total = queryset.count()
        if options["limit"]:
            total = min(total, options["limit"])
        without_raw = Match.objects.filter(objet_complet__isnull=True).count()

        self.stdout.write(
            f"{total} match(s) a reprendre"
            f"{' (simulation, aucune ecriture)' if dry_run else ''}. "
            f"{without_raw} match(s) sans objet_complet ignores (non reprenables sans rappeler l'API Riot)."
        )
        if not total:
            return

        stats = {"matches": 0, "teams": 0, "participants": 0, "skipped": 0}
        anomalies = []
        started_at = time.monotonic()
        last_match_id = ""

        while stats["matches"] + stats["skipped"] < total:
            remaining = total - stats["matches"] - stats["skipped"]
            # Pagination par cle (match_id) : stable meme si des lignes sont modifiees en cours de route.
            batch_ids = list(
                queryset.filter(match_id__gt=last_match_id)
                .order_by("match_id")
                .values_list("match_id", flat=True)[: min(batch_size, remaining)]
            )
            if not batch_ids:
                break
            last_match_id = batch_ids[-1]

            batch_stats, batch_anomalies = self._process_batch(batch_ids, dry_run)
            for key, value in batch_stats.items():
                stats[key] += value
            anomalies.extend(batch_anomalies)

            done = stats["matches"] + stats["skipped"]
            elapsed = time.monotonic() - started_at
            eta = elapsed / done * (total - done) if done else 0
            self.stdout.write(
                f"  {done}/{total} matchs | {stats['participants']} participants | "
                f"{elapsed:.0f}s ecoulees, ~{eta:.0f}s restantes"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Termine en {time.monotonic() - started_at:.1f}s : {stats['matches']} matchs, "
                f"{stats['teams']} equipes, {stats['participants']} participants "
                f"{'calcules' if dry_run else 'mis a jour'}, {stats['skipped']} match(s) sans info ignores."
            )
        )
        if anomalies:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(anomalies)} match(s) incomplets en base (joueurs ou equipes manquants). "
                    "Les reparer avec POST /api/import/repair-stored-imports/ puis relancer cette commande :"
                )
            )
            for match_id, detail in anomalies[:20]:
                self.stdout.write(f"  - {match_id} : {detail}")
            if len(anomalies) > 20:
                self.stdout.write(f"  ... et {len(anomalies) - 20} autre(s).")

    def _process_batch(self, match_ids, dry_run):
        stats = {"matches": 0, "teams": 0, "participants": 0, "skipped": 0}
        anomalies = []

        matches = list(Match.objects.filter(pk__in=match_ids).only("match_id", "objet_complet"))
        teams_by_key = {
            (team.match_id, team.team_id): team
            for team in Team.objects.filter(match_id__in=match_ids).only("id", "match_id", "team_id")
        }
        participants_by_key = {
            (participant.match_id, participant.participant_id): participant
            for participant in Participant.objects.filter(match_id__in=match_ids).only(
                "id", "match_id", "participant_id"
            )
        }

        matches_to_update, teams_to_update, participants_to_update = [], [], []
        for match in matches:
            stored_match = match.objet_complet or {}
            info = stored_match.get("info") or {}
            if not info:
                stats["skipped"] += 1
                continue

            for field, value in match_raw_fields(stored_match).items():
                setattr(match, field, value)
            matches_to_update.append(match)

            missing = []
            for raw_team in info.get("teams") or []:
                team = teams_by_key.get((match.match_id, raw_team.get("teamId")))
                if team is None:
                    missing.append(f"equipe {raw_team.get('teamId')}")
                    continue
                for field, value in team_raw_fields(raw_team).items():
                    setattr(team, field, value)
                teams_to_update.append(team)

            for raw_participant in info.get("participants") or []:
                participant = participants_by_key.get((match.match_id, raw_participant.get("participantId")))
                if participant is None:
                    missing.append(f"joueur {raw_participant.get('participantId')}")
                    continue
                for field, value in participant_raw_fields(raw_participant).items():
                    setattr(participant, field, value)
                participants_to_update.append(participant)

            if missing:
                anomalies.append((match.match_id, ", ".join(missing)))

        stats["matches"] = len(matches_to_update)
        stats["teams"] = len(teams_to_update)
        stats["participants"] = len(participants_to_update)

        if not dry_run:
            with transaction.atomic():
                _bulk_update(Participant, participants_to_update, PARTICIPANT_BACKFILL_FIELDS)
                _bulk_update(Team, teams_to_update, TEAM_BACKFILL_FIELDS)
                # En dernier : data_version sert de marqueur "match repris".
                _bulk_update(Match, matches_to_update, MATCH_BACKFILL_FIELDS)

        return stats, anomalies


POSTGRES_RECORD_TYPES = {
    "IntegerField": "integer",
    "BigIntegerField": "bigint",
    "BigAutoField": "bigint",
    "AutoField": "integer",
    "FloatField": "double precision",
    "BooleanField": "boolean",
    "CharField": "text",
    "TextField": "text",
    "JSONField": "jsonb",
}


def _bulk_update(model, objects, field_names):
    """
    Met a jour `field_names` pour tous les objets en une seule requete.

    Sous PostgreSQL : UPDATE ... FROM jsonb_to_recordset(...), bien plus rapide que
    bulk_update de Django qui genere un CASE WHEN par colonne et par ligne
    (78 colonnes x 1000 joueurs par lot). Ailleurs (SQLite) : bulk_update classique.
    """
    if not objects:
        return
    if connection.vendor != "postgresql":
        model.objects.bulk_update(objects, field_names, batch_size=250)
        return

    pk_field = model._meta.pk
    fields = [model._meta.get_field(name) for name in field_names]
    columns = [pk_field] + fields
    record_definition = ", ".join(
        f"{connection.ops.quote_name(field.column)} {POSTGRES_RECORD_TYPES[field.get_internal_type()]}"
        for field in columns
    )
    assignments = ", ".join(
        f"{connection.ops.quote_name(field.column)} = r.{connection.ops.quote_name(field.column)}"
        for field in fields
    )
    table = connection.ops.quote_name(model._meta.db_table)
    pk_column = connection.ops.quote_name(pk_field.column)
    rows = [{field.column: getattr(obj, field.attname) for field in columns} for obj in objects]

    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {table} AS t SET {assignments} "
            f"FROM jsonb_to_recordset(%s::jsonb) AS r({record_definition}) "
            f"WHERE t.{pk_column} = r.{pk_column}",
            [json.dumps(rows)],
        )

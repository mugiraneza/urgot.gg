from django.core.management.base import BaseCommand, CommandError

from api.services.tracked_imports import import_all_tracked_summoners, run_tracked_import_polling_service


class Command(BaseCommand):
    help = "Importe les matchs de tous les joueurs suivis, puis recommence periodiquement."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval-minutes",
            type=float,
            default=30.0,
            help="Intervalle en minutes entre deux batches complets.",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Execute un seul batch d'import puis quitte.",
        )

    def handle(self, *args, **options):
        try:
            if options["once"]:
                summary = import_all_tracked_summoners()
                self.stdout.write(
                    self.style.SUCCESS(
                        "Batch termine: "
                        f"total={summary['total']} success={summary['success']} error={summary['error']}"
                    )
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    "Service de batch demarre. Ctrl+C pour l'arreter."
                )
            )
            run_tracked_import_polling_service(interval_minutes=options["interval_minutes"])
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Service arrete par l'utilisateur."))
        except Exception as exc:
            raise CommandError(str(exc)) from exc

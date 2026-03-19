from django.core.management.base import BaseCommand

from api.services.riot_importer import run_match_import

import os


RIOT_API_KEY = os.getenv("RIOT_KEY")
RIOT_ID = os.getenv("RIOT_ID", "proctologue#urgot")
REGION = os.getenv("RIOT_REGION", "europe")


class Command(BaseCommand):
    help = "Collect League of Legends match data and save to the database"

    def handle(self, *args, **kwargs):
        if not RIOT_API_KEY:
            self.stderr.write("RIOT_API_KEY manquante.")
            return

        run_match_import(RIOT_ID, REGION)
        self.stdout.write(self.style.SUCCESS("Importation terminee."))

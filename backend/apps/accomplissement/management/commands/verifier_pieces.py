import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accomplissement.services.integrite import verifier_toutes
from apps.missions.models import Mission


class Command(BaseCommand):
    help = "Vérifie l'empreinte SHA-256 de chaque pièce justificative (code 1 en cas d'écart)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--mission", help="Référence de la mission (ex. DAI/2026/M01).")

    def handle(self, *args: Any, **options: Any) -> None:
        mission = None
        if options["mission"]:
            mission = Mission.all_objects.filter(reference=options["mission"]).first()
            if mission is None:
                raise CommandError(f"Mission introuvable : {options['mission']}.")
        ecarts = verifier_toutes(mission)
        for ecart in ecarts:
            self.stderr.write(
                f"ECART : pièce {ecart.piece.numero} ({ecart.piece.mission.reference}) "
                f"attendu {ecart.attendu}, obtenu {ecart.obtenu}."
            )
        self.stdout.write(f"{len(ecarts)} écart(s) d'intégrité.")
        if ecarts:
            sys.exit(1)

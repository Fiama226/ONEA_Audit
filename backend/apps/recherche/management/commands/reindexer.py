from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.recherche.client import moteur
from apps.recherche.exceptions import RechercheIndisponibleError
from apps.recherche.services import reconcilier_index
from apps.recherche.sources import SOURCES


class Command(BaseCommand):
    help = (
        "Configure l'index puis le réindexe (en synchrone). Code 1 si le moteur est indisponible."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--type",
            choices=sorted(SOURCES),
            default=None,
            help="Ne réindexer que ce type (l'index n'est alors pas vidé).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            moteur().configurer()
            total = reconcilier_index(options["type"])
        except RechercheIndisponibleError as exc:
            raise CommandError(exc.message) from None
        self.stdout.write(f"{total} document(s) indexé(s).")

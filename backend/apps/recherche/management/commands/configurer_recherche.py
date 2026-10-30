from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.recherche.client import moteur
from apps.recherche.exceptions import RechercheIndisponibleError


class Command(BaseCommand):
    help = "Applique les réglages de l'index de recherche (idempotent). Code 1 si indisponible."

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            moteur().configurer()
        except RechercheIndisponibleError as exc:
            raise CommandError(exc.message) from None
        self.stdout.write("Index de recherche configuré.")

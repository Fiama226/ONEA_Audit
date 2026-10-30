"""Exploitation et e2e : planifie et envoie les relances (`--simulation` : liste seulement)."""

from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.suivi import relances


def _date(valeur: str) -> date:
    try:
        return date.fromisoformat(valeur)
    except ValueError as exc:
        raise CommandError("La date doit être au format AAAA-MM-JJ.") from exc


class Command(BaseCommand):
    help = "Planifie et envoie les relances du suivi des recommandations."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--date", type=_date, default=None, help="Jour simulé (AAAA-MM-JJ).")
        parser.add_argument(
            "--simulation",
            action="store_true",
            help="Liste les relances sans rien écrire ni envoyer.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        jour: date | None = options["date"]
        if options["simulation"]:
            lignes = relances.simuler(jour)
            for mission, suivi, palier, deja in lignes:
                etat = "déjà planifiée" if deja else "à planifier"
                self.stdout.write(
                    f"{mission.reference} | action {suivi.action_id} | "
                    f"{suivi.echeance:%d/%m/%Y} | {palier} | {etat}"
                )
            self.stdout.write(f"{len(lignes)} relance(s) due(s) (simulation, rien n'est envoyé).")
            return
        lots = relances.executer_relances(jour)
        self.stdout.write(f"{lots} e-mail(s) traité(s).")

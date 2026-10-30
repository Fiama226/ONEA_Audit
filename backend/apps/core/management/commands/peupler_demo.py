"""Peuple une base vide avec des données fictives de formation ou de volumétrie (opt-in)."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core import demo
from apps.documents.models import Document
from apps.missions.models import Mission
from apps.programmation.models import ProgrammeAnnuel
from apps.referentiel.models import CartographieVersion, Direction, Processus
from apps.users.models import User

COMPTES_RESERVES = ("demo", "admin", "rai", "dg", "auditeur1", "audite1")


def objets_metier_presents() -> list[str]:
    """Familles d'objets métier déjà présentes (suppressions logiques incluses)."""
    familles: list[tuple[str, Any]] = [
        ("directions", Direction),
        ("processus", Processus),
        ("cartographies", CartographieVersion),
        ("programmes", ProgrammeAnnuel),
        ("missions", Mission),
        ("documents", Document),
    ]
    return [nom for nom, modele in familles if modele.all_objects.exists()]


class Command(BaseCommand):
    help = (
        "Peuple une base VIDE avec des données fictives (profil formation ou volumetrie), "
        "par les services métier. Interdit en production. Jamais lancé automatiquement."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--profil", choices=demo.PROFILS, required=True)
        parser.add_argument(
            "--echelle", type=float, default=1.0, help="Facteur de volumes (1 = complet)."
        )
        parser.add_argument("--graine", type=int, default=demo.GRAINE_PAR_DEFAUT)
        parser.add_argument(
            "--a-blanc", action="store_true", help="Affiche le plan sans rien écrire."
        )
        parser.add_argument(
            "--recette",
            action="store_true",
            help="Autorise explicitement l'environnement de recette (jamais la production).",
        )
        parser.add_argument(
            "--avec-pdf",
            action="store_true",
            help="Convertit aussi les documents en PDF (Gotenberg requis).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        demo.verifier_environnement(recette=options["recette"])
        volumes = demo.volumes(options["profil"], options["echelle"])
        if self._deja_peuplee():
            self.stdout.write(
                "Données de démonstration déjà présentes : rien à faire (aucun doublon créé)."
            )
            return
        presents = objets_metier_presents()
        if presents or User.objects.filter(username__in=COMPTES_RESERVES).exists():
            raise CommandError(
                "La base contient déjà des objets métier ou des comptes réservés "
                f"({', '.join(presents) or 'comptes'}) : le peuplement exige une base vide."
            )
        if options["a_blanc"]:
            self.stdout.write("Simulation à blanc : aucune écriture.")
            self.stdout.write(f"Profil {options['profil']}, graine {options['graine']}.")
            for nom, valeur in vars(volumes).items():
                self.stdout.write(f"  {nom} : {valeur}")
            return
        ctx = demo.ContexteDemo(
            profil=options["profil"],
            echelle=options["echelle"],
            graine=options["graine"],
            volumes=volumes,
            avec_pdf=options["avec_pdf"],
            sortie=self.stdout.write,
        )
        demo.peupler_tout(ctx)
        for message in ctx.avertissements:
            self.stdout.write(self.style.WARNING(f"Attention : {message}"))
        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))

    def _deja_peuplee(self) -> bool:
        acteur = User.objects.filter(username=demo.ACTEUR).first()
        return acteur is not None and Direction.all_objects.exists()

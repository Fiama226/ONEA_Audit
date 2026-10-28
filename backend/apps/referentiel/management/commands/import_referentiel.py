import os
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.referentiel.imports import ImportReferentielError, importer_referentiel
from apps.users.models import Role, User

TAILLE_MAX = 5 * 1024 * 1024  # octets : borne la mémoire utilisée, 5 000 lignes tiennent en < 1 Mio

_LIBELLES = (
    ("directions", "Directions"),
    ("departements", "Départements"),
    ("processus", "Processus"),
)


class Command(BaseCommand):
    help = (
        "Importe (ou met à jour) directions, départements et processus depuis un CSV UTF-8 "
        "« ; ». Idempotent, tout ou rien, ne supprime rien."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("chemin", help="Fichier CSV à importer")
        parser.add_argument(
            "--user", required=True, help="Identifiant d'un utilisateur RAI ou ADMIN"
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Simule l'import sans rien écrire"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user = User.objects.filter(username=options["user"]).first()
        if user is None or not user.is_active:
            raise CommandError(f"Utilisateur « {options['user']} » introuvable ou inactif.")
        if not user.has_role(Role.RAI, Role.ADMIN):
            raise CommandError("L'import est réservé aux utilisateurs RAI ou ADMIN.")
        dry_run = bool(options["dry_run"])
        try:
            if os.path.getsize(options["chemin"]) > TAILLE_MAX:
                raise CommandError(
                    f"Fichier trop volumineux : {TAILLE_MAX // (1024 * 1024)} Mio au maximum."
                )
            with open(options["chemin"], encoding="utf-8-sig", newline="") as flux:
                rapport = importer_referentiel(flux, by=user, dry_run=dry_run)
        except OSError as e:
            raise CommandError(f"Fichier illisible : {e}") from e
        except ImportReferentielError as e:
            for erreur in e.erreurs:
                self.stderr.write(erreur)
            raise CommandError(
                f"Import refusé : {len(e.erreurs)} erreur(s), aucune donnée écrite."
            ) from e
        if dry_run:
            self.stdout.write("Simulation : aucune donnée écrite.")
        for cle, nom in _LIBELLES:
            self.stdout.write(
                f"{nom} : {rapport.crees[cle]} créées, {rapport.mis_a_jour[cle]} mises à jour"
            )
        self.stdout.write(f"Inchangés : {rapport.inchanges}")

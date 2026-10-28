"""Pre-provision accounts from the Keycloak directory or a CSV file (operations only)."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.users.keycloak_admin import KeycloakAdminError
from apps.users.models import Role, User
from apps.users.provisioning import (
    FichierImportInvalide,
    RapportImport,
    importer_csv,
    importer_depuis_annuaire,
    rechercher_annuaire,
)


class Command(BaseCommand):
    help = (
        "Importe des comptes depuis l'annuaire Keycloak (--keycloak) ou un fichier CSV (--csv). "
        "Sans --apply, la commande ne fait qu'une vérification à blanc."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--keycloak", action="store_true", help="Importer depuis Keycloak.")
        source.add_argument("--csv", metavar="CHEMIN", help="Importer depuis un fichier CSV.")
        parser.add_argument(
            "--search", metavar="TEXTE", help="Avec --keycloak : ne traiter que la recherche."
        )
        parser.add_argument("--apply", action="store_true", help="Écrire réellement les comptes.")
        parser.add_argument(
            "--by", metavar="IDENTIFIANT_ADMIN", help="Administrateur actif à historiser."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["search"] and not options["keycloak"]:
            raise CommandError("L'option --search ne s'utilise qu'avec --keycloak.")
        par = self._acteur(options["by"])
        dry_run = not options["apply"]
        try:
            if options["keycloak"]:
                ids = None
                if options["search"]:
                    ids = [e.keycloak_id for e in rechercher_annuaire(options["search"])]
                rapport = importer_depuis_annuaire(ids, by=par, dry_run=dry_run)
            else:
                rapport = self._csv(options["csv"], par, dry_run)
        except KeycloakAdminError as exc:
            raise CommandError(exc.message, returncode=1) from exc
        self._afficher(rapport)

    def _acteur(self, identifiant: str | None) -> User | None:
        if not identifiant:
            return None
        compte = User.objects.filter(username=identifiant, role=Role.ADMIN, is_active=True).first()
        if compte is None:
            raise CommandError(
                f"« {identifiant} » n'est pas un administrateur actif de la plateforme."
            )
        return compte

    def _csv(self, chemin: str, par: User | None, dry_run: bool) -> RapportImport:
        try:
            contenu = Path(chemin).read_bytes()
        except OSError as exc:
            raise CommandError(f"Fichier illisible : {chemin}") from exc
        try:
            return importer_csv(contenu, by=par, dry_run=dry_run)
        except FichierImportInvalide as exc:
            raise CommandError(exc.message) from exc

    def _afficher(self, rapport: RapportImport) -> None:
        if rapport.dry_run:
            self.stdout.write("Vérification à blanc : aucune écriture (ajoutez --apply).")
        else:
            self.stdout.write("Import appliqué.")
        self.stdout.write(f"Comptes créés : {len(rapport.crees)}")
        for identifiant in rapport.crees:
            self.stdout.write(f"  + {identifiant}")
        self.stdout.write(f"Comptes mis à jour : {len(rapport.mis_a_jour)}")
        for identifiant in rapport.mis_a_jour:
            self.stdout.write(f"  ~ {identifiant}")
        self.stdout.write(f"Lignes ignorées : {len(rapport.ignores)}")
        for ligne in rapport.ignores:
            where = f"ligne {ligne.ligne}" if ligne.ligne is not None else "annuaire"
            self.stdout.write(f"  - {where} ({ligne.identifiant}) : {ligne.motif}")

"""Pre-provision accounts from the Keycloak directory or a CSV file (operations only).

A CSV import creates local accounts with temporary passwords, emailed when sending is on.
The passwords no email carried are never printed: they go to the one-time file of the
import (downloadable once by the --by administrator, within 24 h), or straight to a new
local file with --fichier-mots-de-passe: that file is created (new file only) before the
import, and the server copy is destroyed only once the local one is written.
"""

import os
from pathlib import Path
from typing import Any, TextIO
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.users.keycloak_admin import KeycloakAdminError
from apps.users.models import Role, User
from apps.users.provisioning import (
    CSV_MAX_BYTES,
    FichierImportInvalide,
    RapportImport,
    importer_csv,
    importer_depuis_annuaire,
    lire_fichier_mots_de_passe,
    rechercher_annuaire,
)

URL_FICHIER = "/api/v1/user-accounts/import-passwords/{}/"


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
        parser.add_argument(
            "--sans-courriel",
            action="store_true",
            help="Avec --csv : ne pas envoyer les courriels de bienvenue.",
        )
        parser.add_argument(
            "--fichier-mots-de-passe",
            metavar="CHEMIN",
            help=(
                "Avec --csv --apply : écrire les mots de passe non envoyés dans ce NOUVEAU "
                "fichier (droits 600) au lieu de les garder 24 h pour un téléchargement."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["search"] and not options["keycloak"]:
            raise CommandError("L'option --search ne s'utilise qu'avec --keycloak.")
        if options["apply"] and not options["by"]:
            raise CommandError("L'option --apply exige --by IDENTIFIANT_ADMIN (piste d'audit).")
        cible = options["fichier_mots_de_passe"]
        if cible and not (options["csv"] and options["apply"]):
            raise CommandError("L'option --fichier-mots-de-passe exige --csv et --apply.")
        par = self._acteur(options["by"])
        dry_run = not options["apply"]
        # The target is created (new file only) BEFORE the import: an unwritable path stops
        # everything while nothing has been written yet.
        sortie = self._ouvrir(cible) if cible else None
        ecrit = False
        try:
            try:
                if options["keycloak"]:
                    ids = None
                    if options["search"]:
                        ids = [e.keycloak_id for e in rechercher_annuaire(options["search"])]
                    rapport = importer_depuis_annuaire(ids, by=par, dry_run=dry_run)
                else:
                    rapport = self._csv(options["csv"], par, dry_run, not options["sans_courriel"])
            except KeycloakAdminError as exc:
                raise CommandError(exc.message, returncode=1) from exc
            self._afficher(rapport)
            fichier_id = rapport.fichier_mots_de_passe_id
            if fichier_id is None or par is None:
                if sortie is not None:
                    self.stdout.write(
                        "Aucun mot de passe à écrire : tous sont partis par courriel."
                    )
            elif sortie is None:
                url = URL_FICHIER.format(fichier_id)
                self.stdout.write(
                    "Mots de passe temporaires non envoyés par courriel : fichier à télécharger "
                    f"une seule fois, sous 24 h, par {par.username} : {url}"
                )
            else:
                self._ecrire(sortie, fichier_id, par, str(cible))
                ecrit = True
        finally:
            if sortie is not None:
                sortie.close()
                if not ecrit:
                    Path(str(cible)).unlink(missing_ok=True)

    def _ouvrir(self, cible: str) -> TextIO:
        """New file only (O_EXCL), readable by its owner only."""
        try:
            descripteur = os.open(cible, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise CommandError(
                f"Le fichier {cible} existe déjà : choisissez un nouveau chemin."
            ) from exc
        except OSError as exc:
            raise CommandError(f"Impossible de créer le fichier {cible} : {exc.strerror}.") from exc
        return os.fdopen(descripteur, "w", encoding="utf-8", newline="")

    def _ecrire(self, sortie: TextIO, fichier_id: UUID, par: User, cible: str) -> None:
        """Copy the server file to the local one; the server copy is destroyed only once
        the local one is safely written (the read is rolled back otherwise)."""
        try:
            with transaction.atomic():
                texte = lire_fichier_mots_de_passe(fichier_id, par=par)
                sortie.write(texte)
                sortie.flush()
                os.fsync(sortie.fileno())
        except OSError as exc:
            raise CommandError(
                f"Écriture impossible dans {cible} ({exc.strerror or exc}) : les mots de passe "
                f"restent à télécharger une seule fois, sous 24 h, par {par.username} : "
                f"{URL_FICHIER.format(fichier_id)}"
            ) from exc
        self.stdout.write(
            f"Mots de passe temporaires non envoyés par courriel écrits dans {cible}."
        )

    def _acteur(self, identifiant: str | None) -> User | None:
        if not identifiant:
            return None
        compte = User.objects.filter(username=identifiant, role=Role.ADMIN, is_active=True).first()
        if compte is None:
            raise CommandError(
                f"« {identifiant} » n'est pas un administrateur actif de la plateforme."
            )
        return compte

    def _csv(
        self, chemin: str, par: User | None, dry_run: bool, envoyer_courriel: bool
    ) -> RapportImport:
        try:
            with Path(chemin).open("rb") as fichier:
                contenu = fichier.read(CSV_MAX_BYTES + 1)  # bounded: the size is checked next
        except OSError as exc:
            raise CommandError(f"Fichier illisible : {chemin}") from exc
        try:
            return importer_csv(contenu, by=par, dry_run=dry_run, envoyer_courriel=envoyer_courriel)
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

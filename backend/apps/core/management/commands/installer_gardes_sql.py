"""Installe (ou vérifie avec `--verifier`) les déclencheurs de gel et les droits du rôle applicatif.

À lancer avec la connexion du PROPRIÉTAIRE des tables (jamais avec `onea_app`).
Code de sortie 1 si `--verifier` relève un écart.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core import gardes_sql


class Command(BaseCommand):
    help = "Installe ou vérifie les déclencheurs de gel en base (D6) et les droits de onea_app."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--verifier", action="store_true", help="Ne modifie rien ; code 1 si écart."
        )
        parser.add_argument(
            "--role", default=None, help="Rôle applicatif (défaut : POSTGRES_APP_USER)."
        )
        parser.add_argument(
            "--exiger-role", action="store_true", help="Avec --verifier : le rôle doit exister."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        role = options["role"]
        if options["verifier"]:
            problemes = gardes_sql.verifier(role=role, exiger_role=options["exiger_role"])
            if problemes:
                for p in problemes:
                    self.stderr.write(f"ECART : {p}")
                raise CommandError(f"{len(problemes)} écart(s) sur le gel en base.")
            self.stdout.write("Gel en base conforme.")
            return
        resultat = gardes_sql.installer(role=role)
        droits = (
            "droits appliqués" if resultat["droits"] else "rôle applicatif absent : droits ignorés"
        )
        self.stdout.write(f"{resultat['declencheurs']} déclencheur(s) posé(s) ; {droits}.")

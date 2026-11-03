"""Génère un certificat autosigné de DÉVELOPPEMENT pour la signature PAdES (pas en production)."""

import os
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.signatures.certificat_dev import generer_pkcs12


class Command(BaseCommand):
    help = (
        "Génère un PKCS#12 autosigné de développement et son certificat PEM (ancre de confiance). "
        "Interdit en production : l'ONEA fournit son propre certificat."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--sortie", required=True, help="Dossier de sortie (hors dépôt).")
        parser.add_argument("--phrase", required=True, help="Phrase secrète du PKCS#12.")
        parser.add_argument("--force", action="store_true", help="Écrase les fichiers existants.")

    def handle(self, *args: Any, **options: Any) -> None:
        if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith(".prod"):
            raise CommandError(
                "Commande interdite en production : fournir le certificat de l'ONEA."
            )
        dossier = Path(options["sortie"])
        dossier.mkdir(parents=True, exist_ok=True)
        p12, pem = generer_pkcs12(options["phrase"])
        cibles = {dossier / "signature-dev.p12": p12, dossier / "signature-dev-ancre.pem": pem}
        for chemin in cibles:
            if chemin.exists() and not options["force"]:
                raise CommandError(f"{chemin} existe déjà (utiliser --force).")
        for chemin, contenu in cibles.items():
            chemin.write_bytes(contenu)
        self.stdout.write(
            f"Certificat de développement écrit dans {dossier}. Variables à définir : "
            f"SIGNATURE_PKCS12_FILE={dossier / 'signature-dev.p12'} "
            "SIGNATURE_PKCS12_PASSPHRASE=<phrase> "
            f"SIGNATURE_ANCRES_CONFIANCE={dossier / 'signature-dev-ancre.pem'}"
        )

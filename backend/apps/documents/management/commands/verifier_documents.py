import hashlib
from pathlib import PurePosixPath
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.documents.models import DocumentVersion, GabaritDocument
from apps.documents.services.generation import verifier_integrite
from apps.documents.stockage import lire, stockage_documents


def _fichiers_stockes(dossier: str = "") -> list[str]:
    stockage = stockage_documents()
    sous_dossiers, fichiers = stockage.listdir(dossier)
    trouves = [str(PurePosixPath(dossier) / f) for f in fichiers if not f.startswith(".tmp-")]
    for sous in sous_dossiers:
        trouves += _fichiers_stockes(str(PurePosixPath(dossier) / sous))
    return trouves


class Command(BaseCommand):
    help = "Vérifie l'empreinte SHA-256 de chaque fichier de document stocké."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--orphelins", action="store_true", help="Liste les fichiers sans ligne en base."
        )
        parser.add_argument(
            "--manifeste",
            action="store_true",
            help="Imprime « clé;sha256 » des fichiers référencés.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        verifies = anomalies = 0
        references: dict[str, str] = {}
        for version in DocumentVersion.all_objects.select_related("document"):
            etat = verifier_integrite(version)
            for format, fichier, empreinte in (
                ("docx", version.fichier_docx, version.empreinte_docx),
                ("pdf", version.fichier_pdf, version.empreinte_pdf),
            ):
                if not fichier:
                    continue
                references[fichier.name] = empreinte
                verifies += 1
                if not etat[format]:
                    anomalies += 1
                    self.stderr.write(
                        f"ANOMALIE : {fichier.name} (version {version.pk}) absent ou altéré."
                    )
        for gabarit in GabaritDocument.all_objects.all():
            references[gabarit.fichier.name] = gabarit.empreinte
            verifies += 1
            try:
                lu = hashlib.sha256(lire(str(gabarit.fichier.name))).hexdigest()
                ok = lu == gabarit.empreinte
            except (OSError, ValueError):
                ok = False
            if not ok:
                anomalies += 1
                self.stderr.write(
                    f"ANOMALIE : {gabarit.fichier.name} (gabarit {gabarit.pk}) absent ou altéré."
                )
        self.stdout.write(f"{verifies} fichier(s) vérifié(s), {anomalies} anomalie(s).")
        if options["manifeste"]:
            for cle in sorted(references):
                self.stdout.write(f"{cle};{references[cle]}")
        if options["orphelins"]:
            self.stdout.write("Orphelins :")
            for cle in sorted(set(_fichiers_stockes()) - set(references)):
                self.stdout.write(cle)
        if anomalies:
            raise CommandError(f"{anomalies} anomalie(s) d'intégrité détectée(s).")

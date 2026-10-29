import importlib
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.documents.moteur.documentation import contenus_attendus, dossier_par_defaut
from apps.documents.moteur.registre import types_documents


def _charger_generateurs() -> None:
    """Import the document-type modules (they register themselves) when the package exists."""
    try:
        importlib.import_module("apps.documents.generators")
    except ModuleNotFoundError as exc:
        if exc.name != "apps.documents.generators":
            raise


class Command(BaseCommand):
    help = "Écrit ou vérifie la documentation Markdown des contrats de balises."

    def add_arguments(self, parser: CommandParser) -> None:
        groupe = parser.add_mutually_exclusive_group(required=True)
        groupe.add_argument("--ecrire", action="store_true", help="Écrit les fichiers.")
        groupe.add_argument("--verifier", action="store_true", help="Échoue si un fichier diffère.")
        parser.add_argument("--dossier", default=None, help="Dossier cible (défaut : docs/).")

    def handle(self, *args: Any, **options: Any) -> None:
        _charger_generateurs()
        dossier = Path(options["dossier"]) if options["dossier"] else dossier_par_defaut()
        attendus = contenus_attendus([t.contrat for t in types_documents()])
        if options["ecrire"]:
            dossier.mkdir(parents=True, exist_ok=True)
            for nom, contenu in attendus.items():
                (dossier / nom).write_text(contenu, encoding="utf-8", newline="\n")
            self.stdout.write(f"{len(attendus)} fichier(s) écrit(s) dans {dossier}.")
            return
        problemes: list[str] = []
        for nom, contenu in attendus.items():
            fichier = dossier / nom
            if not fichier.exists():
                problemes.append(f"{nom} : fichier manquant.")
            elif fichier.read_text(encoding="utf-8") != contenu:
                problemes.append(f"{nom} : contenu périmé.")
        if dossier.exists():
            problemes.extend(
                f"{p.name} : fichier non reconnu."
                for p in sorted(dossier.glob("*.md"))
                if p.name not in attendus
            )
        if problemes:
            raise CommandError(
                "Documentation des contrats à régénérer (contrats_documents --ecrire) : "
                + " ".join(problemes)
            )
        self.stdout.write("Documentation des contrats à jour.")

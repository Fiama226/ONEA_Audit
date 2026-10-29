import importlib
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.documents.models import GabaritDocument, StatutGabarit
from apps.documents.moteur.provisoires import construire_gabarit_provisoire
from apps.documents.moteur.registre import types_documents
from apps.documents.services.gabarits import activer_gabarit, deposer_gabarit, verrouiller_type
from apps.users.models import Role, User


def _charger_generateurs() -> None:
    try:
        importlib.import_module("apps.documents.generators")
    except ModuleNotFoundError as exc:
        if exc.name != "apps.documents.generators":
            raise


class Command(BaseCommand):
    help = "Liste ou installe les gabarits Word provisoires des types sans gabarit actif."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--installer", action="store_true", help="Dépose et active.")
        parser.add_argument("--user", default=None, help="Login de l'auteur du dépôt.")

    def handle(self, *args: Any, **options: Any) -> None:
        _charger_generateurs()
        actifs = set(
            GabaritDocument.objects.filter(statut=StatutGabarit.ACTIF).values_list(
                "type_document", flat=True
            )
        )
        manquants = [t for t in types_documents() if t.code not in actifs]
        if not options["installer"]:
            for t in manquants:
                self.stdout.write(f"{t.code} : aucun gabarit actif ({t.libelle}).")
            self.stdout.write(f"{len(manquants)} type(s) sans gabarit actif.")
            return
        if not options["user"]:
            raise CommandError("L'option --user <login> est obligatoire avec --installer.")
        try:
            auteur = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            raise CommandError(f"Utilisateur introuvable : {options['user']}.") from None
        if auteur.role != Role.ADMIN:
            raise CommandError("L'utilisateur doit avoir le rôle administrateur.")
        installes = 0
        for t in manquants:
            with transaction.atomic():
                verrouiller_type(t.code)
                if GabaritDocument.objects.filter(
                    type_document=t.code, statut=StatutGabarit.ACTIF
                ).exists():  # re-check under the lock: never replace a real template
                    continue
                gabarit = deposer_gabarit(
                    type_document=t.code,
                    contenu=construire_gabarit_provisoire(t),
                    nom_original=f"gabarit-provisoire-{t.code.lower()}.docx",
                    by=auteur,
                    commentaire="Gabarit provisoire en attente du modèle officiel ONEA.",
                    provisoire=True,
                )
                activer_gabarit(gabarit, by=auteur)
            installes += 1
            self.stdout.write(f"{t.code} : gabarit provisoire installé.")
        self.stdout.write(f"{installes} gabarit(s) provisoire(s) installé(s).")

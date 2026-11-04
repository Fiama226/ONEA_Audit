"""E2E ONLY: create the test accounts of the Playwright suite with a known password.

The browser tests log in through the real form, so their accounts need a password that is
known in advance and a state that skips the forced change (``doit_changer_mot_de_passe``
cleared, no expiry, no login code). That is exactly what must never exist in a real
deployment, hence three guards, all checked before any write:

* ``DEBUG`` must be on (never true in the production settings);
* the database name must match ``^onea_e2e_[0-9]+$`` (the throw-away database that
  ``scripts/e2e.sh`` / ``scripts/e2e.ps1`` create and drop);
* the password comes from ``--mot-de-passe`` or the ``E2E_PASSWORD`` variable, never a default.

Idempotent: an existing account of the list is reset to the same state. A delegate account
(``delegue1``, an AUDITEUR holding every delegated account-management right) is included to
exercise ``/administration/utilisateurs`` as a non-administrator.
"""

import os
import re
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction

from apps.users.models import DelegationGestionComptes, OrigineCompte, Role, User

NOM_BASE_E2E = re.compile(r"^onea_e2e_[0-9]+$")
DIRECTION_AUDITE = "DEX"

# (identifiant, rôle, direction)
COMPTES_E2E: tuple[tuple[str, Role, str], ...] = (
    ("admin", Role.ADMIN, ""),
    ("rai", Role.RAI, ""),
    ("dg", Role.DG, ""),
    ("auditeur1", Role.AUDITEUR, ""),
    ("auditeur2", Role.AUDITEUR, ""),
    ("delegue1", Role.AUDITEUR, ""),
    ("audite1", Role.AUDITE, DIRECTION_AUDITE),
)
DELEGUE = "delegue1"


class Command(BaseCommand):
    help = (
        "E2E UNIQUEMENT : crée les comptes de test de la suite Playwright avec un mot de passe "
        "connu et sans changement forcé. Refuse tout hors DEBUG et hors base onea_e2e_<nombre>."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--mot-de-passe",
            default="",
            help="Mot de passe commun des comptes (à défaut : variable E2E_PASSWORD).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        mot_de_passe = str(options["mot_de_passe"] or os.environ.get("E2E_PASSWORD", ""))
        base = str(connection.settings_dict.get("NAME") or "")
        if not settings.DEBUG:
            raise CommandError("Refus : commande réservée aux tests e2e (DEBUG désactivé).")
        if not NOM_BASE_E2E.match(base):
            raise CommandError(
                f"Refus : la base « {base} » ne correspond pas à ^onea_e2e_[0-9]+$ "
                "(aucune écriture faite)."
            )
        if not mot_de_passe:
            raise CommandError("Mot de passe manquant : --mot-de-passe ou variable E2E_PASSWORD.")
        with transaction.atomic():
            for identifiant, role, direction in COMPTES_E2E:
                self._poser(identifiant, role, direction, mot_de_passe)
        self.stdout.write(f"{len(COMPTES_E2E)} comptes e2e prêts dans {base}.")

    def _poser(self, identifiant: str, role: Role, direction: str, mot_de_passe: str) -> None:
        user, _ = User.objects.get_or_create(
            username=identifiant,
            defaults={"role": role.value, "origine": OrigineCompte.ADMINISTRATION},
        )
        user.email = f"{identifiant}@onea.test"
        user.first_name = identifiant.capitalize()
        user.last_name = "E2E"
        user.role = role.value
        user.direction_code = direction
        user.is_active = True
        user.otp_connexion_actif = False
        user.doit_changer_mot_de_passe = False
        user.mot_de_passe_expire_le = None
        user.echecs_connexion = 0
        user.verrouille_jusqu_a = None
        user.set_password(mot_de_passe)
        user.save()
        if identifiant == DELEGUE:
            DelegationGestionComptes.objects.update_or_create(
                user=user,
                defaults={
                    "creer": True,
                    "reinitialiser": True,
                    "roles": True,
                    "desactiver": True,
                },
            )

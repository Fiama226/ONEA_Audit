"""Give a temporary password to every active account that has no usable one.

For the switch from Keycloak: the accounts it used to authenticate (the test accounts of
the shared test site, for instance) have no local password. Each one gets a temporary
password (72 h, to be changed at the first login), printed ONCE on the standard output as
``identifiant<TAB>mot_de_passe``, never logged nor audited (only the account ids and the
count reach the security log). Accounts that already have a password are never touched.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from apps.users.auth_services import generer_mot_de_passe_temporaire, logger_securite
from apps.users.models import User
from apps.users.services import _action_auditee, _poser_mot_de_passe_temporaire

# Value of `additional_data["action"]` on the audit entries written by this command.
ACTION_MOT_DE_PASSE_TEMPORAIRE = "mot_de_passe_temporaire_migration"


def _sans_mot_de_passe() -> list[int]:
    """Active accounts whose password is unusable (or empty), by username."""
    return [
        u.pk
        for u in User.objects.filter(is_active=True).only("pk", "password").order_by("username")
        if not u.has_usable_password()
    ]


class Command(BaseCommand):
    help = (
        "Donne un mot de passe temporaire (72 h, à changer à la première connexion) à chaque "
        "compte actif sans mot de passe utilisable, et l'affiche une seule fois "
        "(identifiant<TAB>mot de passe). Les autres comptes ne sont pas modifiés."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--a-blanc",
            action="store_true",
            help="Lister les comptes concernés sans rien modifier.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        ids = _sans_mot_de_passe()
        if options["a_blanc"]:
            for username in (
                User.objects.filter(pk__in=ids)
                .order_by("username")
                .values_list("username", flat=True)
            ):
                self.stdout.write(username)
            self.stderr.write(f"{len(ids)} compte(s) concerné(s) ; aucune modification.")
            return
        donnes: list[int] = []
        for compte_id in ids:
            mot_de_passe = generer_mot_de_passe_temporaire()
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=compte_id)
                # Re-checked under the lock: a password set meanwhile is never overwritten.
                if not user.is_active or user.has_usable_password():
                    continue
                champs = _poser_mot_de_passe_temporaire(user, mot_de_passe, timezone.now())
                with _action_auditee(user, ACTION_MOT_DE_PASSE_TEMPORAIRE):
                    user.save(update_fields=champs)
            donnes.append(user.pk)
            self.stdout.write(f"{user.username}\t{mot_de_passe}")
        logger_securite.info(
            "Mots de passe temporaires donnés aux comptes sans mot de passe : nombre=%s comptes=%s",
            len(donnes),
            ",".join(str(pk) for pk in donnes),
        )
        # Kept off stdout so that the output stays a clean identifiant<TAB>password list.
        self.stderr.write(
            f"{len(donnes)} mot(s) de passe temporaire(s) donné(s), affiché(s) une seule fois ; "
            "valables 72 h, à changer à la première connexion."
        )

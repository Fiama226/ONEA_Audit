"""Give a temporary password to every active account that has no usable one.

For the switch to the in-app login: the accounts the former identity provider used to
authenticate (the test accounts of the shared test site, for instance) have no local
password. Each one gets a temporary password (72 h, to be changed at the first login),
printed ONCE on the standard output as ``identifiant<TAB>mot_de_passe``, never logged nor
audited (only the account ids and the count reach the security log). Accounts that already
have a password are never touched.

Django staff and superuser accounts are left out: a password printed in a batch must never
open the Django admin. They are only listed on the standard error; give them a password
with ``creer_administrateur`` or ``changepassword``.
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


def _sans_mot_de_passe(user: User) -> bool:
    """No password that can ever match: marked unusable, or an empty field."""
    return not user.password or not user.has_usable_password()


def _comptes_sans_mot_de_passe() -> tuple[list[int], list[str]]:
    """Active accounts without a password, by username: (ids to fix, privileged usernames).

    The privileged ones (``is_staff`` or ``is_superuser``) are reported, never changed.
    """
    ids: list[int] = []
    privilegies: list[str] = []
    comptes = (
        User.objects.filter(is_active=True)
        .only("pk", "username", "password", "is_staff", "is_superuser")
        .order_by("username")
    )
    for compte in comptes:
        if not _sans_mot_de_passe(compte):
            continue
        if compte.is_staff or compte.is_superuser:
            privilegies.append(compte.username)
        else:
            ids.append(compte.pk)
    return ids, privilegies


class Command(BaseCommand):
    help = (
        "Donne un mot de passe temporaire (72 h, à changer à la première connexion) à chaque "
        "compte actif sans mot de passe utilisable, et l'affiche une seule fois "
        "(identifiant<TAB>mot de passe). Les autres comptes ne sont pas modifiés ; les comptes "
        "is_staff ou is_superuser sont seulement signalés (sortie d'erreur)."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--a-blanc",
            action="store_true",
            help="Lister les comptes concernés sans rien modifier.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        ids, privilegies = _comptes_sans_mot_de_passe()
        for username in privilegies:
            self.stderr.write(
                f"Compte d'administration Django ignoré (is_staff ou is_superuser) : {username} ; "
                "utilisez creer_administrateur ou changepassword."
            )
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
                user = User.objects.select_for_update(no_key=True).get(pk=compte_id)
                # Re-checked under the lock: a password set (or a privilege given) meanwhile
                # is never overwritten.
                if (
                    not user.is_active
                    or user.is_staff
                    or user.is_superuser
                    or not _sans_mot_de_passe(user)
                ):
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

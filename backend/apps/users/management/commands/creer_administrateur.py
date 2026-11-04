"""Bootstrap: create the initial administrator, or give it a new temporary password.

Non-interactive (deployment scripts, recovery). The temporary password is printed ONCE on
the standard output and never logged nor audited; it lasts 72 h and must be changed at the
first login. On an existing identifier (case-insensitive) the command only resets: new
temporary password, account unlocked, pending one-time codes dropped, every session closed.
It refuses an existing account that is not an ADMIN (it never changes a role) and a
disabled one (reactivate it in the application first).
"""

from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.users.auth_services import (
    envoi_courriel_actif,
    generer_mot_de_passe_temporaire,
    logger_securite,
    terminer_sessions,
)
from apps.users.models import CodeOtp, OrigineCompte, Role, User
from apps.users.services import (
    COURRIEL_INVALIDE,
    CREATION_CONCURRENTE,
    _action_auditee,
    _poser_mot_de_passe_temporaire,
    _valeurs_creation,
    _verifier_disponibilite,
)

# Value of `additional_data["action"]` on the audit entries written by this command.
ACTION_AMORCAGE = "amorcage_administrateur"
COURRIEL_REQUIS = "La création d'un administrateur exige --courriel ADRESSE."


def _erreur(exc: RegleMetierError) -> CommandError:
    messages = [m for erreurs in exc.errors.values() for m in erreurs]
    return CommandError(" ".join(messages) or exc.message)


class Command(BaseCommand):
    help = (
        "Crée l'administrateur initial (rôle ADMIN) ou, s'il existe, lui donne un nouveau mot "
        "de passe temporaire. Le mot de passe est affiché une seule fois."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--identifiant", required=True, help="Identifiant de connexion.")
        parser.add_argument(
            "--courriel",
            default="",
            help="Adresse de courriel (obligatoire à la création, ignorée ensuite).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        identifiant = str(options["identifiant"]).strip()
        courriel = str(options["courriel"] or "").strip()
        mot_de_passe = generer_mot_de_passe_temporaire()
        existant = (
            User.objects.filter(username__iexact=identifiant).first() if identifiant else None
        )
        if existant is None:
            compte = self._creer(identifiant, courriel, mot_de_passe)
            self.stdout.write(f"Administrateur « {compte.username} » créé.")
        else:
            compte, sessions = self._reinitialiser(existant, mot_de_passe)
            self.stdout.write(
                f"Mot de passe de l'administrateur « {compte.username} » réinitialisé : compte "
                f"déverrouillé, {sessions} session(s) fermée(s)."
            )
            if courriel and courriel.lower() != compte.email.lower():
                self.stdout.write(
                    self.style.WARNING(
                        "L'adresse --courriel diffère de celle du compte : elle n'est pas "
                        "modifiée (changez-la dans l'application)."
                    )
                )
            if compte.otp_connexion_actif and not envoi_courriel_actif():
                self.stdout.write(
                    self.style.WARNING(
                        "Le code de connexion par courriel est actif sur ce compte, mais "
                        "l'envoi de courriels n'est pas configuré."
                    )
                )
        self.stdout.write(f"Mot de passe temporaire : {mot_de_passe}")
        self.stdout.write(
            "Affiché une seule fois ; valable 72 h ; à changer à la première connexion."
        )

    def _creer(self, identifiant: str, courriel: str, mot_de_passe: str) -> User:
        try:
            valeurs = _valeurs_creation(
                {"username": identifiant, "email": courriel, "role": Role.ADMIN.value}
            )
        except RegleMetierError as exc:
            raise _erreur(exc) from exc
        if not courriel:
            raise CommandError(COURRIEL_REQUIS)
        try:
            validate_email(valeurs["email"])
        except ValidationError as exc:
            raise CommandError(COURRIEL_INVALIDE) from exc
        try:
            with transaction.atomic():
                _verifier_disponibilite(valeurs)
                user = User(**valeurs, origine=OrigineCompte.ADMINISTRATION, is_active=True)
                _poser_mot_de_passe_temporaire(user, mot_de_passe, timezone.now())
                with _action_auditee(user, ACTION_AMORCAGE):
                    user.save()
        except RegleMetierError as exc:
            raise _erreur(exc) from exc
        except IntegrityError as exc:
            raise CommandError(CREATION_CONCURRENTE) from exc
        logger_securite.info("Administrateur créé par la commande d'amorçage : compte=%s", user.pk)
        return user

    def _reinitialiser(self, existant: User, mot_de_passe: str) -> tuple[User, int]:
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=existant.pk)
            if user.role != Role.ADMIN:
                raise CommandError(
                    f"« {user.username} » existe mais n'est pas un administrateur : la commande "
                    "ne change pas le rôle d'un compte existant."
                )
            if not user.is_active:
                raise CommandError(
                    f"Le compte « {user.username} » est désactivé : réactivez-le dans "
                    "l'application avant de relancer la commande."
                )
            champs = _poser_mot_de_passe_temporaire(user, mot_de_passe, timezone.now())
            with _action_auditee(user, ACTION_AMORCAGE):
                user.save(update_fields=champs)
            CodeOtp.objects.filter(user=user, utilise_le__isnull=True).delete()
        sessions = terminer_sessions(user.pk)
        logger_securite.info(
            "Mot de passe d'un administrateur réinitialisé par la commande d'amorçage : "
            "compte=%s sessions_terminees=%s",
            user.pk,
            sessions,
        )
        return user, sessions

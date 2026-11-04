"""Bootstrap: create the initial administrator, or give it a new temporary password.

Non-interactive (deployment scripts, recovery). The temporary password is printed ONCE on
the standard output and never logged nor audited; it lasts 72 h and must be changed at the
first login. On an existing identifier (case-insensitive) the command only resets: new
temporary password, account unlocked, pending one-time codes dropped, every session closed.
The login code (OTP) is turned off too when no email can go out (it would lock the admin
out), or on request with --desactiver-otp; that change is audited and security-logged.
It refuses an existing account that is not an ADMIN (it never changes a role), a disabled
one (reactivate it in the application first) and an identifier matching several accounts.
"""

from typing import Any

from django.contrib.auth.validators import UnicodeUsernameValidator
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
IDENTIFIANT_INVALIDE = (
    "Identifiant invalide : 150 caractères au plus, lettres, chiffres et . + - _ uniquement."
)
IDENTIFIANT_AMBIGU = (
    "Plusieurs comptes correspondent à « {identifiant} » (casse ignorée) : "
    "corrigez les identifiants dans l'application avant de relancer la commande."
)
_validateur_identifiant = UnicodeUsernameValidator()
IDENTIFIANT_MAX = 150


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
        parser.add_argument(
            "--desactiver-otp",
            action="store_true",
            help=(
                "À la réinitialisation : désactiver aussi le code de connexion par courriel "
                "(fait d'office quand l'envoi de courriels n'est pas configuré)."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        identifiant = str(options["identifiant"]).strip()
        courriel = str(options["courriel"] or "").strip()
        mot_de_passe = generer_mot_de_passe_temporaire()
        existants = (
            list(User.objects.filter(username__iexact=identifiant)[:2]) if identifiant else []
        )
        if len(existants) > 1:
            raise CommandError(IDENTIFIANT_AMBIGU.format(identifiant=identifiant))
        if not existants:
            compte = self._creer(identifiant, courriel, mot_de_passe)
            self.stdout.write(f"Administrateur « {compte.username} » créé.")
        else:
            compte, sessions, otp_coupe = self._reinitialiser(
                existants[0], mot_de_passe, desactiver_otp=options["desactiver_otp"]
            )
            self.stdout.write(
                f"Mot de passe de l'administrateur « {compte.username} » réinitialisé : compte "
                f"déverrouillé, {sessions} session(s) fermée(s)."
            )
            if otp_coupe:
                self.stdout.write("Code de connexion par courriel désactivé sur ce compte.")
            if courriel and courriel.lower() != compte.email.lower():
                self.stdout.write(
                    self.style.WARNING(
                        "L'adresse --courriel diffère de celle du compte : elle n'est pas "
                        "modifiée (changez-la dans l'application)."
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
        if len(identifiant) > IDENTIFIANT_MAX:
            raise CommandError(IDENTIFIANT_INVALIDE)
        try:
            _validateur_identifiant(identifiant)
        except ValidationError as exc:
            raise CommandError(IDENTIFIANT_INVALIDE) from exc
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

    def _reinitialiser(
        self, existant: User, mot_de_passe: str, *, desactiver_otp: bool
    ) -> tuple[User, int, bool]:
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
            # Without email the login code can never arrive: the admin would stay locked out.
            otp_coupe = user.otp_connexion_actif and (desactiver_otp or not envoi_courriel_actif())
            if otp_coupe:
                user.otp_connexion_actif = False
                champs.append("otp_connexion_actif")
            with _action_auditee(user, ACTION_AMORCAGE):
                user.save(update_fields=champs)
            CodeOtp.objects.filter(user=user, utilise_le__isnull=True).delete()
        sessions = terminer_sessions(user.pk)
        logger_securite.info(
            "Mot de passe d'un administrateur réinitialisé par la commande d'amorçage : "
            "compte=%s sessions_terminees=%s otp_desactive=%s",
            user.pk,
            sessions,
            otp_coupe,
        )
        return user, sessions, otp_coupe

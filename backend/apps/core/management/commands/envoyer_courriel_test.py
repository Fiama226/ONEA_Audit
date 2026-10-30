"""Envoie un message d'essai pour valider la configuration SMTP (aucun secret affiché)."""

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.core.validators import validate_email


class Command(BaseCommand):
    help = "Envoie un courriel d'essai à un destinataire pour valider la configuration SMTP."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("destinataire", help="Adresse du destinataire de l'essai.")

    def handle(self, *args: Any, **options: Any) -> None:
        destinataire: str = options["destinataire"]
        try:
            validate_email(destinataire)
        except ValidationError as exc:
            raise CommandError(f"Adresse de destinataire invalide : {destinataire}") from exc

        hote = getattr(settings, "EMAIL_HOST", "") or "(aucun)"
        port = getattr(settings, "EMAIL_PORT", "")
        mode = (
            "TLS implicite"
            if getattr(settings, "EMAIL_USE_SSL", False)
            else "STARTTLS"
            if getattr(settings, "EMAIL_USE_TLS", False)
            else "sans chiffrement"
        )
        message = EmailMessage(
            subject="ONEA Audit interne : courriel d'essai",
            body=(
                "Ceci est un courriel d'essai envoyé par la commande envoyer_courriel_test.\n"
                "Si vous le lisez, la configuration SMTP de l'application fonctionne.\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destinataire],
        )
        try:
            message.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001 - le détail (type seul) évite toute fuite
            raise CommandError(
                f"Échec de l'envoi via {hote}:{port} ({mode}) : {type(exc).__name__}. "
                "Vérifier EMAIL_URL, le fichier email_password et l'accès réseau au relais."
            ) from exc
        self.stdout.write(
            f"Courriel d'essai envoyé à {destinataire} "
            f"(relais {hote}:{port}, {mode}, expéditeur {settings.DEFAULT_FROM_EMAIL})."
        )

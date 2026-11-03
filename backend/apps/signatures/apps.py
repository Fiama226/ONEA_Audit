from django.apps import AppConfig


class SignaturesConfig(AppConfig):
    name = "apps.signatures"
    label = "signatures"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import Confirmation, ParametreSignature, SignatureElectronique

        register(Confirmation)
        register(ParametreSignature)
        register(SignatureElectronique)

        from django.conf import settings

        if getattr(settings, "SIGNATURE_ELECTRONIQUE_ACTIVE", False):
            from .electronique import enregistrer_signataire_electronique
            from .pades import SignatairePades

            enregistrer_signataire_electronique(SignatairePades())

from typing import Any

from django.contrib.admin.forms import AdminAuthenticationForm

from apps.core.reseau import adresse_client

from .auth_services import Etape, authentifier
from .auth_throttles import (
    EchecsConnexionParIpThrottle,
    RefusParIpThrottle,
    autoriser_connexion_hors_api,
)


class ConnexionAdminForm(AdminAuthenticationForm):
    """Django admin login through the same checks as the API login.

    Lockout, failure counting, disabled account and temporary-password expiry come from
    ``authentifier``. An account that needs a second step (OTP) or a password change is
    refused here: it must sign in through the application. The resulting session carries no
    API marker, so it opens the admin pages only, never the API.

    The per-address limits of the API login apply too (AUTH-06): its request quota and its
    cap on failures, checked before any password hash; a refusal looks like a wrong password.
    """

    def clean(self) -> dict[str, Any]:
        identifiant = self.cleaned_data.get("username")
        mot_de_passe = self.cleaned_data.get("password")
        if identifiant is not None and mot_de_passe:
            if self.request is not None and not autoriser_connexion_hors_api(self.request):
                raise self.get_invalid_login_error()
            adresse = adresse_client(self.request) if self.request is not None else None
            resultat = authentifier(identifiant, mot_de_passe, adresse=adresse)
            if resultat.etape is None or resultat.user is None:
                if self.request is not None:
                    RefusParIpThrottle().enregistrer_echec(self.request)
                    EchecsConnexionParIpThrottle().compter_refus(
                        self.request,
                        resultat.comptage,
                        compte_id=resultat.compte_id,
                        identifiant=identifiant,
                    )
                raise self.get_invalid_login_error()
            if resultat.etape is not Etape.OK:
                raise self.get_invalid_login_error()
            self.user_cache = resultat.user
            self.confirm_login_allowed(resultat.user)
        return self.cleaned_data

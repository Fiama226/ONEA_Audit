from typing import Any

from django.contrib.admin.forms import AdminAuthenticationForm

from apps.core.reseau import adresse_client

from .auth_services import Etape, authentifier


class ConnexionAdminForm(AdminAuthenticationForm):
    """Django admin login through the same checks as the API login.

    Lockout, failure counting, disabled account and temporary-password expiry come from
    ``authentifier``. An account that needs a second step (OTP) or a password change is
    refused here: it must sign in through the application. The resulting session carries no
    API marker, so it opens the admin pages only, never the API.
    """

    def clean(self) -> dict[str, Any]:
        identifiant = self.cleaned_data.get("username")
        mot_de_passe = self.cleaned_data.get("password")
        if identifiant is not None and mot_de_passe:
            adresse = adresse_client(self.request) if self.request is not None else None
            resultat = authentifier(identifiant, mot_de_passe, adresse=adresse)
            if resultat.etape is not Etape.OK or resultat.user is None:
                raise self.get_invalid_login_error()
            self.user_cache = resultat.user
            self.confirm_login_allowed(resultat.user)
        return self.cleaned_data

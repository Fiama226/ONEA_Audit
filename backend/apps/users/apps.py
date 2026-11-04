from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "apps.users"
    label = "users"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from auditlog.registry import auditlog

        from .models import DelegationGestionComptes, User

        # Never log credentials, login timestamps or technical retry counters.
        auditlog.register(
            User,
            exclude_fields=[
                "password",
                "last_login",
                "keycloak_sync_le",
                "keycloak_sync_tentatives",
                "echecs_connexion",
            ],
        )
        auditlog.register(DelegationGestionComptes)

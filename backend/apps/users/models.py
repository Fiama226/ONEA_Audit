from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrateur"
    RAI = "RAI", "Responsable de l'audit interne"
    AUDITEUR = "AUDITEUR", "Auditeur interne"
    AUDITE = "AUDITE", "Audité"
    DG = "DG", "Direction générale"


class ActionTutoriel(models.TextChoices):
    TERMINER = "terminer", "Terminer"
    IGNORER = "ignorer", "Ignorer"
    REINITIALISER = "reinitialiser", "Réinitialiser"


class OrigineCompte(models.TextChoices):
    CONNEXION = "CONNEXION", "Première connexion"
    ANNUAIRE = "ANNUAIRE", "Import annuaire"
    CSV = "CSV", "Import CSV"
    ADMINISTRATION = "ADMINISTRATION", "Création par l'administration"


class KeycloakSyncStatut(models.TextChoices):
    A_JOUR = "A_JOUR", "À jour"
    EN_ATTENTE = "EN_ATTENTE", "En attente"
    ECHEC = "ECHEC", "Échec"


class User(AbstractUser):
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.AUDITE)
    keycloak_id = models.UUIDField(null=True, blank=True, unique=True)
    matricule = models.CharField(max_length=32, blank=True)
    fonction = models.CharField(max_length=128, blank=True)
    direction_code = models.CharField(max_length=16, blank=True)

    profil_gere_localement = models.BooleanField(default=False)

    desactive_le = models.DateTimeField(null=True, blank=True)
    desactive_par = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    motif_desactivation = models.TextField(blank=True)

    origine = models.CharField(
        max_length=16, choices=OrigineCompte.choices, default=OrigineCompte.CONNEXION
    )
    premiere_connexion_le = models.DateTimeField(null=True, blank=True)
    role_provisoire = models.BooleanField(default=False)

    keycloak_sync_statut = models.CharField(
        max_length=16, choices=KeycloakSyncStatut.choices, default=KeycloakSyncStatut.A_JOUR
    )
    keycloak_sync_erreur = models.TextField(blank=True)
    keycloak_sync_le = models.DateTimeField(null=True, blank=True)
    keycloak_sync_tentatives = models.PositiveIntegerField(default=0)
    # Permanent failure (404, refused): no automatic retry, manual relaunch only.
    keycloak_sync_manuel = models.BooleanField(default=False)

    # Tutoriel d'accueil guidé : dernière version du parcours vue ou ignorée (null = jamais).
    tutoriel_version_vue = models.PositiveIntegerField(null=True, blank=True)
    tutoriel_termine_le = models.DateTimeField(null=True, blank=True)

    # In-app authentication (replaces Keycloak; legacy fields above are removed later).
    doit_changer_mot_de_passe = models.BooleanField(default=False)
    mot_de_passe_expire_le = models.DateTimeField(null=True, blank=True)
    echecs_connexion = models.PositiveIntegerField(default=0)
    verrouille_jusqu_a = models.DateTimeField(null=True, blank=True)
    otp_connexion_actif = models.BooleanField(default=False)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["matricule"],
                condition=~Q(matricule=""),
                name="users_matricule_unique_non_vide",
            )
        ]

    @property
    def nom_complet(self) -> str:
        return self.get_full_name() or self.username

    @property
    def en_attente_connexion(self) -> bool:
        return self.premiere_connexion_le is None

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

    # Business action carried by the next save into its audit entry (``additional_data``).
    # Set by the account services only, never a secret. Not a database field.
    action_audit: str | None = None

    def get_additional_data(self) -> dict[str, str] | None:
        """Called by auditlog when it writes the entry of a save."""
        return {"action": self.action_audit} if self.action_audit else None


class ObjetOtp(models.TextChoices):
    RESET = "RESET", "Réinitialisation du mot de passe"
    LOGIN = "LOGIN", "Connexion"


class CodeOtp(models.Model):
    """One-time code, stored hashed. A transient credential: never soft-deleted.

    At most one *active* (unused) code per (user, objet); used codes are kept as history.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    objet = models.CharField(max_length=8, choices=ObjetOtp.choices)
    code_hash = models.CharField(max_length=255)
    expire_le = models.DateTimeField()
    essais = models.PositiveSmallIntegerField(default=0)
    utilise_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "objet"],
                condition=Q(utilise_le__isnull=True),
                name="users_codeotp_un_actif_par_objet",
            )
        ]

    def __str__(self) -> str:
        return f"{self.objet} #{self.user_id}"


class DelegationGestionComptes(models.Model):
    """Account-management rights delegated by an admin to a non-admin user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="delegation_comptes"
    )
    creer = models.BooleanField(default=False)
    reinitialiser = models.BooleanField(default=False)
    roles = models.BooleanField(default=False)
    desactiver = models.BooleanField(default=False)
    accorde_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    accorde_le = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Délégation #{self.user_id}"

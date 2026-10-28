from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrateur"
    RAI = "RAI", "Responsable de l'audit interne"
    AUDITEUR = "AUDITEUR", "Auditeur interne"
    AUDITE = "AUDITE", "Audité"
    DG = "DG", "Direction générale"


class OrigineCompte(models.TextChoices):
    CONNEXION = "CONNEXION", "Première connexion"
    ANNUAIRE = "ANNUAIRE", "Import annuaire"
    CSV = "CSV", "Import CSV"


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

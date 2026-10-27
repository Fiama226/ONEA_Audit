from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrateur"
    RAI = "RAI", "Responsable de l'audit interne"
    AUDITEUR = "AUDITEUR", "Auditeur interne"
    AUDITE = "AUDITE", "Audité"
    DG = "DG", "Direction générale"


class User(AbstractUser):
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.AUDITE)
    keycloak_id = models.UUIDField(null=True, blank=True, unique=True)
    matricule = models.CharField(max_length=32, blank=True)
    fonction = models.CharField(max_length=128, blank=True)
    direction_code = models.CharField(max_length=16, blank=True)

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

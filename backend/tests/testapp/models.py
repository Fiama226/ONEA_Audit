from django.db import models

from apps.core.models import BaseModel


class Exemple(BaseModel):
    """Concrete model used only to exercise the abstract BaseModel in tests."""

    nom = models.CharField(max_length=64, blank=True)

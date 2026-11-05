from typing import TYPE_CHECKING, Any

from django.db import models

from apps.core.exceptions import RegleMetierError
from apps.core.models import BaseModel

if TYPE_CHECKING:
    from apps.users.models import User


class RegleGouvernance(BaseModel):
    """Règle de gouvernance paramétrée par l'ADMIN (clé, valeur JSON) ; jamais supprimée.

    Absence de ligne = valeur par défaut de la règle (`regles_gouvernance.DEFAUTS`). Chaque
    changement est tracé dans le journal d'audit : qui, quand, valeur avant et après ; le motif
    et le caractère d'assouplissement vont dans `additional_data` de l'entrée.
    """

    cle = models.CharField("clé", max_length=60)
    valeur = models.JSONField("valeur")
    motif = models.TextField("motif du dernier changement", blank=True)

    class Meta:
        verbose_name = "règle de gouvernance"
        verbose_name_plural = "règles de gouvernance"
        ordering = ["cle"]
        constraints = [
            models.UniqueConstraint(
                fields=["cle"],
                condition=models.Q(deleted_at__isnull=True),
                name="regle_gouvernance_cle_unique",
            )
        ]

    # Données d'audit portées par la prochaine sauvegarde (jamais en base).
    audit_motif: str = ""
    audit_affaiblissement: bool = False

    def __str__(self) -> str:
        return self.cle

    def get_additional_data(self) -> dict[str, Any]:
        """Lu par auditlog à l'écriture de l'entrée."""
        return {
            "action": "regle_gouvernance",
            "motif": self.audit_motif,
            "affaiblissement": self.audit_affaiblissement,
        }

    def soft_delete(self, by: "User") -> None:
        raise RegleMetierError("Une règle de gouvernance ne peut pas être supprimée.")

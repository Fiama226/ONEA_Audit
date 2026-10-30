"""Adaptateur du lot 7 : SEUL module du lot 8 qui importe la communication et le plan d'actions.

Noms réels relevés en T1 étape 0 (code fusionné sur `develop`) :

- action : `recommandations.Action` (`mission`, `recommandation`, `libelle`, `indicateur`,
  `responsable` nullable, `echeance` nullable, `deleted_at`) ;
- risque accepté : il n'existe PAS de booléen sur `Recommandation` ; c'est le modèle
  `recommandations.AcceptationRisque` (relation inverse `Recommandation.acceptations`, une
  acceptation active par recommandation). `CHAMP_RISQUE_ACCEPTE` désigne cette relation ;
- diffusion : `communication.Diffusion` (OneToOne `rapport`, `diffusee_le` horodatée), rapport au
  statut `DIFFUSE` ; la mission passe à `RAPPORT_DIFFUSE` dans la même transaction ;
- signal : `communication.signals.rapport_diffuse` (sender `Rapport`, `rapport`, `diffusion`,
  `par`), émis `on_commit` ; la réconciliation horaire de T5 reste le filet ;
- type de document du rapport : `RAPPORT_FINAL` (étape XVIII).
"""

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.dispatch import Signal

    from apps.missions.models import Mission

MODELE_ACTION = "recommandations.Action"
CHAMP_RISQUE_ACCEPTE: str | None = "acceptations"
CODE_DOCUMENT_RAPPORT = "RAPPORT_FINAL"


@dataclass(frozen=True)
class ActionPlan:
    id: Any
    mission_id: Any
    recommandation_id: Any
    libelle: str
    indicateur: str
    responsable_id: int | None
    echeance: date | None


def actions_du_plan(mission: "Mission") -> list[ActionPlan]:
    """Actions actives du plan d'actions de la mission, dans l'ordre de leur numéro."""
    from apps.recommandations.models import Action

    return [
        ActionPlan(
            id=a.pk,
            mission_id=a.mission_id,
            recommandation_id=a.recommandation_id,
            libelle=a.libelle,
            indicateur=a.indicateur,
            responsable_id=a.responsable_id,
            echeance=a.echeance,
        )
        for a in Action.objects.filter(mission=mission).order_by("numero")
    ]


def date_diffusion(mission: "Mission") -> date | None:
    """Date (fuseau de l'application) de la première diffusion du rapport, sinon None."""
    from django.utils import timezone

    from apps.communication.models import Diffusion

    premiere = Diffusion.objects.filter(mission=mission).order_by("diffusee_le").first()
    return None if premiere is None else timezone.localdate(premiere.diffusee_le)


def recommandations_a_risque_accepte(mission: "Mission") -> "QuerySet[Any]":
    """Recommandations de la mission dont le risque est accepté (acceptation active)."""
    from apps.constats.models import Recommandation

    if CHAMP_RISQUE_ACCEPTE is None:
        return Recommandation.objects.none()
    return Recommandation.objects.filter(
        **{
            "mission": mission,
            f"{CHAMP_RISQUE_ACCEPTE}__isnull": False,
            f"{CHAMP_RISQUE_ACCEPTE}__deleted_at__isnull": True,
        }
    ).distinct()


def signal_rapport_diffuse() -> "Signal | None":
    from apps.communication.signals import rapport_diffuse

    return rapport_diffuse

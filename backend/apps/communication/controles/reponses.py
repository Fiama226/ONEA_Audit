"""XVI : réponse de la direction à chaque constat du rapport provisoire, ou délai échu.

Contrôle « réponse de l'audité » (règle de gouvernance, champ `response_or_deadline`) enregistré
par l'application au chargement ; il se tait après une dérogation motivée.
"""

from apps.constats.models import Constat
from apps.missions.models import EtapeMission
from apps.missions.services import aujourd_hui

from ..models import Rapport, ReponseRapport
from ..services.provisoire import _references, provisoire_courant

ETAPE_REPONSES = 16


def controle_reponses_provisoire(etape: EtapeMission) -> list[str]:
    rapport = Rapport.objects.filter(mission_id=etape.mission_id).order_by("-created_at").first()
    provisoire = provisoire_courant(rapport) if rapport is not None else None
    if provisoire is None or aujourd_hui() > provisoire.date_limite_reponses:
        return []
    references = _references(provisoire)
    repondus = set(
        ReponseRapport.objects.filter(provisoire__rapport=rapport).values_list(
            "constat__reference", flat=True
        )
    )
    attendus = Constat.objects.filter(
        mission_id=etape.mission_id, reference__in=references
    ).order_by("numero")
    limite = provisoire.date_limite_reponses.strftime("%d/%m/%Y")
    return [
        f"Le constat {c.reference} attend la réponse de la direction (délai : {limite})."
        for c in attendus
        if c.reference not in repondus
    ]

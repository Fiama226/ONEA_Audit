"""Soumission du rapport au RAI (D9) : instantané figé, étape XVIII terminée (rapport initial)."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import relire
from apps.missions.acces import declaration_levee, est_chef
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import EtapeMission, StatutEtape, StatutMission
from apps.missions.services.etapes import demarrer_etape, terminer_etape
from apps.signatures.services import empreinte
from apps.users.models import User

from ..gardes import STATUTS_REDACTION
from ..models import Rapport, TypeEvenementRapport
from ._ecriture import journaliser, ouvrir_mission, sauver_transition, verrouiller_etape
from .assemblage import assembler

ETAPE_REDACTION = 17
ETAPE_VALIDATION = 18
MSG_DROIT = "Seul le chef de mission peut soumettre le rapport."
MSG_XVII = "Terminez l'étape XVII avant de soumettre le rapport."
MSG_STATUT = "Le rapport n'est pas en rédaction : il ne peut pas être soumis."
MSG_HORS_COMMUNICATION = "La mission n'est pas en phase de communication : rapport non soumis."

CHAMPS_SOUMISSION = [
    "statut",
    "cycle",
    "soumis_par",
    "soumis_le",
    "instantane_soumis",
    "empreinte_soumise",
]


def _terminer_xviii(rapport: Rapport, by: User) -> None:
    etape = EtapeMission.objects.get(mission_id=rapport.mission_id, numero=ETAPE_VALIDATION)
    if etape.statut == StatutEtape.A_FAIRE:
        etape = demarrer_etape(etape, by=by)
    terminer_etape(etape, by=by)


@transaction.atomic
def soumettre_rapport(rapport: Rapport, *, by: User) -> Rapport:
    """Fige l'instantané, passe le rapport à SOUMIS et termine XVIII (rapport initial).

    Un rapport corrigé (D12) ne touche à aucune étape.
    """
    mission = ouvrir_mission(rapport.mission_id)
    if not (est_chef(by, mission) and declaration_levee(by, mission)):
        raise PermissionDenied(MSG_DROIT)
    verrouille = verrouiller_etape(mission.pk, ETAPE_REDACTION)
    rapport = relire(rapport)
    corrige = rapport.corrige_de_id is not None
    attendu = StatutMission.RAPPORT_DIFFUSE if corrige else StatutMission.EN_COMMUNICATION
    if mission.statut != attendu:
        raise RegleMetierError(MSG_HORS_COMMUNICATION)
    if verrouille not in STATUTS_ETAPE_CLOSE:
        raise RegleMetierError(MSG_XVII)
    if rapport.statut not in STATUTS_REDACTION:
        raise RegleMetierError(MSG_STATUT)
    avant = rapport.statut
    instantane = assembler(rapport, provisoire=False)
    rapport.soumettre()
    rapport.cycle += 1
    rapport.soumis_par = by
    rapport.soumis_le = timezone.now()
    rapport.instantane_soumis = instantane
    rapport.empreinte_soumise = empreinte("rapport", instantane)
    sauver_transition(rapport, CHAMPS_SOUMISSION, by=by)
    journaliser(rapport, TypeEvenementRapport.SOUMIS, by=by, avant=avant)
    if not corrige:
        _terminer_xviii(rapport, by)
    return rapport

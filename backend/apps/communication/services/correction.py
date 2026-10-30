"""Rapport corrigé (D12, IFACI XVIII) : remplace un rapport diffusé sans toucher aux étapes."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max

from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer, refuser, relire
from apps.missions.models import StatutMission
from apps.users.models import Role, User

from ..gardes import CHAMPS_REDACTION
from ..models import DestinataireDiffusion, Rapport, StatutRapport, TypeEvenementRapport
from ._ecriture import journaliser, ouvrir_mission, sauver_transition

MSG_RAI = "Seul le responsable de l'audit interne peut émettre un rapport corrigé."
MSG_STATUT = "Seul un rapport diffusé peut être remplacé par un rapport corrigé."
MSG_HORS_PHASE = "La mission n'est pas dans la phase où un rapport corrigé peut être émis."
MSG_MOTIF = "Le motif de la correction est obligatoire."


@transaction.atomic
def emettre_rapport_corrige(rapport: Rapport, *, motif: str, by: User) -> Rapport:
    """Crée le rapport `numero_version + 1` en BROUILLON et remplace le rapport diffusé.

    Les sections sont copiées ; la liste de diffusion est recopiée (sans suivi) et ses
    destinataires initiaux ne pourront pas être retirés. XVIII reste validée et la mission
    reste RAPPORT_DIFFUSE.
    """
    if by.role != Role.RAI:
        raise PermissionDenied(MSG_RAI)
    mission = ouvrir_mission(rapport.mission_id)
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    ancien = relire(rapport)
    if ancien.statut != StatutRapport.DIFFUSE:
        raise RegleMetierError(MSG_STATUT)
    if mission.statut != StatutMission.RAPPORT_DIFFUSE:
        raise RegleMetierError(MSG_HORS_PHASE)

    # L'ancien rapport quitte l'état actif avant la création du nouveau (un seul rapport actif).
    avant = ancien.statut
    ancien.remplacer()
    sauver_transition(ancien, ["statut"], by=by)
    journaliser(ancien, TypeEvenementRapport.CORRIGE, by=by, avant=avant, motif=motif)

    dernier = Rapport.all_objects.filter(mission=mission).aggregate(m=Max("numero_version"))["m"]
    corrige = Rapport(
        mission=mission,
        numero_version=(dernier or 0) + 1,
        corrige_de=ancien,
        motif_correction=motif,
        **{champ: getattr(ancien, champ) for champ in sorted(CHAMPS_REDACTION)},
    )
    enregistrer(corrige, by=by, creation=True)
    journaliser(corrige, TypeEvenementRapport.CREE, by=by, motif=motif)

    for d in DestinataireDiffusion.objects.filter(rapport=ancien).order_by("created_at"):
        copie = DestinataireDiffusion(
            rapport=corrige,
            mission_id=mission.pk,
            utilisateur_id=d.utilisateur_id,
            nom_externe=d.nom_externe,
            qualite=d.qualite,
            categorie=d.categorie,
        )
        enregistrer(copie, by=by, creation=True)
    return corrige

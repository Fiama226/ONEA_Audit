"""Réponses de l'audité aux constats (D11 du plan du lot 6) : ajout seul, confirmées."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer, refuser, relire
from apps.missions.acces import role_dans_mission
from apps.missions.models import RoleMission
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.services import confirmer
from apps.users.models import Role, User

from ..droits import refus_entite
from ..models import Constat, PositionAudite, ReponseAudite, StatutConstat
from ._fenetres import ouvrir_xv

MSG_DROIT = "Seul un audité affecté à la mission peut répondre à ses constats."
MSG_DESACCORD = "Motivez votre désaccord."
MSG_NON_SOUMIS = "Le constat n'a pas encore été soumis : vous ne pouvez pas y répondre."
MSG_VERSION_PERIMEE = "Le constat a changé depuis votre lecture : relisez-le avant de répondre."
MSG_POSITION = "La position doit être Accord ou Désaccord."
_REPONDABLES = (StatutConstat.SOUMIS, StatutConstat.VALIDE)


def texte_reponse(constat: Constat, position: str, *, by: User) -> str:
    """Texte exact confirmé par l'audité (à confirmer avec ONEA)."""
    soumis = constat.soumis_le
    date = timezone.localtime(soumis).strftime("%d/%m/%Y") if soumis else ""
    qui = by.nom_complet + (f", {by.fonction}" if by.fonction else "")
    avis = "en accord" if position == PositionAudite.ACCORD else "en désaccord"
    return (
        f"Je soussigné(e) {qui}, déclare être {avis} avec le constat {constat.reference} "
        f"« {constat.titre} » de la mission {constat.mission.reference}, "
        f"dans sa version soumise le {date}."
    )


def derniere_reponse(constat: Constat) -> ReponseAudite | None:
    """Dernière réponse du cycle courant (fait foi) ; l'historique reste en base."""
    return (
        ReponseAudite.objects.filter(constat=constat, cycle=constat.cycle)
        .order_by("-created_at", "-pk")
        .first()
    )


@transaction.atomic
def repondre(
    constat: Constat,
    *,
    position: str,
    commentaire: str,
    empreinte_soumise: str,
    by: User,
    adresse_ip: str | None = None,
) -> ReponseAudite:
    mission = constat.mission
    if by.role != Role.AUDITE or role_dans_mission(by, mission) != RoleMission.AUDITE:
        raise PermissionDenied(MSG_DROIT)
    mission = ouvrir_xv(mission)
    constat = relire(constat)
    if constat.statut not in _REPONDABLES:
        raise RegleMetierError(MSG_NON_SOUMIS)
    refus = refus_entite(by, constat)
    if refus is not None:
        raise PermissionDenied(refus)
    if empreinte_soumise != constat.empreinte_soumise:
        raise RegleMetierError(MSG_VERSION_PERIMEE, {"empreinte_soumise": [MSG_VERSION_PERIMEE]})
    if position not in PositionAudite.values:
        raise refuser(MSG_POSITION, position=MSG_POSITION)
    commentaire = commentaire.strip()
    if position == PositionAudite.DESACCORD and not commentaire:
        raise refuser(MSG_DESACCORD, commentaire=MSG_DESACCORD)
    confirmation = confirmer(
        type_document=TypeDocumentSignable.REPONSE_CONSTAT,
        objet=constat,
        texte=texte_reponse(constat, position, by=by),
        donnees={
            "constat": str(constat.pk),
            "reference": constat.reference,
            "cycle": constat.cycle,
            "empreinte_soumise": constat.empreinte_soumise,
            "position": position,
            "commentaire": commentaire,
        },
        by=by,
        adresse_ip=adresse_ip,
    )
    reponse = ReponseAudite(
        mission=mission,
        constat=constat,
        auteur=by,
        cycle=constat.cycle,
        position=position,
        commentaire=commentaire,
        confirmation=confirmation,
    )
    enregistrer(reponse, by=by, creation=True)
    return reponse

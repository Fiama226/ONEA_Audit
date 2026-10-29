"""Référentiel d'audit : instantané validé (D3), avis des audités (D10) et synthèse."""

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q

from apps.core.services import enregistrer, refuser
from apps.missions.models import Mission, RisqueMission, RoleMission, StatutEtape
from apps.missions.services.travaux import verrouiller_travaux
from apps.referentiel.models import NiveauRisque
from apps.signatures.models import Confirmation, TypeDocumentSignable
from apps.signatures.services import confirmer, derniere_confirmation
from apps.users.models import Role, User

from ..gardes import statuts_etapes
from ..models import (
    AvisAudite,
    ForceFaiblesse,
    LigneMARC,
    StatutReferentiel,
    TypeAvis,
    TypeForceFaiblesse,
    statut_referentiel,
)

TEXTE_VALIDATION = (
    "Je soussigné(e) {nom_complet}, valide le référentiel d'audit de la mission "
    "{reference} « {titre} » ({n} lignes de la matrice d'analyse des risques et "
    "contrôles), qui servira de référence à l'évaluation du dispositif de contrôle "
    "interne."
)
MSG_AVIS_NON_DIFFUSE = "Le référentiel d'audit n'est pas soumis à l'avis des audités."
MSG_AVIS_COMMENTAIRE = "Un commentaire est obligatoire pour des remarques."
_VI = 6
_V = 5


def _texte(valeur: Any) -> str:
    return str(valeur) if valeur is not None else ""


def instantane_referentiel(mission: Mission) -> dict[str, Any]:
    """Contenu du référentiel d'audit (JSON strict, ordres stables, 4 requêtes)."""
    risques = RisqueMission.objects.filter(mission=mission).select_related("processus")
    lignes = LigneMARC.objects.filter(mission=mission).select_related("objet_auditable")
    forces = ForceFaiblesse.objects.filter(mission=mission)
    avis = AvisAudite.objects.filter(mission=mission).select_related("auteur")
    return {
        "mission": {"reference": mission.reference, "titre": mission.titre},
        "risques": [
            {
                "id": str(r.pk),
                "code": r.code_source,
                "libelle": r.libelle,
                "processus": r.processus.libelle,
                "probabilite": r.probabilite,
                "impact": r.impact,
                "score": r.score,
                "niveau": _texte(r.niveau),
            }
            for r in risques.order_by("created_at", "pk")
        ],
        "lignes_marc": [
            {
                "id": str(ligne.pk),
                "risque_id": str(ligne.risque_id),
                "objet_auditable": ligne.objet_auditable.libelle if ligne.objet_auditable else None,
                "operation": ligne.operation,
                "objectif_controle": ligne.objectif_controle,
                "controle_attendu": ligne.controle_attendu,
                "controle_existant": ligne.controle_existant,
                "composante": _texte(ligne.composante),
                "nature": _texte(ligne.nature),
                "evaluation": _texte(ligne.evaluation),
                "appreciation": ligne.appreciation and _texte(ligne.appreciation.value),
                "cle": ligne.cle,
                "commentaire": ligne.commentaire,
            }
            for ligne in lignes.order_by("ordre", "created_at", "pk")
        ],
        "forces_faiblesses": [
            {
                "type": _texte(ff.type),
                "libelle": ff.libelle,
                "consequence": ff.consequence,
                "ligne_marc_id": str(ff.ligne_marc_id) if ff.ligne_marc_id else None,
            }
            for ff in forces.order_by("ordre", "created_at", "pk")
        ],
        "avis": [
            {
                "auteur": a.auteur.get_full_name() or a.auteur.username,
                "avis": _texte(a.avis),
                "commentaire": a.commentaire,
                "donne_le": a.donne_le.isoformat(),
            }
            for a in avis.order_by("donne_le", "pk")
        ],
    }


@transaction.atomic
def figer_referentiel(mission: Mission, *, by: User) -> Confirmation:
    """Confirmation horodatée portant l'instantané du référentiel (dans la transaction)."""
    donnees = instantane_referentiel(mission)
    texte = TEXTE_VALIDATION.format(
        nom_complet=by.get_full_name() or by.username,
        reference=mission.reference,
        titre=mission.titre,
        n=len(donnees["lignes_marc"]),
    )
    return confirmer(
        type_document=TypeDocumentSignable.VALIDATION_REFERENTIEL,
        objet=mission,
        texte=texte,
        donnees=donnees,
        by=by,
    )


def referentiel_valide(mission: Mission) -> Confirmation | None:
    """Dernière confirmation si l'étape VI est validée, sinon `None`."""
    if statuts_etapes(mission.pk, (_VI,)).get(_VI) != StatutEtape.VALIDEE:
        return None
    return derniere_confirmation(mission, TypeDocumentSignable.VALIDATION_REFERENTIEL)


@transaction.atomic
def deposer_avis(mission: Mission, *, avis: str, commentaire: str, by: User) -> AvisAudite:
    """Avis d'un audité affecté (ajout seul) ; fenêtre : VI démarrée et non validée (D10)."""
    from apps.missions.acces import role_dans_mission

    if by.role != Role.AUDITE or role_dans_mission(by, mission) != RoleMission.AUDITE:
        raise PermissionDenied("Seul un audité affecté à la mission peut donner son avis.")
    mission = verrouiller_travaux(mission)
    statut = statuts_etapes(mission.pk, (_VI,)).get(_VI, StatutEtape.A_FAIRE)
    if statut in (StatutEtape.A_FAIRE, StatutEtape.NON_APPLICABLE):
        raise refuser(MSG_AVIS_NON_DIFFUSE)
    commentaire = commentaire.strip()
    if avis == TypeAvis.REMARQUES and not commentaire:
        raise refuser(MSG_AVIS_COMMENTAIRE, commentaire=MSG_AVIS_COMMENTAIRE)
    objet = AvisAudite(mission=mission, auteur=by, avis=avis, commentaire=commentaire)
    enregistrer(objet, by=by, creation=True)
    return objet


@dataclass
class SyntheseReferentiel:
    statut: StatutReferentiel
    statut_v: str
    statut_vi: str
    nb_lignes: int
    nb_forces: int
    nb_faiblesses: int
    risques_non_couverts: list[str]
    validation: Confirmation | None
    avis: list[AvisAudite]


def synthese_referentiel(mission: Mission) -> SyntheseReferentiel:
    """Vue d'ensemble du référentiel (au plus 6 requêtes)."""
    statuts = statuts_etapes(mission.pk, (_V, _VI))
    statut_v = statuts.get(_V, StatutEtape.A_FAIRE)
    statut_vi = statuts.get(_VI, StatutEtape.A_FAIRE)
    risques = RisqueMission.objects.filter(mission=mission).annotate(
        nb=Count("lignes_marc", filter=Q(lignes_marc__deleted_at__isnull=True))
    )
    lignes = 0
    non_couverts: list[str] = []
    for r in risques.order_by("created_at", "pk"):
        lignes += r.nb
        if r.nb == 0 and r.niveau in (NiveauRisque.MOYEN, NiveauRisque.ELEVE):
            non_couverts.append(r.code_source or f"Nouveau : {r.libelle[:40]}")
    nombres = ForceFaiblesse.objects.filter(mission=mission).aggregate(
        forces=Count("pk", filter=Q(type=TypeForceFaiblesse.FORCE)),
        faiblesses=Count("pk", filter=Q(type=TypeForceFaiblesse.FAIBLESSE)),
    )
    validation = (
        derniere_confirmation(mission, TypeDocumentSignable.VALIDATION_REFERENTIEL)
        if statut_vi == StatutEtape.VALIDEE
        else None
    )
    avis = list(
        AvisAudite.objects.filter(mission=mission)
        .select_related("auteur")
        .order_by("donne_le", "pk")
    )
    return SyntheseReferentiel(
        statut=statut_referentiel(statut_vi),
        statut_v=statut_v,
        statut_vi=statut_vi,
        nb_lignes=lignes,
        nb_forces=nombres["forces"],
        nb_faiblesses=nombres["faiblesses"],
        risques_non_couverts=non_couverts,
        validation=validation,
        avis=avis,
    )

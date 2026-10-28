"""Déclarations d'indépendance (D9)."""

from django.db import transaction
from django.utils import timezone

from apps.core.services import enregistrer, refuser, relire
from apps.signatures.models import Confirmation, TypeDocumentSignable
from apps.signatures.services import confirmer, derniere_confirmation
from apps.users.models import User

from ..gardes import verrouiller_mission
from ..models import DeclarationIndependance, StatutDeclaration, StatutMission

MSG_AUTRE = "Seul l'auditeur concerné peut confirmer sa déclaration."
MSG_DEJA_CONFIRMEE = "Cette déclaration est déjà confirmée."
MSG_DEJA_DECLAREE = (
    "Votre situation est déjà déclarée : le Responsable de l'Audit Interne doit l'arbitrer."
)
MSG_BROUILLON = "La mission n'est pas encore planifiée : la déclaration ne peut pas être confirmée."

_TEXTE = (
    "Je soussigné(e) {nom_complet}, affecté(e) à la mission {reference} « {titre} » en qualité "
    "de {role_mission}, déclare n'avoir, à ma connaissance, aucun conflit d'intérêts ni aucune "
    "relation personnelle, professionnelle ou financière avec les entités auditées ({entites}), "
    "ni avoir exercé de responsabilité opérationnelle sur les activités auditées au cours des "
    "douze derniers mois, de nature à porter atteinte à mon objectivité (Normes internationales "
    "d'audit interne, principe 2). Je m'engage à signaler sans délai au Responsable de l'Audit "
    "Interne toute situation nouvelle de cette nature."
)


def nom_complet(user: User) -> str:
    return user.get_full_name() or user.username


def texte_declaration(declaration: DeclarationIndependance) -> str:
    affectation = declaration.affectation
    mission = affectation.mission
    entites = ", ".join(mission.entites.order_by("code").values_list("libelle", flat=True))
    return _TEXTE.format(
        nom_complet=nom_complet(affectation.utilisateur),
        reference=mission.reference,
        titre=mission.titre,
        role_mission=affectation.get_role_mission_display().lower(),
        entites=entites,
    )


def confirmation_de(declaration: DeclarationIndependance) -> Confirmation | None:
    return derniere_confirmation(declaration, TypeDocumentSignable.DECLARATION_INDEPENDANCE)


@transaction.atomic
def confirmer_declaration(
    declaration: DeclarationIndependance,
    *,
    by: User,
    conflit: bool = False,
    description_conflit: str = "",
    adresse_ip: str | None = None,
) -> DeclarationIndependance:
    mission = verrouiller_mission(declaration.affectation.mission_id)
    declaration = relire(declaration)
    affectation = declaration.affectation
    if affectation.utilisateur_id != by.pk:
        raise refuser(MSG_AUTRE, utilisateur=MSG_AUTRE)
    if declaration.statut == StatutDeclaration.CONFIRMEE:
        raise refuser(MSG_DEJA_CONFIRMEE, statut=MSG_DEJA_CONFIRMEE)
    if declaration.statut == StatutDeclaration.CONFLIT_DECLARE:
        raise refuser(MSG_DEJA_DECLAREE, statut=MSG_DEJA_DECLAREE)
    if mission.statut == StatutMission.BROUILLON:
        raise refuser(MSG_BROUILLON, statut=MSG_BROUILLON)
    description = description_conflit.strip()
    if conflit and not description:
        msg = "Décrivez la situation qui pourrait porter atteinte à votre objectivité."
        raise refuser(msg, description_conflit=msg)
    if not conflit:
        description = ""

    texte = texte_declaration(declaration)
    if conflit:
        texte = f"{texte}\n\nSituation déclarée : {description}"
    confirmer(
        type_document=TypeDocumentSignable.DECLARATION_INDEPENDANCE,
        objet=declaration,
        texte=texte,
        donnees={
            "mission": str(mission.pk),
            "reference": mission.reference,
            "role_mission": affectation.role_mission,
            "conflit": conflit,
            "description_conflit": description,
        },
        by=by,
        adresse_ip=adresse_ip,
    )
    declaration.statut = (
        StatutDeclaration.CONFLIT_DECLARE if conflit else StatutDeclaration.CONFIRMEE
    )
    declaration.description_conflit = description
    enregistrer(declaration, by=by)
    return declaration


@transaction.atomic
def arbitrer_conflit(
    declaration: DeclarationIndependance, *, justification: str, by: User
) -> DeclarationIndependance:
    verrouiller_mission(declaration.affectation.mission_id)
    declaration = relire(declaration)
    if declaration.statut != StatutDeclaration.CONFLIT_DECLARE or declaration.arbitre_le:
        msg = "Cette déclaration ne comporte aucune situation à arbitrer."
        raise refuser(msg, statut=msg)
    if not justification.strip():
        msg = "La justification est obligatoire."
        raise refuser(msg, justification=msg)
    declaration.arbitrage_justification = justification.strip()
    declaration.arbitre_par = by
    declaration.arbitre_le = timezone.now()
    enregistrer(declaration, by=by)
    return declaration

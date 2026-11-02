"""Diffusion du rapport validé (D11) : liste de diffusion, diffusion, suivi des destinataires."""

import logging
from datetime import date, datetime, time
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer, refuser, relire
from apps.core.tasks import send_mail_task
from apps.documents.models import StatutPdf
from apps.missions.exceptions import MissionFigeeError
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import (
    AffectationMission,
    EtapeMission,
    RoleMission,
    StatutEtape,
    StatutMission,
)
from apps.missions.services import FUSEAU_ONEA, aujourd_hui
from apps.missions.services.missions import MSG_DIFFUSION, marquer_rapport_diffuse
from apps.signatures.electronique import signataire_electronique
from apps.signatures.models import ModeSignatureParametre
from apps.signatures.parametres import MODES_ELECTRONIQUES
from apps.signatures.services import empreinte, verifier
from apps.users.models import Role, User

from .. import signals
from ..exceptions import MSG_DESTINATAIRES_FIGES
from ..gardes import STATUTS_LISTE_FIGEE
from ..models import (
    CategorieDestinataire,
    DestinataireDiffusion,
    Diffusion,
    Rapport,
    StatutRapport,
    TypeEvenementRapport,
)
from ._ecriture import journaliser, ouvrir_mission, sauver_transition, verrouiller_etape
from ._versions import version_finale, version_note

logger = logging.getLogger(__name__)

ETAPE_VALIDATION = 18
MSG_RAI = "Seul le responsable de l'audit interne peut gérer la diffusion du rapport."
MSG_NON_VALIDE = "Seul un rapport validé peut être diffusé."
MSG_HORS_PHASE = "La mission n'est pas dans la phase où ce rapport peut être diffusé."
MSG_VERSION = "Le rapport final n'est pas encore généré : patientez ou relancez la génération."
MSG_SIGNATURE = "Le rapport doit être signé électroniquement avant diffusion."
MSG_SANS_DESTINATAIRE = "Ajoutez au moins un destinataire avant de diffuser le rapport."
MSG_INTEGRITE = (
    "L'intégrité du rapport validé n'est pas vérifiée : le rapport ne peut pas être diffusé."
)
MSG_DIFFUSE_SEUL = "Le rapport n'est pas diffusé."
MSG_PAS_DESTINATAIRE = "Vous n'êtes pas destinataire de ce rapport."
MSG_EXTERNE_SEUL = "Seul un destinataire externe peut être remis hors plateforme."
MSG_RECOPIE = (
    "Ce destinataire figure dans la liste du rapport remplacé : il ne peut pas être retiré."
)
MSG_CIBLE = "Indiquez un utilisateur de la plateforme ou un destinataire externe, pas les deux."
MSG_DATE_REMISE = "La date de remise doit se situer entre la diffusion et aujourd'hui."

CHAMPS_MODIFIABLES = ("categorie", "qualite", "nom_externe")


def _exiger_rai(by: User) -> None:
    if by.role != Role.RAI:
        raise PermissionDenied(MSG_RAI)


def _liste_ouverte(rapport: Rapport) -> None:
    if rapport.statut in STATUTS_LISTE_FIGEE:
        raise RegleMetierError(MSG_DESTINATAIRES_FIGES)


def _ouvrir_liste(rapport: Rapport, by: User) -> Rapport:
    """Droit, verrou (mission puis rapport) et état de la liste de diffusion."""
    _exiger_rai(by)
    ouvrir_mission(rapport.mission_id)
    rapport = relire(rapport)
    _liste_ouverte(rapport)
    return rapport


# --------------------------------------------------------------------------- liste de diffusion


def _cree(rapport: Rapport, by: User, **champs: Any) -> DestinataireDiffusion:
    destinataire = DestinataireDiffusion(rapport=rapport, mission_id=rapport.mission_id, **champs)
    enregistrer(destinataire, by=by, creation=True)
    return destinataire


@transaction.atomic
def preremplir_destinataires(rapport: Rapport, *, by: User) -> list[DestinataireDiffusion]:
    """DG actifs, audités affectés et chef de mission ; idempotent (rien n'est ajouté deux fois).

    Un destinataire déjà présent ou retiré par le RAI n'est pas rajouté.
    """
    rapport = relire(rapport)
    _liste_ouverte(rapport)
    deja = set(
        DestinataireDiffusion.all_objects.filter(
            rapport=rapport, utilisateur__isnull=False
        ).values_list("utilisateur_id", flat=True)
    )
    cibles: list[tuple[User, CategorieDestinataire]] = [
        (u, CategorieDestinataire.DG)
        for u in User.objects.filter(role=Role.DG, is_active=True).order_by("pk")
    ]
    affectations = (
        AffectationMission.objects.filter(
            mission_id=rapport.mission_id,
            role_mission__in=[RoleMission.AUDITE, RoleMission.CHEF_MISSION],
            utilisateur__is_active=True,
        )
        .select_related("utilisateur")
        .order_by("created_at")
    )
    for a in affectations:
        categorie = (
            CategorieDestinataire.EQUIPE
            if a.role_mission == RoleMission.CHEF_MISSION
            else CategorieDestinataire.AUDITE
        )
        cibles.append((a.utilisateur, categorie))
    crees: list[DestinataireDiffusion] = []
    for utilisateur, categorie in cibles:
        if utilisateur.pk in deja:
            continue
        deja.add(utilisateur.pk)
        crees.append(_cree(rapport, by, utilisateur=utilisateur, categorie=categorie))
    return crees


@transaction.atomic
def ajouter_destinataire(
    rapport: Rapport,
    *,
    by: User,
    categorie: str = CategorieDestinataire.AUTRE.value,
    utilisateur: User | None = None,
    nom_externe: str = "",
    qualite: str = "",
) -> DestinataireDiffusion:
    """Ajoute un destinataire interne (utilisateur actif) ou externe, avant la diffusion."""
    rapport = _ouvrir_liste(rapport, by)
    nom_externe = nom_externe.strip()
    if (utilisateur is None) == (not nom_externe):
        raise refuser(MSG_CIBLE, utilisateur=MSG_CIBLE)
    if utilisateur is not None:
        if not utilisateur.is_active:
            raise refuser("Cet utilisateur est inactif.", utilisateur="Utilisateur inactif.")
        if DestinataireDiffusion.objects.filter(rapport=rapport, utilisateur=utilisateur).exists():
            raise refuser("Ce destinataire figure déjà dans la liste.", utilisateur="Déjà présent.")
    return _cree(
        rapport,
        by,
        utilisateur=utilisateur,
        nom_externe=nom_externe,
        qualite=qualite.strip(),
        categorie=categorie,
    )


@transaction.atomic
def modifier_destinataire(
    destinataire: DestinataireDiffusion, *, by: User, **champs: Any
) -> DestinataireDiffusion:
    """Modifie la catégorie, la qualité et (externe) le nom ; jamais l'utilisateur."""
    _ouvrir_liste(destinataire.rapport, by)
    destinataire = relire(destinataire)
    inconnus = set(champs) - set(CHAMPS_MODIFIABLES)
    if inconnus:
        raise refuser("Données invalides.", **{c: "Champ non modifiable." for c in inconnus})
    if "nom_externe" in champs and destinataire.utilisateur_id is not None:
        raise refuser("Données invalides.", nom_externe="Destinataire interne.")
    for champ, valeur in champs.items():
        setattr(destinataire, champ, valeur.strip() if isinstance(valeur, str) else valeur)
    enregistrer(destinataire, by=by)
    return destinataire


def _recopie(destinataire: DestinataireDiffusion, rapport: Rapport) -> bool:
    """Le destinataire figurait dans la liste du rapport remplacé (D12) : jamais retirable."""
    if rapport.corrige_de_id is None:
        return False
    precedents = DestinataireDiffusion.objects.filter(rapport_id=rapport.corrige_de_id)
    if destinataire.utilisateur_id is not None:
        return precedents.filter(utilisateur_id=destinataire.utilisateur_id).exists()
    return precedents.filter(
        utilisateur__isnull=True,
        nom_externe=destinataire.nom_externe,
        qualite=destinataire.qualite,
    ).exists()


@transaction.atomic
def retirer_destinataire(destinataire: DestinataireDiffusion, *, by: User) -> None:
    rapport = _ouvrir_liste(destinataire.rapport, by)
    destinataire = relire(destinataire)
    if _recopie(destinataire, rapport):
        raise RegleMetierError(MSG_RECOPIE)
    destinataire.soft_delete(by)


# --------------------------------------------------------------------------- diffusion


def _etapes_closes(mission_id: Any) -> bool:
    statuts = dict(
        EtapeMission.objects.select_for_update()
        .filter(mission_id=mission_id, numero__gte=15)
        .values_list("numero", "statut")
    )
    return (
        all(statuts.get(n) in STATUTS_ETAPE_CLOSE for n in range(15, 19))
        and statuts.get(ETAPE_VALIDATION) == StatutEtape.VALIDEE
    )


def _porte_signature(rapport: Rapport, version_pdf: Any) -> None:
    """Mode FIGÉ à la validation : s'il exige la signature électronique, elle doit être posée."""
    if rapport.mode_signature not in MODES_ELECTRONIQUES:
        return
    signataire = signataire_electronique()
    if signataire is None or not signataire.est_signee(version_pdf):
        raise RegleMetierError(MSG_SIGNATURE)


def _integre(rapport: Rapport) -> bool:
    """Instantané conforme à son empreinte et, si exigée, confirmation de validation intacte."""
    if rapport.instantane_soumis is None:
        return False
    if empreinte("rapport", rapport.instantane_soumis) != rapport.empreinte_soumise:
        return False
    if rapport.mode_signature == ModeSignatureParametre.SIGNATURE_ELECTRONIQUE:
        return True
    confirmation = rapport.confirmation_validation
    return confirmation is not None and verifier(confirmation)


def _lien(rapport: Rapport) -> str:
    base = str(getattr(settings, "FRONTEND_URL", "")).rstrip("/")
    return f"{base}/rapports/{rapport.pk}" if base else ""


def _envoyer(rapport: Rapport, destinataires: list[tuple[str, str]], message: str) -> None:
    """Un e-mail par destinataire interne, sans pièce jointe : lien vers la plateforme."""
    mission = rapport.mission
    for adresse, nom in destinataires:
        send_mail_task.delay(
            [adresse],
            f"Rapport d'audit diffusé — {mission.reference}",
            "diffusion_rapport",
            {
                "nom": nom,
                "reference": mission.reference,
                "titre": mission.titre,
                "message": message,
                "corrige": rapport.corrige_de_id is not None,
                "motif_correction": rapport.motif_correction,
                "lien": _lien(rapport),
            },
        )


def _poser_suivi(destinataire: DestinataireDiffusion, champ: str, valeur: Any, by: User) -> None:
    setattr(destinataire, champ, valeur)
    destinataire.updated_by = by
    with actor_scope(by), transaction.atomic():
        destinataire.save(update_fields=[champ, "updated_at", "updated_by"])


@transaction.atomic
def diffuser(rapport: Rapport, *, message: str = "", by: User) -> Diffusion:
    """Diffuse le rapport validé (RAI) : `Diffusion` immuable, rapport DIFFUSE, mission diffusée.

    Un rapport corrigé (D12) ne touche à aucune étape ni au statut de la mission.
    """
    _exiger_rai(by)
    mission = ouvrir_mission(rapport.mission_id)
    verrouiller_etape(mission.pk, ETAPE_VALIDATION)
    rapport = relire(rapport)
    corrige = rapport.corrige_de_id is not None
    if rapport.statut != StatutRapport.VALIDE:
        raise RegleMetierError(MSG_NON_VALIDE)
    attendu = StatutMission.RAPPORT_DIFFUSE if corrige else StatutMission.EN_COMMUNICATION
    if mission.statut != attendu:
        raise RegleMetierError(MSG_HORS_PHASE)
    if not _etapes_closes(mission.pk):
        raise RegleMetierError(MSG_DIFFUSION)
    if not _integre(rapport):
        raise RegleMetierError(MSG_INTEGRITE)
    version = version_finale(rapport)
    if version is None or version.statut_pdf != StatutPdf.PRET or not version.fichier_docx:
        raise RegleMetierError(MSG_VERSION)
    _porte_signature(rapport, version)
    internes = list(
        DestinataireDiffusion.objects.filter(rapport=rapport).select_related("utilisateur")
    )
    if not internes:
        raise RegleMetierError(MSG_SANS_DESTINATAIRE)
    message = message.strip()
    avant = rapport.statut
    diffusion = Diffusion(
        rapport=rapport,
        mission_id=mission.pk,
        version_rapport=version,
        version_note=version_note(rapport),
        diffusee_par=by,
        message=message,
    )
    enregistrer(diffusion, by=by, creation=True)
    rapport.diffuser()
    sauver_transition(rapport, ["statut"], by=by)
    journaliser(rapport, TypeEvenementRapport.DIFFUSE, by=by, avant=avant, motif=message)
    if not corrige:
        marquer_rapport_diffuse(mission, by=by)
    maintenant = timezone.now()
    a_notifier: list[tuple[str, str]] = []
    for d in internes:
        if d.utilisateur is not None and d.utilisateur.email:
            _poser_suivi(d, "notifie_le", maintenant, by)
            a_notifier.append((d.utilisateur.email, d.utilisateur.get_full_name() or ""))

    def apres_validation() -> None:
        _envoyer(rapport, a_notifier, message)

    def emettre_signal() -> None:
        signals.rapport_diffuse.send(sender=Rapport, rapport=rapport, diffusion=diffusion, par=by)

    transaction.on_commit(apres_validation, robust=True)
    transaction.on_commit(emettre_signal, robust=True)
    return diffusion


# --------------------------------------------------------------------------- suivi


def _destinataire_de(rapport: Rapport, user: User, *, verrou: bool) -> DestinataireDiffusion | None:
    lignes = DestinataireDiffusion.objects.filter(rapport=rapport, utilisateur=user)
    return (lignes.select_for_update() if verrou else lignes).first()


@transaction.atomic
def noter_consultation(rapport: Rapport, user: User) -> None:
    """Pose `premiere_consultation_le` une fois ; sans effet hors destinataire interne ou diffusion.

    Appelée par la route de téléchargement : elle ne doit jamais faire échouer le téléchargement.
    """
    destinataire = _destinataire_de(rapport, user, verrou=True)
    if destinataire is None or destinataire.premiere_consultation_le is not None:
        return
    if relire(rapport).statut != StatutRapport.DIFFUSE:
        return
    try:
        _poser_suivi(destinataire, "premiere_consultation_le", timezone.now(), user)
    except MissionFigeeError:
        logger.info("Consultation non journalisée : mission figée.")


@transaction.atomic
def accuser_reception(rapport: Rapport, *, by: User) -> DestinataireDiffusion:
    """Accusé de réception du destinataire interne ; la première date fait foi."""
    rapport = relire(rapport)
    destinataire = _destinataire_de(rapport, by, verrou=True)
    if destinataire is None:
        raise PermissionDenied(MSG_PAS_DESTINATAIRE)
    if rapport.statut != StatutRapport.DIFFUSE:
        raise RegleMetierError(MSG_DIFFUSE_SEUL)
    if destinataire.accuse_reception_le is None:
        maintenant = timezone.now()
        _poser_suivi(destinataire, "accuse_reception_le", maintenant, by)
        if destinataire.premiere_consultation_le is None:
            _poser_suivi(destinataire, "premiere_consultation_le", maintenant, by)
    return destinataire


@transaction.atomic
def marquer_remis_hors_plateforme(
    destinataire: DestinataireDiffusion, *, le: date, by: User
) -> DestinataireDiffusion:
    """Date la remise d'un exemplaire à un destinataire externe (RAI, rapport diffusé)."""
    _exiger_rai(by)
    ouvrir_mission(destinataire.mission_id)
    destinataire = relire(destinataire)
    if destinataire.utilisateur_id is not None:
        raise RegleMetierError(MSG_EXTERNE_SEUL)
    rapport = relire(destinataire.rapport)
    if rapport.statut != StatutRapport.DIFFUSE:
        raise RegleMetierError(MSG_DIFFUSE_SEUL)
    diffusee_le = timezone.localtime(rapport.diffusion.diffusee_le, FUSEAU_ONEA).date()
    if not diffusee_le <= le <= aujourd_hui():
        raise refuser(MSG_DATE_REMISE, le=MSG_DATE_REMISE)
    _poser_suivi(
        destinataire, "remis_hors_plateforme_le", datetime.combine(le, time.min, FUSEAU_ONEA), by
    )
    return destinataire

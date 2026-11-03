"""Signature électronique PAdES du rapport final validé (lot 7 bis, RAI)."""

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core.exceptions import RegleMetierError
from apps.core.services import relire
from apps.documents.models import DocumentVersion
from apps.missions.models import StatutMission
from apps.signatures.electronique import signataire_electronique
from apps.signatures.models import SignatureElectronique
from apps.signatures.pades import MSG_NON_CONFIGUREE, SignatairePades, signature_de
from apps.signatures.parametres import MODES_ELECTRONIQUES
from apps.users.models import Role, User

from ..models import Rapport, StatutRapport, TypeEvenementRapport
from ._ecriture import journaliser, ouvrir_mission, verrouiller_etape
from ._versions import version_finale
from .validation import ETAPE_VALIDATION

MSG_RAI = "Seul le responsable de l'audit interne peut signer le rapport."
MSG_NON_VALIDE = "Seul un rapport validé peut être signé électroniquement."
MSG_MODE = "Le mode de signature de ce rapport n'exige pas de signature électronique."
MSG_VERSION = "Le rapport final n'est pas encore généré : patientez ou relancez la génération."
MSG_HORS_PHASE = "La mission n'est pas dans la phase où ce rapport peut être signé."
MSG_DIFFUSE = "Le rapport est déjà diffusé : il ne peut plus être signé."


def version_a_signer(rapport: Rapport) -> DocumentVersion | None:
    version = version_finale(rapport)
    if version is None or not version.fichier_pdf:
        return None
    return version


@transaction.atomic
def signer_rapport(rapport: Rapport, *, by: User, lieu: str = "") -> SignatureElectronique:
    """Signe le PDF du rapport final (RAI, rapport VALIDE, mode électronique figé)."""
    if by.role != Role.RAI:
        raise PermissionDenied(MSG_RAI)
    mission = ouvrir_mission(rapport.mission_id)
    verrouiller_etape(mission.pk, ETAPE_VALIDATION)
    rapport = relire(rapport)
    if rapport.statut == StatutRapport.DIFFUSE:
        raise RegleMetierError(MSG_DIFFUSE)
    if rapport.statut != StatutRapport.VALIDE:
        raise RegleMetierError(MSG_NON_VALIDE)
    attendu = (
        StatutMission.RAPPORT_DIFFUSE if rapport.corrige_de_id else StatutMission.EN_COMMUNICATION
    )
    if mission.statut != attendu:
        raise RegleMetierError(MSG_HORS_PHASE)
    if rapport.mode_signature not in MODES_ELECTRONIQUES:
        raise RegleMetierError(MSG_MODE)
    signataire = signataire_electronique()
    if not isinstance(signataire, SignatairePades):
        raise RegleMetierError(MSG_NON_CONFIGUREE)
    version = version_a_signer(rapport)
    if version is None:
        raise RegleMetierError(MSG_VERSION)
    signature = signataire.signer(
        version,
        by=by,
        raison=f"Validation du rapport {mission.reference} par le Responsable de l'Audit Interne",
        lieu=lieu,
    )
    journaliser(rapport, TypeEvenementRapport.SIGNE, by=by, avant=rapport.statut)
    return signature


def signature_du_rapport(rapport: Rapport) -> SignatureElectronique | None:
    version = version_finale(rapport)
    return None if version is None else signature_de(version)

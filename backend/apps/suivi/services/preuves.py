"""Preuves de mise en œuvre : dépôt contrôlé, écriture unique, empreinte vérifiée à la lecture (R8).

Entrée non fiable. Ordre : droit (403) → contrôle commun (taille, type réel par signature,
archive) → antivirus → lecture bornée du contenu → verrous (mission, puis suivi) → quota →
écriture du fichier en dernier. La clé de stockage est générée côté serveur (UUID) : le nom du
client ne sert qu'à l'affichage. Le stockage ne permet ni écrasement ni suppression : si la ligne
échoue après l'écriture, le fichier orphelin est consigné dans le journal, jamais effacé.
"""

import logging
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone

from apps.accomplissement.fichiers import EXTENSIONS_AUTORISEES, nom_affichable
from apps.core import antivirus
from apps.core.audit import actor_scope
from apps.core.consultations import journaliser_consultation
from apps.core.fichiers import controler_televersement
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.documents import stockage
from apps.documents.integrite import IntegriteError, verifier_empreinte
from apps.documents.services.quota import controler_quota
from apps.missions.gardes import verrouiller_mission
from apps.users.models import User

from .. import droits
from ..models import (
    EvenementSuivi,
    PreuveMiseEnOeuvre,
    StatutSuivi,
    SuiviAction,
    TypeEvenementSuivi,
)
from ._compte import pour_compte

logger = logging.getLogger(__name__)

MSG_LIBELLE = "Le libellé est obligatoire."
MSG_STATUT = (
    "Les preuves ne peuvent être déposées ou retirées que tant que l'action est à lancer "
    "ou en cours."
)
MSG_CHANGE = "Le fichier a changé pendant le dépôt : déposez-le à nouveau."
STATUTS_PREUVES_OUVERTS: frozenset[str] = frozenset({StatutSuivi.A_LANCER, StatutSuivi.EN_COURS})


def _verrouiller(suivi: SuiviAction) -> SuiviAction:
    """Ordre de verrouillage : mission, puis suivi (transaction requise)."""
    verrouiller_mission(suivi.mission_id)
    return relire(suivi)


def _exiger_ouvert(suivi: SuiviAction) -> None:
    if suivi.statut not in STATUTS_PREUVES_OUVERTS:
        raise refuser(MSG_STATUT)


def _toucher(suivi: SuiviAction, by: User) -> None:
    suivi.derniere_activite_le = timezone.now()
    suivi.updated_by = by
    with actor_scope(by):
        suivi.save(update_fields=["derniere_activite_le", "updated_by", "updated_at"])


def deposer_preuve(
    suivi: SuiviAction,
    *,
    fichier: "UploadedFile[Any]",
    libelle: str,
    by: User,
    description: str = "",
    commentaire: str = "",
) -> PreuveMiseEnOeuvre:
    # Droit d'abord : un non-autorisé reçoit 403, jamais une erreur sur le contenu.
    droits.exiger_operer_pour_responsable(by, suivi)
    taille_max = int(settings.PIECE_TAILLE_MAX_OCTETS)
    # Contrôle commun AVANT toute lecture complète en mémoire : taille réelle (seek), signature,
    # archive. Le type vient de la signature, jamais du content-type annoncé.
    detecte = controler_televersement(
        fichier, extensions=EXTENSIONS_AUTORISEES, taille_max=taille_max
    )
    antivirus.analyser(fichier)
    libelle = libelle.strip()
    if not libelle:
        raise refuser(MSG_LIBELLE, libelle=MSG_LIBELLE)
    nom = nom_affichable(str(fichier.name or ""))
    fichier.seek(0)
    contenu = fichier.read(taille_max + 1)  # borné : la taille annoncée peut mentir
    if len(contenu) != detecte.taille:
        raise refuser(MSG_CHANGE, fichier=MSG_CHANGE)

    with transaction.atomic():
        suivi = _verrouiller(suivi)
        droits.exiger_operer_pour_responsable(by, suivi)  # de nouveau, sous verrou
        _exiger_ouvert(suivi)
        texte, pour = pour_compte(suivi, by, commentaire)
        controler_quota(detecte.taille)
        maximum = PreuveMiseEnOeuvre.all_objects.filter(suivi=suivi).aggregate(m=Max("numero"))["m"]
        cle = f"suivi/preuves/{suivi.mission_id}/{uuid4()}"
        # Écriture du fichier en dernier : plus aucun contrôle ne peut échouer avant la ligne.
        cle, empreinte = stockage.ecrire_avec_empreinte(cle, contenu)
        try:
            preuve = PreuveMiseEnOeuvre(
                suivi=suivi,
                mission_id=suivi.mission_id,
                numero=int(maximum or 0) + 1,
                libelle=libelle[:200],
                description=description.strip(),
                cle_stockage=cle,
                empreinte_sha256=empreinte,
                taille_octets=detecte.taille,
                type_mime=detecte.mime,
                nom_fichier_original=nom,
                deposee_par=by,
            )
            enregistrer(preuve, by=by, creation=True)
            EvenementSuivi.journaliser(
                suivi,
                TypeEvenementSuivi.PREUVE_DEPOSEE,
                par=by,
                pour_compte_de=pour,
                texte=texte,
                statut_avant=suivi.statut,
                donnees={"preuve": str(preuve.pk), "numero": preuve.numero, "libelle": libelle},
            )
            _toucher(suivi, by)
        except BaseException:
            logger.error(  # noqa: TRY400
                "Fichier orphelin conservé (jamais effacé) : cle=%s sha256=%s suivi=%s",
                cle,
                empreinte,
                suivi.pk,
            )
            raise
    return preuve


def modifier_preuve(
    preuve: PreuveMiseEnOeuvre,
    *,
    by: User,
    libelle: str | None = None,
    description: str | None = None,
) -> PreuveMiseEnOeuvre:
    """Libellé et description seulement : le fichier et son empreinte sont immuables."""
    droits.exiger_operer_pour_responsable(by, preuve.suivi)
    with transaction.atomic():
        suivi = _verrouiller(preuve.suivi)
        droits.exiger_operer_pour_responsable(by, suivi)
        _exiger_ouvert(suivi)
        preuve = relire(preuve)
        changes = {
            champ: valeur
            for champ, valeur in (("libelle", libelle), ("description", description))
            if valeur is not None
        }
        appliquer(preuve, changes, {"libelle", "description"})
        preuve.libelle = preuve.libelle.strip()
        if not preuve.libelle:
            raise refuser(MSG_LIBELLE, libelle=MSG_LIBELLE)
        enregistrer(preuve, by=by)
    return preuve


def retirer_preuve(preuve: PreuveMiseEnOeuvre, *, by: User, commentaire: str = "") -> None:
    """Suppression logique : le fichier et son empreinte restent conservés."""
    droits.exiger_operer_pour_responsable(by, preuve.suivi)
    with transaction.atomic():
        suivi = _verrouiller(preuve.suivi)
        droits.exiger_operer_pour_responsable(by, suivi)
        _exiger_ouvert(suivi)
        texte, pour = pour_compte(suivi, by, commentaire)
        preuve = relire(preuve)
        preuve.soft_delete(by)
        EvenementSuivi.journaliser(
            suivi,
            TypeEvenementSuivi.PREUVE_RETIREE,
            par=by,
            pour_compte_de=pour,
            texte=texte,
            statut_avant=suivi.statut,
            donnees={"preuve": str(preuve.pk), "numero": preuve.numero},
        )
        _toucher(suivi, by)


def ouvrir_preuve_verifiee(
    preuve: PreuveMiseEnOeuvre, *, by: User, adresse_ip: str | None
) -> bytes:
    """Contenu de la preuve, après droit, relecture et vérification de l'empreinte.

    Droit (403) AVANT toute lecture du disque. Un fichier absent, illisible ou altéré lève
    `IntegriteError` (409, journal CRITICAL). La consultation n'est journalisée qu'une fois le
    contenu vérifié, donc réellement remis.
    """
    if preuve.deleted_at is not None:
        raise Http404("Preuve introuvable.")
    droits.exiger_telechargement_preuve(by, preuve)
    contexte = f"preuve {preuve.pk}"
    try:
        contenu = stockage.lire(preuve.cle_stockage)
    except (OSError, SuspiciousFileOperation) as exc:
        logger.critical("Fichier de preuve illisible (%s) : %s", contexte, type(exc).__name__)
        raise IntegriteError from exc
    if len(contenu) != preuve.taille_octets:
        logger.critical("Taille de preuve invalide (%s).", contexte)
        raise IntegriteError
    verifier_empreinte(contenu, preuve.empreinte_sha256, contexte)
    journaliser_consultation(preuve, par=by, action="TELECHARGEMENT", adresse_ip=adresse_ip)
    return contenu

"""Fixtures et aides de la tâche 8 : chaîne soumission, validation, versions de documents."""

from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.communication.models import Rapport
from apps.communication.services.diffusion import diffuser
from apps.communication.services.soumission import soumettre_rapport
from apps.communication.services.validation import valider_rapport
from apps.documents.models import (
    Document,
    DocumentVersion,
    GabaritDocument,
    StatutGabarit,
    StatutGeneration,
    StatutPdf,
)
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes
from tests.signatures.conftest import signataire_factice  # noqa: F401

XV_A_XVII = {15: "TERMINEE", 16: "TERMINEE", 17: "TERMINEE"}


@pytest.fixture
def admin(db: None) -> User:
    return make_user(Role.ADMIN)


@pytest.fixture
def dg(db: None) -> User:
    return make_user(Role.DG)


@pytest.fixture
def rapport_soumis_reel(rapport_redige: Rapport, chef: User) -> Rapport:
    """Rapport réellement soumis par le chef (instantané et empreinte du service)."""
    forcer_etapes(rapport_redige.mission, XV_A_XVII)
    return soumettre_rapport(rapport_redige, by=chef)


@pytest.fixture
def rapport_valide(rapport_soumis_reel: Rapport, rai: User, dg: User) -> Rapport:
    """Rapport validé ; un DG actif existe avant la validation (préremplissage de la liste)."""
    return valider_rapport(rapport_soumis_reel, by=rai)


@pytest.fixture
def rapport_diffuse(rapport_valide: Rapport, rai: User) -> Rapport:
    """Rapport diffusé (versions du rapport final et de la note prêtes)."""
    creer_version(rapport_valide)
    creer_version(rapport_valide, "NOTE_SYNTHETIQUE")
    diffuser(rapport_valide, by=rai)
    return Rapport.objects.get(pk=rapport_valide.pk)


def creer_version(
    rapport: Rapport,
    type_document: str = "RAPPORT_FINAL",
    *,
    pdf: bool = True,
    docx: bool = True,
    statut: str = StatutGeneration.PRETE,
    **extra: Any,
) -> DocumentVersion:
    """Version de document du rapport (sans fichier réel), liée à sa confirmation de validation."""
    auteur = make_user(Role.RAI)
    gabarit, _ = GabaritDocument.objects.get_or_create(
        type_document=type_document,
        version=1,
        defaults={
            "statut": StatutGabarit.ACTIF,
            "fichier": "gabarits/t.docx",
            "nom_original": "t.docx",
            "taille": 1,
            "empreinte": "a" * 64,
            "contrat_version": 1,
        },
    )
    document, _ = Document.objects.get_or_create(
        type_document=type_document,
        content_type=ContentType.objects.get_for_model(Rapport),
        object_id=rapport.pk,
        defaults={
            "mission": rapport.mission,
            "numero": f"{rapport.mission.reference}/{type_document}-{rapport.numero_version:02d}",
            "annee": 2026,
            "sequence": rapport.numero_version,
        },
    )
    derniere = document.versions.order_by("-numero_version").first()
    version: DocumentVersion = DocumentVersion.objects.create(
        document=document,
        numero_version=derniere.numero_version + 1 if derniere else 1,
        statut=statut,
        gabarit=gabarit,
        demandee_par=auteur,
        empreinte_contexte="b" * 64,
        fichier_docx="docs/t.docx" if docx else "",
        fichier_pdf="docs/t.pdf" if pdf else "",
        statut_pdf=StatutPdf.PRET if pdf else StatutPdf.EN_COURS,
        **{"confirmation_id": rapport.confirmation_validation_id, **extra},
    )
    return version

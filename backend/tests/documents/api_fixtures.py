"""Fixtures of the document API tests: a mission, its team and a ready version."""

from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.documents.models import DocumentVersion
from apps.missions.models import Mission, RoleMission
from apps.missions.services import equipe as svc_equipe
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import affecter

from .fabrique import docx_avec

Utilisateurs = dict[str, User]


@pytest.fixture
def utilisateurs(mission_planifiee: Mission, rai: User) -> Utilisateurs:
    chef = make_user(Role.AUDITEUR)
    affecter(mission_planifiee, chef, RoleMission.CHEF_MISSION)
    ancien = make_user(Role.AUDITEUR)
    affectation = affecter(mission_planifiee, ancien, RoleMission.AUDITEUR)
    svc_equipe.desaffecter(affectation, by=rai)
    audite = make_user(Role.AUDITE)
    affecter(mission_planifiee, audite, RoleMission.AUDITE)
    Mission.objects.filter(pk=mission_planifiee.pk).update(ordre_mission_emis_le=timezone.now())
    return {
        "rai": rai,
        "chef": chef,
        "auditeur_desaffecte": ancien,
        "audite_affecte": audite,
        "admin": make_user(Role.ADMIN),
        "dg": make_user(Role.DG),
    }


@pytest.fixture
def version_prete_mission(version_prete: DocumentVersion, utilisateurs: Utilisateurs) -> Any:
    return version_prete


def depot(nom: str = "gabarit.docx", contenu: bytes | None = None) -> dict[str, Any]:
    donnees = contenu if contenu is not None else docx_avec("Mission : {{ mission.titre }}")
    return {
        "type_document": "TEST_DOC",
        "fichier": SimpleUploadedFile(nom, donnees),
        "commentaire": "v2",
    }


def octets(reponse: Any) -> bytes:
    """Body of a `FileResponse` (streamed)."""
    return b"".join(reponse.streaming_content)

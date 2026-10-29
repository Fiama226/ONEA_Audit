import hashlib
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.core.models import BaseModel
from apps.documents.models import (
    Document,
    DocumentVersion,
    GabaritDocument,
    StatutGabarit,
    StatutGeneration,
)
from apps.documents.moteur import registre
from apps.documents.moteur.registre import TypeDocument, enregistrer_type
from apps.documents.stockage import cle_gabarit, cle_version, ecrire
from apps.missions.models import Mission
from apps.missions.services.missions import creer_mission, planifier_mission
from apps.signatures.models import Confirmation
from apps.users.models import Role, User
from config.documents_settings import configuration_stockage
from tests.factories import DirectionFactory, MissionFactory, ProcessusFactory
from tests.missions.conftest import chef, mission_lancee  # noqa: F401

from .fabrique import CONTRAT_TEST, docx_avec


@pytest.fixture(autouse=True)
def stockage_tmp(tmp_path: Path, settings: Any) -> Path:
    settings.DOCUMENTS_ROOT = str(tmp_path)
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": str(tmp_path)}
        ),
    }
    return tmp_path


class FournisseurTest:
    """Fake data provider: the source object is the mission itself."""

    def objet(self, objet_id: UUID) -> BaseModel:
        return Mission.objects.get(pk=objet_id)

    def mission_de(self, objet: BaseModel) -> Mission:
        assert isinstance(objet, Mission)
        return objet

    def objets_de_mission(self, mission: Mission) -> list[BaseModel]:
        return [mission]

    def peut_consulter(self, user: User, objet: BaseModel) -> bool:
        return True

    def peut_generer(self, user: User, objet: BaseModel) -> bool:
        return user.role == Role.RAI

    def raison_non_generable(self, objet: BaseModel) -> str | None:
        return None

    def contexte(self, objet: BaseModel) -> dict[str, Any]:
        assert isinstance(objet, Mission)
        return {"mission": {"reference": objet.reference, "titre": objet.titre}}

    def confirmation(self, objet: BaseModel) -> Confirmation | None:
        return None


@pytest.fixture
def type_test() -> Iterator[TypeDocument]:
    t = TypeDocument(
        code="TEST_DOC",
        libelle="Document de test",
        etape=None,
        contrat=CONTRAT_TEST,
        abreviation="TD",
        modele_numero="{mission}/{code}-{sequence}",
        portee_numero="MISSION",
        fournisseur=FournisseurTest(),
    )
    enregistrer_type(t)
    yield t
    registre._TYPES.pop("TEST_DOC", None)


@pytest.fixture
def mission_planifiee(rai: User) -> Mission:
    fabrique: Any = MissionFactory
    processus: Any = ProcessusFactory
    direction: Any = DirectionFactory
    fabrique()  # provides a validated cartography
    mission = creer_mission(
        titre="Audit de la facturation",
        type="ASSURANCE",
        by=rai,
        processus=[processus()],
        entites=[direction()],
        date_debut_prevue=date(2026, 3, 1),
        date_fin_prevue=date(2026, 5, 1),
    )
    mission = planifier_mission(mission, by=rai)
    assert mission.reference == "DAI/2026/M01"
    return mission


@pytest.fixture
def objet_test(mission_planifiee: Mission) -> Mission:
    return mission_planifiee


@pytest.fixture
def gabarit_actif_test(type_test: TypeDocument, rai: User) -> GabaritDocument:
    contenu = docx_avec("Mission : {{ mission.titre }}")
    empreinte = hashlib.sha256(contenu).hexdigest()
    nom = ecrire(cle_gabarit("test_doc", 1, empreinte), contenu)
    gabarit: GabaritDocument = GabaritDocument.objects.create(
        type_document="TEST_DOC",
        version=1,
        statut=StatutGabarit.ACTIF,
        fichier=nom,
        nom_original="gabarit.docx",
        taille=len(contenu),
        empreinte=empreinte,
        balises=["mission.titre"],
        contrat_version=CONTRAT_TEST.version,
        active_par=rai,
        active_le=timezone.now(),
        created_by=rai,
    )
    return gabarit


@pytest.fixture
def version_prete(
    gabarit_actif_test: GabaritDocument, objet_test: Mission, rai: User
) -> DocumentVersion:
    document = Document.objects.create(
        type_document="TEST_DOC",
        mission=objet_test,
        content_type=ContentType.objects.get_for_model(objet_test),
        object_id=objet_test.pk,
        numero=f"{objet_test.reference}/TD-01",
        annee=2026,
        sequence=1,
    )
    contenu = docx_avec("Mission : Audit")
    nom = ecrire(cle_version(document.pk, 1, "docx"), contenu)
    version: DocumentVersion = DocumentVersion.objects.create(
        document=document,
        numero_version=1,
        statut=StatutGeneration.PRETE,
        gabarit=gabarit_actif_test,
        contexte={"mission": {"titre": "Audit"}},
        empreinte_contexte="a" * 64,
        demandee_par=rai,
        fichier_docx=nom,
        empreinte_docx=hashlib.sha256(contenu).hexdigest(),
        taille_docx=len(contenu),
        genere_le=timezone.now(),
    )
    return version

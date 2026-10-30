"""Fixtures de la recherche : moteur en mémoire neuf par test, index peuplé, documents."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.constats.models import Constat, StatutConstat
from apps.documents.models import (
    Document,
    DocumentVersion,
    GabaritDocument,
    StatutGabarit,
    StatutGeneration,
)
from apps.missions.models import Mission
from apps.recherche.client import moteur, reinitialiser_moteur
from apps.recherche.services import reconcilier_index
from apps.users.models import Role, User
from tests.constats.factories import ConstatFactory
from tests.factories import DirectionFactory, make_user
from tests.missions.conftest import (  # noqa: F401
    affecter,
    audite_affecte,
    auditeur_mission,
    chef,
    forcer_etapes,
    mission_lancee,
)
from tests.suivi.conftest import (  # noqa: F401
    autre_audite,
    autre_auditeur,
    mission_en_suivi,
    responsable,
)


@pytest.fixture(autouse=True)
def moteur_propre() -> Iterator[None]:
    reinitialiser_moteur()
    yield
    reinitialiser_moteur()


@pytest.fixture
def index() -> Any:
    """Le moteur en mémoire courant (celui que `moteur()` renvoie)."""
    return moteur()


def soumettre_en_base(constat: Constat) -> None:
    """Passe le constat à SOUMIS sans signal ni réindexation (écriture en masse)."""
    Constat.objects.filter(pk=constat.pk).update(
        statut=StatutConstat.SOUMIS, soumis_le=timezone.now()
    )
    constat.refresh_from_db()


@pytest.fixture
def index_peuple(
    mission_lancee: Mission,  # noqa: F811
    audite_affecte: User,  # noqa: F811
    auditeur_mission: User,  # noqa: F811
) -> dict[str, str]:
    """Deux constats « Rapprochement bancaire » (brouillon, soumis) indexés dans la mission."""
    Mission.objects.filter(pk=mission_lancee.pk).update(ordre_mission_emis_le=timezone.now())
    entite = DirectionFactory()
    User.objects.filter(pk=audite_affecte.pk).update(direction_code=entite.code)
    audite_affecte.refresh_from_db()
    brouillon = ConstatFactory(
        mission=mission_lancee, entite=entite, titre="Rapprochement bancaire en brouillon"
    )
    soumis = ConstatFactory(
        mission=mission_lancee, entite=entite, titre="Rapprochement bancaire soumis"
    )
    soumettre_en_base(soumis)
    reconcilier_index()
    return {
        "CONSTAT-brouillon": f"CONSTAT-{brouillon.pk}",
        "CONSTAT-soumis": f"CONSTAT-{soumis.pk}",
    }


@pytest.fixture
def creer_document() -> Callable[..., Document]:
    """Document d'un type enregistré, avec (ou sans) version prête ; l'objet source est donné."""

    def _creer(
        mission: Mission, code: str, objet: Any, *, version: str | None = StatutGeneration.PRETE
    ) -> Document:
        rai = make_user(Role.RAI)
        document = Document.objects.create(
            type_document=code,
            mission=mission,
            content_type=ContentType.objects.get_for_model(objet),
            object_id=objet.pk,
            numero=f"{mission.reference}/{code}-{Document.all_objects.count() + 1:02d}",
            annee=2026,
            sequence=Document.all_objects.count() + 1,
        )
        if version is not None:
            gabarit, _ = GabaritDocument.objects.get_or_create(
                type_document=code,
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
            DocumentVersion.objects.create(
                document=document,
                numero_version=1,
                statut=version,
                gabarit=gabarit,
                demandee_par=rai,
                empreinte_contexte="b" * 64,
                contexte={"mission": {"objectifs": "CONFIDENTIEL-CONTEXTE-JSON"}},
            )
        return document

    return _creer

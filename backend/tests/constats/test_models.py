import pytest
from django.db import IntegrityError, transaction

from apps.constats.models import Constat, PositionAudite, ReponseAudite
from apps.missions.models import Mission
from apps.signatures.models import TypeDocumentSignable
from tests.constats.factories import ConstatFactory, ReponseFactory
from tests.factories import make_user

pytestmark = pytest.mark.django_db


def test_reference_constat_unique_meme_supprime(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    constat.soft_delete(make_user())
    with pytest.raises(IntegrityError), transaction.atomic():
        ConstatFactory(mission=mission_en_xiv, reference=constat.reference, numero=99)
    with pytest.raises(IntegrityError), transaction.atomic():
        ConstatFactory(mission=mission_en_xiv, numero=constat.numero, reference="C-98")
    suivant = ConstatFactory(mission=mission_en_xiv)
    assert suivant.numero == constat.numero + 1


def test_niveau_genere(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv, probabilite=3, impact=5)
    constat.refresh_from_db()
    assert constat.score == 15
    assert constat.niveau == "ELEVE"
    brouillon = ConstatFactory(mission=mission_en_xiv, probabilite=None, impact=None)
    brouillon.refresh_from_db()
    assert brouillon.score is None
    assert brouillon.niveau is None


def test_probabilite_hors_bornes_rejetee_en_base(mission_en_xiv: Mission) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ConstatFactory(mission=mission_en_xiv, probabilite=6)


def test_desaccord_sans_commentaire_rejete_en_base(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    with pytest.raises(IntegrityError), transaction.atomic():
        ReponseFactory(constat=constat, position=PositionAudite.DESACCORD, commentaire="")
    ok = ReponseFactory(constat=constat, position=PositionAudite.DESACCORD, commentaire="Non.")
    assert ok.pk


def test_type_document_reponse_constat() -> None:
    assert TypeDocumentSignable.REPONSE_CONSTAT.value == "REPONSE_CONSTAT"
    assert TypeDocumentSignable.REPONSE_CONSTAT.label == "Réponse à un constat"


def test_factory_constat_complet(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    assert constat.fiches.count() == 1
    assert constat.causes.count() == 1
    assert constat.recommandations.count() == 1
    assert Constat.objects.filter(mission=mission_en_xiv).count() == 1
    assert ReponseAudite.objects.count() == 0

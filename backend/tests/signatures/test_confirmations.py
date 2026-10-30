from datetime import date
from typing import Any, cast

import pytest
from auditlog.models import LogEntry
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.gardes_sql import maintenance
from apps.signatures.exceptions import ConfirmationImmuableError
from apps.signatures.models import Confirmation
from apps.signatures.serializers import ConfirmationResumeSerializer
from apps.signatures.services import confirmer, derniere_confirmation, empreinte, verifier
from apps.users.models import User
from tests.factories import ConfirmationFactory as _CF
from tests.referentiel.typed import direction as DirectionFactory

pytestmark = pytest.mark.django_db


def test_confirmation_immuable_et_verifiable(rai: User) -> None:
    objet = DirectionFactory()
    c = confirmer(
        type_document="ORDRE_MISSION",
        objet=objet,
        texte="Je soussigné(e)…",
        donnees={"titre": "Achats – Ouaga", "auditeurs": ["A", "B"]},
        by=rai,
    )
    assert verifier(c) and len(c.empreinte) == 64
    c.texte = "autre"
    with pytest.raises(ConfirmationImmuableError):
        c.save()
    with pytest.raises(ConfirmationImmuableError):
        Confirmation.objects.filter(pk=c.pk).update(texte="x")
    with pytest.raises(ConfirmationImmuableError):
        Confirmation.all_objects.filter(pk=c.pk).update(texte="x")
    with pytest.raises(ConfirmationImmuableError):
        Confirmation.objects.bulk_update([c], ["texte"])
    with pytest.raises(ConfirmationImmuableError):
        c.soft_delete(by=rai)


def test_message_immuabilite(rai: User) -> None:
    c = _confirmation(signataire=rai)
    with pytest.raises(ConfirmationImmuableError) as e:
        c.soft_delete(by=rai)
    assert e.value.message == (
        "Une confirmation est définitive : elle ne peut être ni modifiée ni supprimée."
    )


def test_empreinte_canonique_independante_de_l_ordre_des_cles() -> None:
    assert empreinte("t", {"a": 1, "b": "é"}) == empreinte("t", {"b": "é", "a": 1})
    assert empreinte("t", {"a": 1}) != empreinte("t ", {"a": 1})


def test_donnees_non_json_natif_verifiables(rai: User) -> None:
    c = confirmer(
        type_document="ORDRE_MISSION",
        objet=DirectionFactory(),
        texte="t",
        donnees={"debut": date(2026, 11, 2)},
        by=rai,
    )
    c.refresh_from_db()
    assert c.donnees == {"debut": "2026-11-02"}
    assert verifier(c)


def test_derniere_confirmation(rai: User) -> None:
    objet = DirectionFactory()
    premiere = confirmer(type_document="ORDRE_MISSION", objet=objet, texte="1", donnees={}, by=rai)
    seconde = confirmer(type_document="ORDRE_MISSION", objet=objet, texte="2", donnees={}, by=rai)
    confirmer(type_document="VALIDATION_RAPPORT", objet=objet, texte="3", donnees={}, by=rai)
    assert seconde.confirme_le >= premiere.confirme_le
    assert derniere_confirmation(objet, "ORDRE_MISSION") == seconde
    assert derniere_confirmation(DirectionFactory(), "ORDRE_MISSION") is None


def test_donnees_alterees_en_base_detectees(rai: User) -> None:
    c = confirmer(
        type_document="ORDRE_MISSION", objet=DirectionFactory(), texte="t", donnees={"a": 1}, by=rai
    )
    with maintenance(), connection.cursor() as cur:
        cur.execute(
            "UPDATE signatures_confirmation SET donnees = %s::jsonb WHERE id = %s",
            ['{"a": 2}', c.pk],
        )
    assert verifier(c) is False


def test_empreinte_invalide_refusee_par_la_base(rai: User) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _confirmation(signataire=rai, empreinte="XYZ")


def test_confirmation_historisee_avec_l_acteur(rai: User) -> None:
    c = confirmer(
        type_document="ORDRE_MISSION", objet=DirectionFactory(), texte="t", donnees={"a": 1}, by=rai
    )
    entree = LogEntry.objects.get_for_object(c).get()
    assert entree.actor == rai


def test_resume_serializer(rai: User) -> None:
    c = _confirmation(signataire=rai)
    data = ConfirmationResumeSerializer(c).data
    assert set(data) == {"id", "type_document", "signataire", "confirme_le", "empreinte"}
    assert set(data["signataire"]) == {"id", "nom_complet"}


def test_save_force_update_et_update_fields_refuses(rai: User) -> None:
    c = _confirmation(signataire=rai)
    clone = Confirmation(
        pk=c.pk,
        type_document=c.type_document,
        content_type_id=c.content_type_id,
        object_id=c.object_id,
        signataire_id=c.signataire_id,
        confirme_le=c.confirme_le,
        empreinte=c.empreinte,
        texte="x",
        donnees={},
    )
    with pytest.raises(ConfirmationImmuableError):
        clone.save(force_update=True)
    with pytest.raises(ConfirmationImmuableError):
        clone.save(update_fields=["texte"])
    c.refresh_from_db()
    assert c.texte != "x"


def test_bulk_create_update_conflicts_refuse(rai: User) -> None:
    c = _confirmation(signataire=rai)
    with pytest.raises(ConfirmationImmuableError):
        Confirmation.objects.bulk_create(
            [c], update_conflicts=True, update_fields=["texte"], unique_fields=["id"]
        )


def test_donnees_flottant_entier_verifiable_apres_postgres(rai: User) -> None:
    c = confirmer(
        type_document="ORDRE_MISSION",
        objet=DirectionFactory(),
        texte="t",
        donnees={"x": 1e20, "y": 1.5, "z": 2.0},
        by=rai,
    )
    assert verifier(c)


@pytest.mark.parametrize("valeur", [float("nan"), float("inf")])
def test_donnees_non_finies_refusees(rai: User, valeur: float) -> None:
    with pytest.raises(RegleMetierError):
        confirmer(
            type_document="ORDRE_MISSION",
            objet=DirectionFactory(),
            texte="t",
            donnees={"x": valeur},
            by=rai,
        )


def test_derniere_confirmation_departage_a_horodatage_egal(rai: User) -> None:
    objet = DirectionFactory()
    instant = timezone.now()
    cs = [_confirmation(objet=objet, signataire=rai, confirme_le=instant) for _ in range(3)]
    voulue = max(cs, key=lambda c: c.pk)
    assert derniere_confirmation(objet, "ORDRE_MISSION") == voulue


def _confirmation(**kw: Any) -> Confirmation:
    return cast(Confirmation, _CF(**kw))  # type: ignore[no-untyped-call]

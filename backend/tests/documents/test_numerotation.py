from dataclasses import replace
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.core.exceptions import RegleMetierError
from apps.documents.models import Document, FormatNumerotation, GabaritDocument
from apps.documents.moteur import registre
from apps.documents.moteur.registre import TypeDocument
from apps.documents.numerotation import (
    apercu_numero,
    attribuer_numero,
    erreurs_modele,
    format_de,
    modifier_format,
)
from apps.missions.models import Mission
from apps.users.models import User

pytestmark = pytest.mark.django_db


def _creer(mission: Mission, numero: str, annee: int, sequence: int, **kw: Any) -> Document:
    document: Document = Document.objects.create(
        type_document="TEST_DOC",
        mission=mission,
        content_type=ContentType.objects.get_for_model(Mission),
        object_id=kw.pop("object_id", mission.pk),
        numero=numero,
        annee=annee,
        sequence=sequence,
    )
    return document


def test_premier_numero(type_test: object, mission_planifiee: Mission) -> None:
    assert attribuer_numero("TEST_DOC", mission=mission_planifiee) == (
        "DAI/2026/M01/TD-01",
        2026,
        1,
    )
    assert format_de("TEST_DOC").abreviation == "TD"


def test_changement_de_format_vaut_pour_la_suite(
    type_test: object, mission_planifiee: Mission, rai: User
) -> None:
    numero, annee, seq = attribuer_numero("TEST_DOC", mission=mission_planifiee)
    _creer(mission_planifiee, numero, annee, seq)
    modifier_format(
        "TEST_DOC", by=rai, modele="{code}/{annee}/{sequence}", portee="ANNEE", abreviation="XX"
    )
    numero2, _, seq2 = attribuer_numero("TEST_DOC", mission=mission_planifiee)
    assert (numero2, seq2) == ("XX/2026/02", 2)
    assert Document.objects.get().numero == "DAI/2026/M01/TD-01"


def test_numero_existant_saute_au_suivant(
    type_test: object, mission_planifiee: Mission, rai: User
) -> None:
    modifier_format("TEST_DOC", by=rai, modele="{code}-{annee}-{sequence}", portee="ANNEE")
    _creer(mission_planifiee, "TD-2026-02", 2026, 1)  # collides with the next candidate
    assert attribuer_numero("TEST_DOC", mission=mission_planifiee) == ("TD-2026-03", 2026, 3)


def test_numero_d_un_document_supprime_non_reutilise(
    type_test: object, mission_planifiee: Mission, rai: User
) -> None:
    numero, annee, seq = attribuer_numero("TEST_DOC", mission=mission_planifiee)
    _creer(mission_planifiee, numero, annee, seq).soft_delete(by=rai)
    assert attribuer_numero("TEST_DOC", mission=mission_planifiee)[2] == 2


def test_portee_annee_repart_a_1(type_test: object, mission_planifiee: Mission, rai: User) -> None:
    modifier_format("TEST_DOC", by=rai, modele="{code}-{annee}-{sequence}", portee="ANNEE")
    _creer(mission_planifiee, "TD-2026-01", 2026, 1)
    assert attribuer_numero("TEST_DOC", mission=mission_planifiee)[0] == "TD-2026-02"
    mission_planifiee.annee = 2027
    assert attribuer_numero("TEST_DOC", mission=mission_planifiee) == ("TD-2027-01", 2027, 1)


def test_erreurs_modele() -> None:
    permis = "Champs permis : {mission}, {annee}, {code}, {sequence}."
    assert erreurs_modele("{mission}/{code}-{sequence}", "MISSION") == []
    assert erreurs_modele("{mission}/{truc}-{sequence}", "MISSION") == [
        f"Champ inconnu : truc. {permis}"
    ]
    assert erreurs_modele("{mission}/{code}", "MISSION") == ["Le modèle doit contenir {sequence}."]
    assert erreurs_modele("{code}-{sequence}", "MISSION") == [
        "La portée « Par mission » exige {mission}."
    ]
    assert erreurs_modele("{code}-{sequence}", "ANNEE") == [
        "La portée « Par année » exige {annee}."
    ]
    assert erreurs_modele("{mission}/" + "x" * 40 + "{sequence}", "MISSION") == [
        "Le numéro dépasse 40 caractères."
    ]
    assert erreurs_modele("{sequence!r}{mission}", "MISSION")[0].startswith("Aucune mise en forme")
    assert erreurs_modele("{mission.__class__}{sequence}", "MISSION")[0].startswith("Champ inconnu")
    assert erreurs_modele("{mission", "MISSION")


def test_apercu_numero_defaut() -> None:
    assert apercu_numero("{mission}/{code}-{sequence}", "MISSION", "OM") == "DAI/2026/M07/OM-01"
    assert apercu_numero("{code}-{annee}-{sequence}", "ANNEE", "RP") == "RP-2026-01"


def test_modifier_format_refuse_invalide(type_test: object, rai: User) -> None:
    with pytest.raises(RegleMetierError) as e:
        modifier_format("TEST_DOC", by=rai, modele="{mission}", abreviation="TROP-LONGUE")
    assert set(e.value.errors) == {"modele", "abreviation"}


def test_sequence_avec_mise_en_forme_refusee() -> None:
    assert erreurs_modele("{mission}/{sequence:02d}", "MISSION") == [
        "Aucune mise en forme n'est permise dans {sequence:02d} : "
        "la séquence compte toujours 2 chiffres.",
        "Le modèle doit contenir {sequence}.",
    ]


def test_format_enregistre_invalide_refuse(type_test: TypeDocument) -> None:
    registre._TYPES["TEST_DOC"] = replace(type_test, modele_numero="{mission}/{code}")
    with pytest.raises(RegleMetierError):
        format_de("TEST_DOC")


def test_modele_sans_sequence_ne_boucle_pas(type_test: object, mission_planifiee: Mission) -> None:
    FormatNumerotation.objects.create(
        type_document="TEST_DOC", modele="{mission}", portee="MISSION", abreviation="TD"
    )
    with pytest.raises(RegleMetierError):
        attribuer_numero("TEST_DOC", mission=mission_planifiee)


def test_reference_vide_refusee(type_test: object, mission_planifiee: Mission) -> None:
    mission_planifiee.reference = ""
    with pytest.raises(RegleMetierError, match="référence"):
        attribuer_numero("TEST_DOC", mission=mission_planifiee)


def test_longueur_avec_reference_maximale() -> None:
    assert erreurs_modele("{mission}/{code}-{sequence}", "MISSION") == []
    assert erreurs_modele("{mission}/" + "x" * 18 + "{sequence}", "MISSION") == [
        "Le numéro dépasse 40 caractères."
    ]


@pytest.mark.django_db(transaction=True)
def test_attribuer_exige_une_transaction(type_test: object, mission_planifiee: Mission) -> None:
    with pytest.raises(RuntimeError, match="transaction"):
        attribuer_numero("TEST_DOC", mission=mission_planifiee)


def test_format_et_gabarit_actif_non_supprimables(
    type_test: object, gabarit_actif_test: GabaritDocument, rai: User
) -> None:
    with pytest.raises(RegleMetierError):
        format_de("TEST_DOC").soft_delete(by=rai)
    with pytest.raises(RegleMetierError):
        gabarit_actif_test.soft_delete(by=rai)

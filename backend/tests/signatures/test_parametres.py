import pytest
from auditlog.models import LogEntry
from rest_framework.exceptions import PermissionDenied

from apps.core.exceptions import RegleMetierError
from apps.signatures.models import (
    TYPES_PARAMETRABLES,
    ParametreSignature,
    TypeDocumentSignable,
)
from apps.signatures.parametres import Exigences, exigences, mode_requis, modifier_mode
from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_mode_electronique_indisponible(admin: User) -> None:
    with pytest.raises(RegleMetierError, match="pas encore disponible"):
        modifier_mode("VALIDATION_RAPPORT", mode="SIGNATURE_ELECTRONIQUE", by=admin)
    assert not ParametreSignature.objects.exists()
    assert exigences("VALIDATION_RAPPORT") == Exigences(confirmation=True, electronique=False)


def test_mode_electronique_avec_signataire(admin: User, signataire_factice: object) -> None:
    modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION_ET_SIGNATURE", by=admin)
    assert exigences("VALIDATION_RAPPORT") == Exigences(confirmation=True, electronique=True)
    modifier_mode("VALIDATION_RAPPORT", mode="SIGNATURE_ELECTRONIQUE", by=admin)
    assert exigences("VALIDATION_RAPPORT") == Exigences(confirmation=False, electronique=True)
    modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION", by=admin)
    assert exigences("VALIDATION_RAPPORT") == Exigences(confirmation=True, electronique=False)
    assert ParametreSignature.objects.count() == 1


def test_retour_a_confirmation_toujours_permis(admin: User) -> None:
    assert modifier_mode("ORDRE_MISSION", mode="CONFIRMATION", by=admin).mode == "CONFIRMATION"


def test_type_non_parametrable_refuse(admin: User) -> None:
    with pytest.raises(RegleMetierError, match="pas de mode de signature paramétrable"):
        modifier_mode("REPONSE_CONSTAT", mode="CONFIRMATION", by=admin)
    assert mode_requis("REPONSE_CONSTAT") == "CONFIRMATION"
    assert exigences("REPONSE_CONSTAT") == Exigences(confirmation=True, electronique=False)


def test_mode_inconnu_refuse(admin: User) -> None:
    with pytest.raises(RegleMetierError):
        modifier_mode("VALIDATION_RAPPORT", mode="PAPIER", by=admin)


def test_seul_admin_modifie(rai: User, user: User, audite: User, dg: User) -> None:
    for u in (rai, user, audite, dg):
        with pytest.raises(PermissionDenied):
            modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION", by=u)
    assert not ParametreSignature.objects.exists()


def test_parametre_historise(admin: User, signataire_factice: object) -> None:
    modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION_ET_SIGNATURE", by=admin)
    ligne = ParametreSignature.objects.get(type_document="VALIDATION_RAPPORT")
    entrees = LogEntry.objects.get_for_object(ligne).order_by("timestamp")
    modif = [e for e in entrees if e.action == LogEntry.Action.UPDATE]
    assert len(modif) == 1
    assert modif[0].changes_dict["mode"] == ["CONFIRMATION", "CONFIRMATION_ET_SIGNATURE"]
    assert modif[0].actor == admin


def test_parametre_jamais_supprime(admin: User) -> None:
    ligne = modifier_mode("ORDRE_MISSION", mode="CONFIRMATION", by=admin)
    with pytest.raises(RegleMetierError):
        ligne.soft_delete(admin)
    with pytest.raises(Exception):  # noqa: B017, PT011
        ligne.delete()
    assert ParametreSignature.objects.count() == 1


def test_nouveaux_types_signables() -> None:
    for code in ("REPONSE_RAPPORT_PROVISOIRE", "ACCEPTATION_RISQUE", "ENGAGEMENT_PLAN_ACTIONS"):
        assert code in TypeDocumentSignable.values
        assert code not in TYPES_PARAMETRABLES
    assert TypeDocumentSignable.ENGAGEMENT_PLAN_ACTIONS.label == "Engagement sur le plan d'actions"

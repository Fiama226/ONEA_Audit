"""Règles de gouvernance : valeurs par défaut, validation, droits, piste d'audit, notifications."""

from typing import Any

import pytest
from auditlog.models import LogEntry
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.gouvernance import regles_gouvernance as rg
from apps.gouvernance.models import RegleGouvernance
from apps.notifications.models import Notification
from apps.users.models import DelegationGestionComptes, Role, User
from tests.connexion import connecter
from tests.factories import make_user

pytestmark = pytest.mark.django_db

URL = "/api/v1/governance-rules/"


def _client(user: User) -> APIClient:
    return connecter(APIClient(), user)


# --------------------------------------------------------------------------- service


def test_defaults_are_the_prudent_ones() -> None:
    assert rg.valeur(rg.PROGRAM_APPROVAL) == {
        "approver": "DG_AND_BOARD",
        "required_before_launch": True,
    }
    assert rg.valeur(rg.RISK_ACCEPTANCE) == {"low": "RAI", "medium": "RAI", "high": "DG"}
    assert rg.valeur(rg.OBJECTIVITY) == {
        "enabled": True,
        "mode": "BLOCK",
        "cooling_off_months": 12,
    }
    assert rg.valeur(rg.PROGRAM_RISK_LINK) == {"required": True}
    assert rg.valeur(rg.AUDITEE_RESPONSE) == {
        "delay_days": 15,
        "waiver_by": "RAI",
        "reason_required": True,
        "evidence_agreement": True,
        "findings_agreed": True,
        "response_or_deadline": True,
    }
    assert rg.valeur(rg.STEP_ORDER) == {"mode": "STRICT"}
    assert rg.valeur(rg.SEARCH_FALLBACK) == {"scope": "MISSIONS"}
    assert rg.valeur(rg.AUDITEE_STEP_READ) == {"allowed": True}
    assert not any(rg.est_assouplie(cle) for cle in rg.CLES)


def test_change_is_read_back_and_cache_is_invalidated(admin: User) -> None:
    assert rg.step_order_strict() is True  # met la valeur en cache
    rg.modifier(rg.STEP_ORDER, {"mode": "FREE"}, motif="Mission pilote", by=admin)
    assert rg.step_order_strict() is False
    cache.clear()
    assert rg.step_order_strict() is False


def test_partial_value_keeps_the_other_fields(admin: User) -> None:
    rg.modifier(rg.OBJECTIVITY, {"cooling_off_months": 24}, motif="", by=admin)
    assert rg.valeur(rg.OBJECTIVITY) == {"enabled": True, "mode": "BLOCK", "cooling_off_months": 24}


@pytest.mark.parametrize(
    ("cle", "valeur", "champ"),
    [
        (rg.PROGRAM_APPROVAL, {"approver": "CONSEIL"}, "approver"),
        (rg.PROGRAM_APPROVAL, {"required_before_launch": "oui"}, "required_before_launch"),
        (rg.RISK_ACCEPTANCE, {"high": "AUDITEUR"}, "high"),
        (rg.OBJECTIVITY, {"cooling_off_months": -1}, "cooling_off_months"),
        (rg.OBJECTIVITY, {"cooling_off_months": 61}, "cooling_off_months"),
        (rg.OBJECTIVITY, {"cooling_off_months": True}, "cooling_off_months"),
        (rg.OBJECTIVITY, {"cooling_off_months": 1.5}, "cooling_off_months"),
        (rg.AUDITEE_RESPONSE, {"delay_days": 0}, "delay_days"),
        (rg.AUDITEE_RESPONSE, {"delay_days": 61}, "delay_days"),
        (rg.AUDITEE_RESPONSE, {"waiver_by": "AUDITEUR"}, "waiver_by"),
        (rg.STEP_ORDER, {"mode": "AUCUN"}, "mode"),
        (rg.SEARCH_FALLBACK, {"scope": "TOUT"}, "scope"),
        (rg.AUDITEE_STEP_READ, {"allowed": None}, "allowed"),
        (rg.STEP_ORDER, {"inconnu": 1}, "inconnu"),
    ],
)
def test_strict_validation(admin: User, cle: str, valeur: dict[str, Any], champ: str) -> None:
    with pytest.raises(rg.RegleInvalideError) as exc:
        rg.modifier(cle, valeur, motif="Essai", by=admin)
    assert champ in exc.value.errors
    assert not RegleGouvernance.objects.filter(cle=cle).exists()


def test_risk_escalation_must_not_decrease_with_the_level(admin: User) -> None:
    with pytest.raises(rg.RegleInvalideError) as exc:
        rg.modifier(rg.RISK_ACCEPTANCE, {"medium": "DG", "high": "RAI"}, motif="x", by=admin)
    assert "high" in exc.value.errors


def test_unknown_rule_is_refused(admin: User) -> None:
    with pytest.raises(rg.RegleInconnueError):
        rg.modifier("inconnue", {}, motif="x", by=admin)


@pytest.mark.parametrize("role", [Role.RAI, Role.DG, Role.AUDITEUR, Role.AUDITE])
def test_only_the_admin_changes_a_rule(role: str) -> None:
    acteur = make_user(role)
    with pytest.raises(rg.PermissionDenied):
        rg.modifier(rg.STEP_ORDER, {"mode": "FREE"}, motif="x", by=acteur)


def test_account_delegation_gives_no_right_on_rules() -> None:
    delegue = make_user(Role.RAI)
    DelegationGestionComptes.objects.create(
        user=delegue, creer=True, reinitialiser=True, roles=True, desactiver=True
    )
    with pytest.raises(rg.PermissionDenied):
        rg.modifier(rg.STEP_ORDER, {"mode": "FREE"}, motif="x", by=delegue)


def test_inactive_admin_cannot_change_a_rule() -> None:
    admin = make_user(Role.ADMIN, is_active=False)
    with pytest.raises(rg.PermissionDenied):
        rg.modifier(rg.STEP_ORDER, {"mode": "FREE"}, motif="x", by=admin)


def test_weakening_requires_a_reason(admin: User) -> None:
    with pytest.raises(rg.RegleInvalideError) as exc:
        rg.modifier(rg.OBJECTIVITY, {"mode": "WARN"}, motif="  ", by=admin)
    assert "motif" in exc.value.errors


def test_strengthening_needs_no_reason(admin: User) -> None:
    rg.modifier(rg.OBJECTIVITY, {"cooling_off_months": 24}, motif="", by=admin)
    assert rg.valeur(rg.OBJECTIVITY)["cooling_off_months"] == 24


@pytest.mark.parametrize(
    ("cle", "valeur", "affaiblit"),
    [
        (rg.PROGRAM_APPROVAL, {"approver": "DG"}, True),
        (rg.PROGRAM_APPROVAL, {"required_before_launch": False}, True),
        (rg.RISK_ACCEPTANCE, {"high": "BOARD"}, False),
        (rg.RISK_ACCEPTANCE, {"low": "NONE"}, True),
        (rg.OBJECTIVITY, {"enabled": False}, True),
        (rg.OBJECTIVITY, {"cooling_off_months": 6}, True),
        (rg.PROGRAM_RISK_LINK, {"required": False}, True),
        (rg.AUDITEE_RESPONSE, {"delay_days": 10}, True),
        (rg.AUDITEE_RESPONSE, {"delay_days": 30}, False),
        (rg.AUDITEE_RESPONSE, {"waiver_by": "DG"}, False),
        (rg.AUDITEE_RESPONSE, {"findings_agreed": False}, True),
        (rg.STEP_ORDER, {"mode": "FREE"}, True),
        (rg.SEARCH_FALLBACK, {"scope": "MISSIONS_AND_FINDINGS"}, False),
        (rg.AUDITEE_STEP_READ, {"allowed": False}, False),
    ],
)
def test_weakening_is_detected(cle: str, valeur: dict[str, Any], affaiblit: bool) -> None:
    nouvelle = {**rg.valeur(cle), **valeur}
    assert rg.affaiblit(cle, rg.valeur(cle), nouvelle) is affaiblit


def test_change_is_written_to_the_audit_trail_with_reason(admin: User) -> None:
    rg.modifier(rg.STEP_ORDER, {"mode": "FREE"}, motif="Mission pilote", by=admin)
    ligne = RegleGouvernance.objects.get(cle=rg.STEP_ORDER)
    entree = LogEntry.objects.get_for_object(ligne).order_by("-timestamp", "-id").first()
    assert entree is not None
    assert entree.actor_id == admin.pk
    avant, apres = entree.changes_dict["valeur"]
    assert "STRICT" in avant and "FREE" in apres
    assert entree.additional_data["motif"] == "Mission pilote"
    assert entree.additional_data["affaiblissement"] is True
    assert entree.additional_data["action"] == "regle_gouvernance"


def test_first_change_records_the_default_as_before(admin: User) -> None:
    rg.modifier(rg.SEARCH_FALLBACK, {"scope": "MISSIONS_AND_FINDINGS"}, motif="", by=admin)
    ligne = RegleGouvernance.objects.get(cle=rg.SEARCH_FALLBACK)
    changements = [
        e.changes_dict.get("valeur")
        for e in LogEntry.objects.get_for_object(ligne).order_by("timestamp", "id")
    ]
    assert any(
        c and "MISSIONS_AND_FINDINGS" in c[1] and "MISSIONS_AND" not in c[0] for c in changements
    )


def test_unchanged_value_writes_nothing(admin: User) -> None:
    rg.modifier(rg.STEP_ORDER, {"mode": "STRICT"}, motif="", by=admin)
    assert not RegleGouvernance.objects.filter(cle=rg.STEP_ORDER).exists()


def test_weakening_notifies_dg_and_rai(admin: User) -> None:
    dg = make_user(Role.DG)
    rai = make_user(Role.RAI)
    auditeur = make_user(Role.AUDITEUR)
    rg.modifier(rg.OBJECTIVITY, {"enabled": False}, motif="Effectif réduit", by=admin)
    destinataires = set(
        Notification.objects.filter(type="REGLE_ASSOUPLIE").values_list(
            "destinataire_id", flat=True
        )
    )
    assert destinataires == {dg.pk, rai.pk}
    assert auditeur.pk not in destinataires
    notification = Notification.objects.filter(destinataire=dg).get()
    assert "Effectif réduit" in notification.message


def test_strengthening_notifies_nobody(admin: User) -> None:
    make_user(Role.DG)
    rg.modifier(rg.OBJECTIVITY, {"cooling_off_months": 24}, motif="", by=admin)
    assert not Notification.objects.exists()


def test_relaxed_norm_rule_is_flagged(admin: User) -> None:
    rg.modifier(rg.PROGRAM_APPROVAL, {"approver": "DG"}, motif="Conseil non réuni", by=admin)
    assert rg.est_assouplie(rg.PROGRAM_APPROVAL)
    etat = {e["cle"]: e for e in rg.etat_regles()}
    assert etat[rg.PROGRAM_APPROVAL]["assouplie"] is True
    assert etat[rg.PROGRAM_APPROVAL]["issue_des_normes"] is True
    assert etat[rg.PROGRAM_APPROVAL]["motif"] == "Conseil non réuni"
    assert etat[rg.STEP_ORDER]["assouplie"] is False


def test_rule_cannot_be_deleted(admin: User) -> None:
    rg.modifier(rg.STEP_ORDER, {"mode": "FREE"}, motif="x", by=admin)
    ligne = RegleGouvernance.objects.get(cle=rg.STEP_ORDER)
    with pytest.raises(Exception, match="supprim"):
        ligne.soft_delete(admin)


def test_corrupt_stored_value_falls_back_to_default(admin: User) -> None:
    RegleGouvernance.objects.create(cle=rg.STEP_ORDER, valeur={"mode": "N'IMPORTE"})
    cache.clear()
    assert rg.step_order_strict() is True


# --------------------------------------------------------------------------- API


@pytest.mark.parametrize("role", [Role.ADMIN, Role.RAI, Role.DG])
def test_list_is_readable_by_admin_rai_and_dg(role: str) -> None:
    reponse = _client(make_user(role)).get(URL)
    assert reponse.status_code == 200
    cles = [r["cle"] for r in reponse.json()]
    assert cles == list(rg.CLES)
    premiere = reponse.json()[0]
    assert {
        "cle",
        "libelle",
        "description",
        "valeur",
        "defaut",
        "issue_des_normes",
        "reference",
        "assouplie",
        "modifie_le",
        "modifie_par",
        "motif",
    } <= set(premiere)


@pytest.mark.parametrize("role", [Role.AUDITEUR, Role.AUDITE])
def test_list_is_refused_to_other_roles(role: str) -> None:
    assert _client(make_user(role)).get(URL).status_code == 403


def test_admin_updates_a_rule_through_the_api(admin: User) -> None:
    reponse = _client(admin).patch(
        f"{URL}{rg.STEP_ORDER}/",
        {"valeur": {"mode": "FREE"}, "motif": "Mission pilote"},
        format="json",
    )
    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["valeur"] == {"mode": "FREE"}
    assert reponse.json()["assouplie"] is True
    assert reponse.json()["modifie_par"]["id"] == admin.pk


@pytest.mark.parametrize("role", [Role.RAI, Role.DG])
def test_rai_and_dg_cannot_update_through_the_api(role: str) -> None:
    reponse = _client(make_user(role)).patch(
        f"{URL}{rg.STEP_ORDER}/", {"valeur": {"mode": "FREE"}, "motif": "x"}, format="json"
    )
    assert reponse.status_code == 403


def test_api_validation_errors_are_400_or_422(admin: User) -> None:
    client = _client(admin)
    reponse = client.patch(
        f"{URL}{rg.OBJECTIVITY}/", {"valeur": {"cooling_off_months": 99}}, format="json"
    )
    assert reponse.status_code in (400, 422)
    assert "cooling_off_months" in reponse.json()["errors"]
    assert client.patch(f"{URL}inconnue/", {"valeur": {}}, format="json").status_code == 404
    reponse = client.patch(f"{URL}{rg.STEP_ORDER}/", {"valeur": "FREE"}, format="json")
    assert reponse.status_code == 400


def test_weakening_without_reason_is_refused_by_the_api(admin: User) -> None:
    reponse = _client(admin).patch(
        f"{URL}{rg.OBJECTIVITY}/", {"valeur": {"enabled": False}}, format="json"
    )
    assert reponse.status_code in (400, 422)
    assert "motif" in reponse.json()["errors"]


def test_before_value_comes_from_the_locked_row_not_a_stale_cache(admin: User) -> None:
    rg.modifier(rg.STEP_ORDER, {"mode": "FREE"}, motif="Mission pilote", by=admin)
    # Cache périmé : il affirme encore STRICT alors que la base dit FREE.
    perime = {cle: dict(r.defaut) for cle, r in rg.REGLES.items()}
    cache.set(rg.CLE_CACHE, perime, rg.DUREE_CACHE)
    rg.modifier(rg.STEP_ORDER, {"mode": "STRICT"}, motif="", by=admin)
    ligne = RegleGouvernance.objects.get(cle=rg.STEP_ORDER)
    assert ligne.valeur == {"mode": "STRICT"}  # le changement n'a pas été pris pour un no-op
    entree = LogEntry.objects.get_for_object(ligne).order_by("-timestamp", "-id").first()
    assert entree is not None
    avant, apres = entree.changes_dict["valeur"]
    assert "FREE" in avant and "STRICT" in apres

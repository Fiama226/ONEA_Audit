"""Durcissement : contournements du gel, lignée de numérotation, instances périmées."""

from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.http import Http404

from apps.core.exceptions import RegleMetierError
from apps.referentiel.exceptions import CartographieFigeeError
from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    NatureObjet,
    Risque,
    StatutCartographie,
)
from apps.referentiel.services import (
    comparer_versions,
    creer_objet,
    creer_processus,
    creer_risque,
    creer_version,
    modifier_direction,
    modifier_risque,
    supprimer_direction,
    supprimer_risque,
    valider_version,
)
from apps.users.models import User
from tests.referentiel import typed

pytestmark = pytest.mark.django_db

SUPPRIME = "2026-01-01T00:00:00Z"


def _risque(version: CartographieVersion, rai: User, processus: Any = None, **kw: Any) -> Risque:
    return creer_risque(
        version=version,
        processus=processus or typed.processus(),
        libelle="x",
        probabilite=1,
        impact=1,
        by=rai,
        **kw,
    )


def _nouveau(version: CartographieVersion, risque: Risque, numero: int) -> Risque:
    return Risque(
        version=version,
        processus=risque.processus,
        numero=numero,
        rang=numero,
        code=f"{numero}-ABC-R{numero}",
        libelle="n",
        probabilite=1,
        impact=1,
        priorite=3,
    )


def _validee(rai: User, annee: int = 2025) -> tuple[CartographieVersion, Risque]:
    v = typed.version(annee=annee)
    r = _risque(v, rai)
    valider_version(v, by=rai)
    r.refresh_from_db()
    return v, r


def test_deplacer_un_risque_hors_version_validee_refuse(rai: User) -> None:
    _, r = _validee(rai)
    brouillon = typed.version(annee=2030)
    r.version = brouillon
    with pytest.raises(CartographieFigeeError):
        r.save()
    assert Risque.objects.filter(version=brouillon).count() == 0


def test_changer_de_version_un_risque_de_brouillon_refuse(rai: User) -> None:
    r = _risque(typed.version(annee=2024), rai)
    r.version = typed.version(annee=2030)
    with pytest.raises(RegleMetierError):
        r.save()


def test_queryset_update_bloque_sur_version_validee(rai: User) -> None:
    v, r = _validee(rai)
    with pytest.raises(CartographieFigeeError):
        Risque.objects.filter(pk=r.pk).update(libelle="pirate")
    with pytest.raises(CartographieFigeeError):
        Risque.all_objects.filter(pk=r.pk).update(deleted_at=SUPPRIME)
    with pytest.raises(CartographieFigeeError):
        Risque.objects.filter(version=v).update(libelle="pirate")
    with pytest.raises(CartographieFigeeError):
        CartographieVersion.objects.filter(pk=v.pk).update(libelle="pirate")
    with pytest.raises(CartographieFigeeError):
        CartographieVersion.all_objects.filter(pk=v.pk).update(deleted_at=SUPPRIME)
    r.refresh_from_db()
    assert r.libelle != "pirate"
    assert r.deleted_at is None


def test_bulk_update_et_bulk_create_bloques_sur_version_validee(rai: User) -> None:
    v, r = _validee(rai)
    r.libelle = "y"
    with pytest.raises(CartographieFigeeError):
        Risque.objects.bulk_update([r], ["libelle"])
    with pytest.raises(CartographieFigeeError):
        CartographieVersion.objects.bulk_update([v], ["libelle"])
    with pytest.raises(CartographieFigeeError):
        Risque.objects.bulk_create([_nouveau(v, r, 99)])


def test_queryset_ecritures_ok_sur_brouillon(rai: User) -> None:
    v = typed.version(annee=2024)
    r = _risque(v, rai)
    assert Risque.objects.filter(pk=r.pk).update(libelle="a") == 1
    r.refresh_from_db()
    r.libelle = "b"
    Risque.objects.bulk_update([r], ["libelle"])
    assert CartographieVersion.objects.filter(pk=v.pk).update(libelle="c") == 1
    Risque.objects.bulk_create([_nouveau(v, r, 50)])
    assert Risque.objects.filter(version=v).count() == 2


def test_validee_exige_date_et_valideur_en_base() -> None:
    v = typed.version(annee=2024)
    with pytest.raises(IntegrityError), transaction.atomic():
        CartographieVersion.objects.filter(pk=v.pk).update(statut=StatutCartographie.VALIDEE)


def test_numero_supprime_dans_la_lignee_jamais_reutilise(rai: User) -> None:
    p = typed.processus(code="FEP")
    v26 = typed.version(annee=2026)
    _risque(v26, rai, p)
    dernier = _risque(v26, rai, p)
    supprimer_risque(dernier, by=rai)
    valider_version(v26, by=rai)
    v27 = creer_version(annee=2027, libelle="2027", source=v26, by=rai)
    nouveau = _risque(v27, rai, p)
    assert nouveau.numero != dernier.numero
    assert nouveau.rang != dernier.rang
    comp = comparer_versions(v26, v27)
    assert comp.modifies == []
    assert [r.code for r in comp.ajoutes] == [nouveau.code]


def test_modifier_risque_supprime_entre_temps_n_est_pas_ressuscite(rai: User) -> None:
    r = _risque(typed.version(annee=2024), rai)
    perime = Risque.objects.get(pk=r.pk)
    supprimer_risque(r, by=rai)
    with pytest.raises(Http404):
        modifier_risque(perime, libelle="zombie", by=rai)
    with pytest.raises(Http404):
        supprimer_risque(perime, by=rai)
    assert Risque.objects.filter(pk=r.pk).count() == 0


def test_creer_risque_cible_supprimee_refusee(rai: User) -> None:
    v = typed.version(annee=2024)
    p = typed.processus()
    o = typed.objet(processus=p)
    p_mort = typed.processus()
    p_mort.soft_delete(rai)
    with pytest.raises(RegleMetierError) as exc:
        _risque(v, rai, p_mort)
    assert "processus" in exc.value.errors
    o.soft_delete(rai)
    with pytest.raises(RegleMetierError) as exc:
        _risque(v, rai, p, objet_auditable=o)
    assert "objet_auditable" in exc.value.errors


def test_modifier_direction_supprimee_entre_temps_pas_ressuscitee(rai: User) -> None:
    d = typed.direction()
    perime = Direction.objects.get(pk=d.pk)
    supprimer_direction(d, by=rai)
    with pytest.raises(Http404):
        modifier_direction(perime, libelle="zombie", by=rai)
    assert Direction.objects.filter(pk=d.pk).count() == 0


def test_creer_processus_direction_supprimee_refusee(rai: User) -> None:
    d = typed.direction()
    d.soft_delete(rai)
    with pytest.raises(RegleMetierError) as exc:
        creer_processus(code="ZZZ", libelle="x", famille="SUPPORT", directions=[d], by=rai)
    assert "directions" in exc.value.errors


def test_creer_objet_processus_supprime_refuse(rai: User) -> None:
    p = typed.processus()
    p.soft_delete(rai)
    with pytest.raises(RegleMetierError) as exc:
        creer_objet(processus=p, nature=NatureObjet.DOMAINE, libelle="x", by=rai)
    assert "processus" in exc.value.errors

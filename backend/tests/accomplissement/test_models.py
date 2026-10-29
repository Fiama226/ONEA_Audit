from datetime import date
from decimal import Decimal

import pytest
from auditlog.registry import auditlog
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accomplissement.models import (
    EvenementFiche,
    FicheDeTest,
    InstantaneProgramme,
    PieceJustificative,
    ProgrammeDeTravail,
    StatutFiche,
    StatutTest,
    TestPrevu,
    TypeEvenementFiche,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import MissionFigeeError
from apps.missions.models import EtapeMission, Mission, StatutMission
from apps.users.models import Role
from tests.accomplissement.factories import (
    FicheFactory,
    PieceFactory,
    ProgrammeFactory,
    TestPrevuFactory,
)
from tests.factories import ObjectifAuditFactory, make_user

pytestmark = pytest.mark.django_db


def test_programme_unique_actif_par_objectif(mission_lancee: Mission) -> None:
    objectif = ObjectifAuditFactory(mission=mission_lancee)
    p = ProgrammeFactory(mission=mission_lancee, objectif=objectif)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProgrammeFactory(mission=mission_lancee, objectif=objectif)
    p.soft_delete(make_user(Role.RAI))
    ProgrammeFactory(mission=mission_lancee, objectif=objectif)  # supprimé : ne bloque pas


def test_code_test_unique_meme_supprime(mission_lancee: Mission) -> None:
    t = TestPrevuFactory(mission=mission_lancee)
    t.soft_delete(make_user(Role.RAI))
    with pytest.raises(IntegrityError), transaction.atomic():
        TestPrevuFactory(mission=mission_lancee, numero=t.numero, code=t.code)
    with pytest.raises(IntegrityError), transaction.atomic():
        TestPrevuFactory(mission=mission_lancee, numero=t.numero + 50, code=t.code)
    suivant = TestPrevuFactory(mission=mission_lancee)
    assert suivant.numero == t.numero + 1  # le compteur compte les tests supprimés


def test_abandon_exige_motif_en_base(mission_lancee: Mission) -> None:
    t = TestPrevuFactory(mission=mission_lancee)
    with pytest.raises(IntegrityError), transaction.atomic():
        TestPrevu.objects.filter(pk=t.pk).update(statut=StatutTest.ABANDONNE)
    TestPrevu.objects.filter(pk=t.pk).update(
        statut=StatutTest.ABANDONNE, motif_abandon="Hors période"
    )


def test_charge_et_dates_coherentes(mission_lancee: Mission) -> None:
    t = TestPrevuFactory(mission=mission_lancee)
    with pytest.raises(IntegrityError), transaction.atomic():
        TestPrevu.objects.filter(pk=t.pk).update(charge_prevue_jours=Decimal("-1"))
    with pytest.raises(IntegrityError), transaction.atomic():
        TestPrevu.objects.filter(pk=t.pk).update(
            date_debut_prevue=date(2026, 2, 10), date_fin_prevue=date(2026, 2, 1)
        )


def test_exceptions_superieures_a_la_taille_rejetees(mission_en_accomplissement: Mission) -> None:
    tests = list(mission_en_accomplissement.tests_prevus.order_by("numero"))
    with pytest.raises(IntegrityError), transaction.atomic():
        FicheFactory(
            mission=mission_en_accomplissement,
            test=tests[0],
            taille_testee=5,
            nombre_exceptions=6,
        )
    FicheFactory(
        mission=mission_en_accomplissement, test=tests[0], taille_testee=5, nombre_exceptions=5
    )


def test_une_seule_fiche_active_par_test(mission_en_accomplissement: Mission) -> None:
    test = mission_en_accomplissement.tests_prevus.first()
    f = FicheFactory(mission=mission_en_accomplissement, test=test)
    assert test.fiche == f
    with pytest.raises(IntegrityError), transaction.atomic():
        FicheFactory(mission=mission_en_accomplissement, test=test)
    f.soft_delete(make_user(Role.RAI))  # la suppression logique libère le test
    FicheFactory(mission=mission_en_accomplissement, test=test)


def test_soumis_exige_conclusion_en_base(fiche_brouillon: FicheDeTest) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        FicheDeTest.objects.filter(pk=fiche_brouillon.pk).update(statut=StatutFiche.SOUMIS)
    FicheDeTest.objects.filter(pk=fiche_brouillon.pk).update(
        statut=StatutFiche.SOUMIS, conclusion="ANOMALIE"
    )


def test_evenement_fiche_ajout_seul(fiche_brouillon: FicheDeTest) -> None:
    par = make_user(Role.AUDITEUR)
    e = EvenementFiche.journaliser(
        fiche_brouillon, TypeEvenementFiche.SOUMISE, par=par, statut_avant=StatutFiche.BROUILLON
    )
    assert e.statut_apres == fiche_brouillon.statut
    e.motif = "x"
    with pytest.raises(RegleMetierError):
        e.save()
    with pytest.raises(RegleMetierError):
        EvenementFiche.objects.filter(pk=e.pk).update(motif="x")
    with pytest.raises(RegleMetierError):
        EvenementFiche.all_objects.bulk_update([e], ["motif"])


def _instantane(mission: Mission, **kw: object) -> InstantaneProgramme:
    etape = EtapeMission.objects.get(mission=mission, numero=10)
    return InstantaneProgramme(
        mission=mission,
        etape=etape,
        donnees={"programmes": []},
        empreinte="a" * 64,
        valide_par=make_user(Role.RAI),
        valide_le=timezone.now(),
        **kw,
    )


def test_instantane_immuable(mission_en_accomplissement: Mission) -> None:
    i = _instantane(mission_en_accomplissement)
    i.save()
    i.empreinte = "b" * 64
    with pytest.raises(RegleMetierError):
        i.save()
    with pytest.raises(RegleMetierError):
        InstantaneProgramme.objects.filter(pk=i.pk).update(empreinte="c" * 64)
    with pytest.raises(RegleMetierError):
        InstantaneProgramme.all_objects.bulk_update([i], ["empreinte"])
    with pytest.raises(RegleMetierError):
        InstantaneProgramme.all_objects.bulk_create(
            [_instantane(mission_en_accomplissement)],
            update_conflicts=True,
            update_fields=["empreinte"],
            unique_fields=["id"],
        )
    with pytest.raises(RegleMetierError):
        i.soft_delete(make_user(Role.RAI))
    mauvais = _instantane(mission_en_accomplissement)
    mauvais.empreinte = "zz"
    with pytest.raises(IntegrityError), transaction.atomic():
        mauvais.save()


def test_modeles_enregistres_dans_la_piste_d_audit() -> None:
    for modele in (
        ProgrammeDeTravail,
        TestPrevu,
        FicheDeTest,
        EvenementFiche,
        PieceJustificative,
        InstantaneProgramme,
    ):
        assert auditlog.contains(modele)


def test_mission_suspendue_refuse_toutes_ecritures(
    fiche_brouillon: FicheDeTest, mission_en_accomplissement: Mission
) -> None:
    piece = PieceFactory(fiche=fiche_brouillon)
    Mission.objects.filter(pk=mission_en_accomplissement.pk).update(
        statut=StatutMission.SUSPENDUE, statut_avant_suspension=StatutMission.EN_PLANIFICATION
    )
    test = fiche_brouillon.test
    for objet, champ, valeur in (
        (test.programme, "commentaire", "x"),
        (test, "charge_prevue_jours", Decimal("1")),
        (fiche_brouillon, "resultat", "x"),
        (piece, "libelle", "x"),
    ):
        setattr(objet, champ, valeur)
        with pytest.raises(MissionFigeeError):
            objet.save()
    with pytest.raises(MissionFigeeError):
        EvenementFiche.journaliser(
            fiche_brouillon,
            TypeEvenementFiche.SOUMISE,
            par=make_user(),
            statut_avant=StatutFiche.BROUILLON,
        )
    with pytest.raises(MissionFigeeError):
        _instantane(mission_en_accomplissement).save()
    with pytest.raises(MissionFigeeError):
        TestPrevuFactory(
            mission=mission_en_accomplissement, programme=test.programme, complementaire=True
        )

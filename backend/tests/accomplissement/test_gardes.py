from decimal import Decimal

import pytest

from apps.accomplissement.exceptions import (
    FicheValideeError,
    FicheVerrouilleeError,
    PieceImmuableError,
)
from apps.accomplissement.models import (
    FicheDeTest,
    PieceJustificative,
    ProgrammeDeTravail,
    StatutFiche,
    StatutTest,
    TestPrevu,
)
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, StatutEtape
from apps.users.models import Role
from tests.accomplissement.factories import (
    FicheFactory,
    PieceFactory,
    ProgrammeFactory,
    TestPrevuFactory,
)
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_save_direct_refuse_par_groupe_de_champs(mission_lancee: Mission) -> None:
    t = TestPrevuFactory(mission=mission_lancee)
    forcer_etapes(mission_lancee, {8: "TERMINEE"})  # VIII close, IX ouverte
    t.refresh_from_db()
    t.charge_prevue_jours = Decimal("2.5")
    t.save()  # ressources : permis
    t.procedure = "contournement"
    with pytest.raises(EtapeCloseError) as exc:
        t.save()
    assert exc.value.romain == "VIII"
    with pytest.raises(EtapeCloseError):
        TestPrevu.objects.filter(pk=t.pk).update(procedure="x")
    with pytest.raises(EtapeCloseError):
        TestPrevu.all_objects.bulk_update([t], ["procedure"])


def test_ressources_gelees_par_ix(mission_lancee: Mission) -> None:
    t = TestPrevuFactory(mission=mission_lancee)
    forcer_etapes(mission_lancee, {8: "TERMINEE", 9: "TERMINEE"})
    t.refresh_from_db()
    t.charge_prevue_jours = Decimal("3")
    with pytest.raises(EtapeCloseError) as exc:
        t.save()
    assert exc.value.romain == "IX"


def test_creation_test_gelee_par_viii_sauf_complementaire(
    mission_en_accomplissement: Mission,
) -> None:
    prog = mission_en_accomplissement.programmes.first()
    with pytest.raises(EtapeCloseError) as exc:
        TestPrevuFactory(mission=mission_en_accomplissement, programme=prog)
    assert exc.value.romain == "VIII"
    TestPrevuFactory(mission=mission_en_accomplissement, programme=prog, complementaire=True)
    forcer_etapes(mission_en_accomplissement, {12: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError) as exc:
        TestPrevuFactory(mission=mission_en_accomplissement, programme=prog, complementaire=True)
    assert exc.value.romain == "XII"


def test_abandon_dans_la_fenetre_xii(mission_en_accomplissement: Mission) -> None:
    t = mission_en_accomplissement.tests_prevus.first()
    t.statut = StatutTest.ABANDONNE
    t.motif_abandon = "Contrôle non testable"
    t.save()  # VIII close mais XII ouverte : permis
    forcer_etapes(mission_en_accomplissement, {12: StatutEtape.TERMINEE})
    t.motif_abandon = "autre"
    with pytest.raises(EtapeCloseError):
        t.save()


def test_programme_gele_par_viii(mission_lancee: Mission) -> None:
    p = ProgrammeFactory(mission=mission_lancee)
    forcer_etapes(mission_lancee, {8: "TERMINEE"})
    p.commentaire = "x"
    with pytest.raises(EtapeCloseError):
        p.save()
    with pytest.raises(EtapeCloseError):
        ProgrammeDeTravail.objects.filter(pk=p.pk).update(commentaire="x")


def test_piece_champs_fichier_immuables(fiche_brouillon: FicheDeTest) -> None:
    p = PieceFactory(fiche=fiche_brouillon)
    p.libelle = "Bon de commande 12"
    p.save()  # permis
    p.empreinte_sha256 = "0" * 64
    with pytest.raises(PieceImmuableError):
        p.save()
    with pytest.raises(PieceImmuableError):
        PieceJustificative.objects.filter(pk=p.pk).update(cle_stockage="autre")
    with pytest.raises(PieceImmuableError):
        PieceJustificative.objects.filter(pk=p.pk).update(taille_octets=1)
    p.refresh_from_db()
    with pytest.raises(PieceImmuableError):
        PieceJustificative.all_objects.bulk_update([p], ["nom_fichier_original"])
    with pytest.raises(PieceImmuableError):
        PieceJustificative.all_objects.bulk_create(
            [p], update_conflicts=True, update_fields=["cle_stockage"], unique_fields=["id"]
        )


def test_piece_retrait_logique_et_fenetre(fiche_brouillon: FicheDeTest) -> None:
    p = PieceFactory(fiche=fiche_brouillon)
    p.soft_delete(make_user(Role.AUDITEUR))  # fiche brouillon, XII ouverte : permis
    assert PieceJustificative.all_objects.filter(pk=p.pk, deleted_at__isnull=False).exists()
    q = PieceFactory(fiche=fiche_brouillon)
    forcer_etapes(fiche_brouillon.mission, {12: StatutEtape.TERMINEE})
    q.libelle = "x"
    with pytest.raises(EtapeCloseError):
        q.save()
    with pytest.raises(EtapeCloseError):
        PieceFactory(fiche=fiche_brouillon)


def test_piece_refusee_sur_fiche_soumise(fiche_brouillon: FicheDeTest) -> None:
    p = PieceFactory(fiche=fiche_brouillon)
    fiche_brouillon.conclusion = "ANOMALIE"
    fiche_brouillon.soumettre()
    fiche_brouillon.save()
    p.libelle = "x"
    with pytest.raises(FicheVerrouilleeError, match="soumise"):
        p.save()
    with pytest.raises(FicheVerrouilleeError):
        PieceJustificative.objects.filter(pk=p.pk).update(libelle="y")
    with pytest.raises(FicheVerrouilleeError):
        PieceFactory(fiche=fiche_brouillon)


def test_fiche_validee_immuable_sauf_rouvrir(fiche_brouillon: FicheDeTest) -> None:
    f = fiche_brouillon
    f.conclusion = "ANOMALIE"
    f.soumettre()
    f.save()  # XII ouverte
    forcer_etapes(f.mission, {13: StatutEtape.EN_COURS})
    f.valider()
    f.save()  # XIII ouverte
    f.refresh_from_db()
    assert f.statut == StatutFiche.VALIDE
    f.travaux_realises = "modif"
    with pytest.raises(FicheValideeError, match="validée : rouvrez-la"):
        f.save()
    with pytest.raises(FicheValideeError):
        FicheDeTest.objects.filter(pk=f.pk).update(resultat="x")
    piece_err = PieceFactory.build(fiche=f)
    with pytest.raises(FicheValideeError):
        piece_err.save()
    f.refresh_from_db()
    f.rouvrir()
    f.save()  # seule sauvegarde permise sur une fiche VALIDE
    f.refresh_from_db()
    assert f.statut == StatutFiche.BROUILLON
    f.travaux_realises = "modif"
    f.save()  # de nouveau modifiable (XII ouverte)
    f.travaux_realises = "encore"
    f.save()


def test_fiche_close_hors_xii(fiche_brouillon: FicheDeTest) -> None:
    autre = fiche_brouillon.mission.tests_prevus.exclude(pk=fiche_brouillon.test_id).first()
    forcer_etapes(fiche_brouillon.mission, {12: StatutEtape.TERMINEE})
    fiche_brouillon.travaux_realises = "x"
    with pytest.raises(EtapeCloseError) as exc:
        fiche_brouillon.save()
    assert exc.value.romain == "XII"
    with pytest.raises(EtapeCloseError):
        FicheDeTest.objects.filter(pk=fiche_brouillon.pk).update(resultat="x")
    with pytest.raises(EtapeCloseError):
        FicheFactory(mission=fiche_brouillon.mission, test=autre)


def test_validation_exige_xiii_non_close(fiche_brouillon: FicheDeTest) -> None:
    f = fiche_brouillon
    f.conclusion = "ANOMALIE"
    f.soumettre()
    f.save()
    f.valider()
    forcer_etapes(f.mission, {13: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError) as exc:
        f.save()
    assert exc.value.romain == "XIII"


def test_fiche_creee_par_bulk_create_gardee(mission_en_accomplissement: Mission) -> None:
    forcer_etapes(mission_en_accomplissement, {12: StatutEtape.TERMINEE})
    test = mission_en_accomplissement.tests_prevus.first()
    with pytest.raises(EtapeCloseError):
        FicheDeTest.all_objects.bulk_create(
            [
                FicheDeTest(
                    mission=mission_en_accomplissement,
                    test=test,
                    auteur=make_user(Role.AUDITEUR),
                )
            ]
        )

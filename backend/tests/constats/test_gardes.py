import pytest
from django.db import transaction
from django.utils import timezone

from apps.accomplissement.models import FicheDeTest
from apps.constats.exceptions import ConstatValideError
from apps.constats.models import (
    CategorieCause,
    CauseConstat,
    Constat,
    EvenementConstat,
    Recommandation,
    ReponseAudite,
    StatutConstat,
    TypeEvenementConstat,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, StatutEtape
from tests.constats.factories import (
    CauseFactory,
    ConstatFactory,
    RecommandationFactory,
    ReponseFactory,
    fiche_anomalie,
)
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _valider(constat: Constat) -> Constat:
    constat.soumettre()
    constat.save()
    constat.valider()
    constat.save()
    return constat


def test_constat_valide_immuable_sauf_rouvrir(mission_en_xiv: Mission) -> None:
    constat = _valider(ConstatFactory(mission=mission_en_xiv))
    constat.titre = "autre"
    with pytest.raises(ConstatValideError):
        constat.save()
    with pytest.raises(ConstatValideError):
        Constat.objects.filter(pk=constat.pk).update(titre="x")
    with pytest.raises(ConstatValideError):
        Constat.all_objects.bulk_update([constat], ["titre"])
    with pytest.raises(ConstatValideError):
        constat.soft_delete(make_user())
    constat.refresh_from_db()
    constat.rouvrir()
    constat.save()
    constat.refresh_from_db()
    assert constat.statut == StatutConstat.BROUILLON
    constat.titre = "modifié"
    constat.save()


def test_constat_gele_par_xiv_close(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    forcer_etapes(mission_en_xiv, {14: StatutEtape.TERMINEE})
    constat.titre = "x"
    with pytest.raises(EtapeCloseError) as exc:
        constat.save()
    assert exc.value.romain == "XIV"
    with pytest.raises(EtapeCloseError):
        ConstatFactory(mission=mission_en_xiv)


def test_causes_et_recommandations_gelees_avec_le_constat(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    cause = constat.causes.get()
    reco = constat.recommandations.get()
    _valider(constat)
    cause.description = "x"
    with pytest.raises(ConstatValideError):
        cause.save()
    reco.libelle = "x"
    with pytest.raises(ConstatValideError):
        reco.save()
    with pytest.raises(ConstatValideError):
        CauseConstat.objects.filter(pk=cause.pk).update(description="y")
    with pytest.raises(ConstatValideError):
        Recommandation.objects.filter(pk=reco.pk).update(libelle="y")
    with pytest.raises(ConstatValideError):
        CauseFactory(constat=constat, categorie=CategorieCause.MILIEU)
    with pytest.raises(ConstatValideError):
        RecommandationFactory(constat=constat)
    with pytest.raises(ConstatValideError):
        reco.soft_delete(make_user())


def test_causes_gelees_par_xiv_close(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    reco = constat.recommandations.get()
    forcer_etapes(mission_en_xiv, {14: StatutEtape.TERMINEE})
    reco.libelle = "x"
    with pytest.raises(EtapeCloseError):
        reco.save()
    with pytest.raises(EtapeCloseError):
        CauseFactory(constat=constat)


def test_m2m_fiches_gele_hors_xiv(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    fiche = fiche_anomalie(mission_en_xiv)
    # Constat valide : refus dans les deux sens (remove / clear).
    _valider(constat)
    with pytest.raises(ConstatValideError), transaction.atomic():
        constat.fiches.remove(fiche)
    with pytest.raises(ConstatValideError), transaction.atomic():
        constat.fiches.clear()
    with pytest.raises(ConstatValideError), transaction.atomic():
        fiche.constats.remove(constat)
    with pytest.raises(ConstatValideError), transaction.atomic():
        fiche.constats.clear()
    constat.refresh_from_db()
    constat.rouvrir()
    constat.save()
    autre = ConstatFactory(mission=mission_en_xiv)
    autre.fiches.clear()
    forcer_etapes(mission_en_xiv, {14: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError), transaction.atomic():
        constat.fiches.set([])
    with pytest.raises(EtapeCloseError), transaction.atomic():
        fiche.constats.add(autre)
    assert FicheDeTest.objects.filter(constats=constat).count() == 1


def test_reponse_ajout_seul(mission_en_xiv: Mission) -> None:
    reponse = ReponseFactory(constat=ConstatFactory(mission=mission_en_xiv))
    reponse.commentaire = "modifié"
    with pytest.raises(RegleMetierError):
        reponse.save()
    with pytest.raises(RegleMetierError):
        reponse.soft_delete(make_user())
    with pytest.raises(RegleMetierError):
        ReponseAudite.objects.filter(pk=reponse.pk).update(commentaire="x")
    with pytest.raises(RegleMetierError):
        ReponseAudite.all_objects.bulk_update([reponse], ["commentaire"])
    with pytest.raises(RegleMetierError):
        ReponseAudite.all_objects.bulk_create(
            [reponse],
            update_conflicts=True,
            update_fields=["commentaire"],
            unique_fields=["id"],
        )
    assert ReponseAudite.objects.count() == 1


def test_reponse_permise_sur_constat_valide_gelee_par_xv(mission_en_xiv: Mission) -> None:
    constat = _valider(ConstatFactory(mission=mission_en_xiv))
    ReponseFactory(constat=constat)  # constat validé : la réponse reste permise
    forcer_etapes(mission_en_xiv, {15: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError) as exc:
        ReponseFactory(constat=constat)
    assert exc.value.romain == "XV"


def test_evenement_ajout_seul(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    ev = EvenementConstat.objects.create(
        constat=constat,
        type=TypeEvenementConstat.SOUMIS,
        par=make_user(),
        le=timezone.now(),
        statut_avant=StatutConstat.BROUILLON,
        statut_apres=StatutConstat.SOUMIS,
    )
    ev.motif = "x"
    with pytest.raises(RegleMetierError):
        ev.save()
    with pytest.raises(RegleMetierError):
        ev.soft_delete(make_user())
    with pytest.raises(RegleMetierError):
        EvenementConstat.objects.filter(pk=ev.pk).update(motif="x")

import pytest
from django.db import transaction

from apps.constats.exceptions import ConstatValideError
from apps.constats.managers import prochain_numero_constat
from apps.constats.models import CauseConstat, Constat, Recommandation
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import MissionFigeeError
from apps.missions.models import Mission, StatutMission
from tests.constats.factories import ConstatFactory, fiche_anomalie
from tests.factories import MissionFactory

pytestmark = pytest.mark.django_db


def _valider(constat: Constat) -> Constat:
    constat.soumettre()
    constat.save()
    constat.valider()
    constat.save()
    return constat


def test_upsert_refuse_sur_constat(mission_en_xiv: Mission) -> None:
    constat = _valider(ConstatFactory(mission=mission_en_xiv))
    ecrase = Constat(
        mission=mission_en_xiv,
        reference=constat.reference,
        numero=constat.numero,
        titre="écrasé",
        entite=constat.entite,
        processus=constat.processus,
    )
    with pytest.raises(RegleMetierError):
        Constat.objects.bulk_create(
            [ecrase],
            update_conflicts=True,
            unique_fields=["mission", "reference"],
            update_fields=["titre"],
        )
    constat.refresh_from_db()
    assert constat.titre != "écrasé"


def test_upsert_refuse_sur_causes_et_recommandations(mission_en_xiv: Mission) -> None:
    constat = _valider(ConstatFactory(mission=mission_en_xiv))
    cause = constat.causes.get()
    reco = constat.recommandations.get()
    for modele, objet, champ in (
        (CauseConstat, cause, "description"),
        (Recommandation, reco, "libelle"),
    ):
        setattr(objet, champ, "écrasé")
        with pytest.raises(RegleMetierError):
            modele.objects.bulk_create(
                [objet], update_conflicts=True, unique_fields=["id"], update_fields=[champ]
            )


def test_m2m_fiches_refuse_sur_mission_suspendue(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    fiche = fiche_anomalie(mission_en_xiv)
    Mission.all_objects.filter(pk=mission_en_xiv.pk).update(statut=StatutMission.SUSPENDUE)
    with pytest.raises(MissionFigeeError), transaction.atomic():
        constat.fiches.remove(fiche)
    with pytest.raises(MissionFigeeError), transaction.atomic():
        constat.fiches.clear()
    with pytest.raises(MissionFigeeError), transaction.atomic():
        fiche.constats.clear()
    assert constat.fiches.count() == 1


@pytest.mark.django_db(transaction=True)
def test_numerotation_exige_une_transaction(mission_lancee: Mission) -> None:
    with pytest.raises(RuntimeError):
        prochain_numero_constat(mission_lancee.pk)
    with transaction.atomic():
        assert prochain_numero_constat(mission_lancee.pk) == 1


def test_rouverture_ne_modifie_que_le_statut(mission_en_xiv: Mission) -> None:
    constat = _valider(ConstatFactory(mission=mission_en_xiv))
    constat.refresh_from_db()
    constat.rouvrir()
    constat.titre = "glissé dans la réouverture"
    with pytest.raises(ConstatValideError):
        constat.save()
    constat.refresh_from_db()
    assert constat.statut == "VALIDE"
    constat.rouvrir()
    constat.save()
    constat.refresh_from_db()
    assert constat.statut == "BROUILLON"


def test_cause_et_reco_doivent_appartenir_a_la_mission_du_constat(
    mission_en_xiv: Mission,
) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    autre = MissionFactory()
    with pytest.raises(RegleMetierError):
        CauseConstat.objects.create(
            constat=constat, mission=autre, categorie="METHODES", description="x"
        )
    with pytest.raises(RegleMetierError):
        Recommandation.objects.create(constat=constat, mission=autre, libelle="x", priorite="HAUTE")


def test_fiche_d_une_autre_mission_refusee(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    constat.fiches.clear()
    etrangere = fiche_anomalie(MissionFactory())
    with pytest.raises(RegleMetierError), transaction.atomic():
        constat.fiches.add(etrangere)
    with pytest.raises(RegleMetierError), transaction.atomic():
        etrangere.constats.add(constat)


def test_niveau_a_des_choix() -> None:
    assert [c[0] for c in Constat._meta.get_field("niveau").choices or []] == [
        "FAIBLE",
        "MOYEN",
        "ELEVE",
    ]

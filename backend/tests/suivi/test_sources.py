from apps.constats.models import Recommandation
from apps.missions.models import Mission
from apps.recommandations.models import Action
from apps.suivi import sources


def test_sources_actions_du_plan(mission_en_suivi: Mission) -> None:
    plan = sources.actions_du_plan(mission_en_suivi)
    assert len(plan) == 3
    assert {a.id for a in plan} == set(
        Action.objects.filter(mission=mission_en_suivi).values_list("pk", flat=True)
    )
    premiere = plan[0]
    assert premiere.mission_id == mission_en_suivi.pk
    assert premiere.libelle and premiere.indicateur
    assert premiere.responsable_id is not None and premiere.echeance is not None
    assert Action._meta.label == sources.MODELE_ACTION


def test_sources_date_diffusion(mission_en_suivi: Mission) -> None:
    assert sources.date_diffusion(mission_en_suivi) is not None


def test_sources_date_diffusion_absente(mission_lancee: Mission) -> None:
    assert sources.date_diffusion(mission_lancee) is None


def test_sources_risque_accepte(mission_en_suivi: Mission) -> None:
    assert sources.CHAMP_RISQUE_ACCEPTE
    acceptees = sources.recommandations_a_risque_accepte(mission_en_suivi)
    assert acceptees.count() == 1
    avec_action = Recommandation.objects.filter(
        mission=mission_en_suivi, actions__isnull=False
    ).distinct()
    assert not set(acceptees) & set(avec_action)


def test_sources_signal_et_code_document() -> None:
    signal = sources.signal_rapport_diffuse()
    assert signal is not None
    assert sources.CODE_DOCUMENT_RAPPORT == "RAPPORT_FINAL"

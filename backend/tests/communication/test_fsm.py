import hashlib

import pytest
from django_fsm import TransitionNotAllowed, can_proceed

from apps.communication.exceptions import RapportFigeError
from apps.communication.models import (
    EvenementRapport,
    Rapport,
    StatutRapport,
    TypeEvenementRapport,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission
from tests.communication.factories import RapportFactory
from tests.factories import make_user

pytestmark = pytest.mark.django_db

S = StatutRapport
TRANSITIONS: dict[str, set[str]] = {
    "soumettre": {S.BROUILLON, S.RENVOYE},
    "valider": {S.SOUMIS},
    "renvoyer": {S.SOUMIS},
    "diffuser": {S.VALIDE},
    "remplacer": {S.DIFFUSE},
    "reinitialiser": {S.SOUMIS, S.VALIDE, S.RENVOYE},
}


def test_fsm_transitions_permises_et_interdites(mission_en_communication: Mission) -> None:
    for statut in StatutRapport.values:
        rapport = Rapport(mission=mission_en_communication, statut=statut)
        for nom, sources in TRANSITIONS.items():
            methode = getattr(rapport, nom)
            attendu = statut in sources
            assert can_proceed(methode) is attendu, f"{nom} depuis {statut}"
            if not attendu:
                with pytest.raises(TransitionNotAllowed):
                    methode()


def test_statut_saute_refuse_par_la_garde(rapport_brouillon: Rapport) -> None:
    """`protected=False` : l'écriture directe d'un statut hors D4 est refusée à la sauvegarde."""
    rapport_brouillon.statut = StatutRapport.VALIDE
    with pytest.raises(RegleMetierError):
        rapport_brouillon.save()
    assert Rapport.objects.get(pk=rapport_brouillon.pk).statut == StatutRapport.BROUILLON


def test_cycle_complet_par_les_transitions(rapport_brouillon: Rapport) -> None:
    rai = make_user()
    instantane = {"synthese": rapport_brouillon.synthese}
    rapport = rapport_brouillon

    rapport.soumettre()
    rapport.cycle = 1
    rapport.soumis_par = rai
    rapport.soumis_le = rapport.created_at
    rapport.instantane_soumis = instantane
    rapport.empreinte_soumise = hashlib.sha256(b"x").hexdigest()
    rapport.save(update_fields=[
        "statut", "cycle", "soumis_par", "soumis_le", "instantane_soumis", "empreinte_soumise",
    ])  # fmt: skip
    rapport.refresh_from_db()
    assert rapport.statut == StatutRapport.SOUMIS

    rapport.renvoyer()
    rapport.motif_renvoi = "Compléter la conclusion."
    rapport.save(update_fields=["statut", "motif_renvoi"])
    rapport.refresh_from_db()
    assert rapport.statut == StatutRapport.RENVOYE
    rapport.conclusion = "Conclusion complétée."  # rédaction à nouveau permise
    rapport.save(update_fields=["conclusion"])

    rapport.soumettre()
    rapport.cycle = 2
    rapport.save(update_fields=["statut", "cycle"])
    rapport.valider()
    rapport.valide_par = rai
    rapport.valide_le = rapport.created_at
    rapport.mode_signature = "CONFIRMATION"
    rapport.save(update_fields=["statut", "valide_par", "valide_le", "mode_signature"])
    rapport.refresh_from_db()
    assert rapport.statut == StatutRapport.VALIDE
    rapport.conclusion = "trop tard"
    with pytest.raises(RapportFigeError):
        rapport.save(update_fields=["conclusion"])

    rapport.diffuser()
    rapport.save(update_fields=["statut"])
    rapport.remplacer()
    rapport.save(update_fields=["statut"])
    assert Rapport.objects.get(pk=rapport.pk).statut == StatutRapport.REMPLACE


def test_sauvegarde_complete_apres_transition(rapport_brouillon: Rapport) -> None:
    """Un `save()` sans `update_fields` ne compare que ce qui a changé en mémoire."""
    rapport_brouillon.soumettre()
    rapport_brouillon.cycle = 1
    rapport_brouillon.soumis_par = make_user()
    rapport_brouillon.empreinte_soumise = "c" * 64
    rapport_brouillon.save()
    assert Rapport.objects.get(pk=rapport_brouillon.pk).statut == StatutRapport.SOUMIS


def test_transition_ne_peut_pas_modifier_les_sections(rapport_brouillon: Rapport) -> None:
    rapport_brouillon.soumettre()
    rapport_brouillon.cycle = 1
    rapport_brouillon.empreinte_soumise = "c" * 64
    rapport_brouillon.synthese = "glissée dans la transition"
    with pytest.raises(RegleMetierError):
        rapport_brouillon.save()
    assert Rapport.objects.get(pk=rapport_brouillon.pk).statut == StatutRapport.BROUILLON


def test_reinitialiser_rouvre_la_redaction(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication, fige=True, statut=S.VALIDE)
    rapport = Rapport.objects.get(pk=rapport.pk)
    rapport.reinitialiser()
    rapport.valide_par = None
    rapport.valide_le = None
    rapport.confirmation_validation = None
    rapport.mode_signature = ""
    rapport.motif_renvoi = ""
    rapport.save(update_fields=[
        "statut", "valide_par", "valide_le", "confirmation_validation", "mode_signature",
        "motif_renvoi",
    ])  # fmt: skip
    rapport.refresh_from_db()
    assert rapport.statut == StatutRapport.BROUILLON
    rapport.synthese = "reprise"
    rapport.save()


def test_journaliser_chaque_transition(rapport_brouillon: Rapport) -> None:
    rai = make_user()
    rapport_brouillon.soumettre()
    ev = EvenementRapport.journaliser(
        rapport_brouillon,
        TypeEvenementRapport.SOUMIS,
        par=rai,
        statut_avant=StatutRapport.BROUILLON,
    )
    assert (ev.statut_avant, ev.statut_apres) == (StatutRapport.BROUILLON, StatutRapport.SOUMIS)
    assert rapport_brouillon.evenements.count() == 1

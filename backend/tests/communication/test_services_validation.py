# ruff: noqa: F811
from typing import Any
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection

from apps.communication.models import (
    CategorieDestinataire,
    DestinataireDiffusion,
    EvenementRapport,
    Rapport,
    StatutRapport,
)
from apps.communication.services.soumission import soumettre_rapport
from apps.communication.services.validation import (
    renvoyer_rapport,
    valider_rapport,
    version_finale,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission, RoleMission, StatutEtape
from apps.missions.services.etapes import ACTIONS_RESERVEES, exiger_action_generique, valider_etape
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.parametres import modifier_mode
from apps.signatures.services import empreinte, verifier
from apps.users.models import User
from tests.communication.support_t8 import (  # noqa: F401
    XV_A_XVII,
    admin,
    creer_version,
    dg,
    rapport_soumis_reel,
    rapport_valide,
    signataire_factice,
)
from tests.missions.conftest import affecter
from tests.signatures.fakes import SignataireFactice


def _etape18(rapport: Rapport) -> EtapeMission:
    return EtapeMission.objects.get(mission_id=rapport.mission_id, numero=18)


def test_validation_confirme_fige_et_valide_xviii(rapport_soumis_reel: Rapport, rai: User) -> None:
    r = valider_rapport(rapport_soumis_reel, by=rai, adresse_ip="10.0.0.7")
    assert r.statut == StatutRapport.VALIDE and r.valide_par == rai and r.valide_le is not None
    assert r.mode_signature == "CONFIRMATION"
    c = r.confirmation_validation
    assert c is not None and verifier(c)
    assert c.type_document == TypeDocumentSignable.VALIDATION_RAPPORT
    assert c.signataire == rai and c.adresse_ip == "10.0.0.7"
    assert c.donnees["empreinte_soumise"] == r.empreinte_soumise and c.donnees["cycle"] == 1
    assert "Responsable de l'Audit Interne" in c.texte and r.mission.reference in c.texte
    assert c.empreinte == empreinte(c.texte, c.donnees)
    assert _etape18(r).statut == StatutEtape.VALIDEE
    evenement = EvenementRapport.objects.get(rapport=r, type="VALIDE")
    assert (evenement.statut_avant, evenement.statut_apres) == ("SOUMIS", "VALIDE")
    en_base = Rapport.objects.get(pk=r.pk)
    assert en_base.confirmation_validation_id == c.pk and en_base.statut == "VALIDE"


def test_validation_preremplit_les_destinataires(
    rapport_soumis_reel: Rapport, rai: User, chef: User, audite_affecte: User, dg: User
) -> None:
    valider_rapport(rapport_soumis_reel, by=rai)
    categories = dict(
        DestinataireDiffusion.objects.filter(rapport=rapport_soumis_reel).values_list(
            "utilisateur_id", "categorie"
        )
    )
    assert categories == {
        dg.pk: CategorieDestinataire.DG,
        audite_affecte.pk: CategorieDestinataire.AUDITE,
        chef.pk: CategorieDestinataire.EQUIPE,
    }


def test_seul_le_rai_valide(
    rapport_soumis_reel: Rapport, chef: User, auditeur_mission: User, admin: User, dg: User
) -> None:
    for intrus in (chef, auditeur_mission, admin, dg):
        with pytest.raises(PermissionDenied):
            valider_rapport(rapport_soumis_reel, by=intrus)
    rapport_soumis_reel.refresh_from_db()
    assert rapport_soumis_reel.statut == StatutRapport.SOUMIS


def test_superviseur_ne_valide_pas(rapport_soumis_reel: Rapport) -> None:
    from tests.factories import make_user

    superviseur = make_user("AUDITEUR")
    affecter(rapport_soumis_reel.mission, superviseur, RoleMission.SUPERVISEUR)
    with pytest.raises(PermissionDenied):
        valider_rapport(rapport_soumis_reel, by=superviseur)
    with pytest.raises(PermissionDenied):
        renvoyer_rapport(rapport_soumis_reel, motif="Non.", by=superviseur)


def test_auto_validation_refusee(rapport_soumis_reel: Rapport, rai: User, chef: User) -> None:
    """Le RAI qui aurait soumis le rapport ne peut pas le valider (soumis_par = valideur)."""
    with connection.cursor() as c:
        c.execute(
            "UPDATE communication_rapport SET soumis_par_id = %s WHERE id = %s",
            [rai.pk, rapport_soumis_reel.pk],
        )
    with pytest.raises(RegleMetierError, match="ne peut pas être la personne qui a soumis"):
        valider_rapport(rapport_soumis_reel, by=rai)
    rapport_soumis_reel.refresh_from_db()
    assert rapport_soumis_reel.statut == StatutRapport.SOUMIS


def test_validation_generique_xviii_refusee(rapport_soumis_reel: Rapport, rai: User) -> None:
    etape = _etape18(rapport_soumis_reel)
    assert etape.statut == StatutEtape.TERMINEE
    assert "VALIDER" in ACTIONS_RESERVEES[18]
    with pytest.raises(RegleMetierError, match="écran du rapport"):
        exiger_action_generique(etape, "VALIDER")
    # Défense en profondeur : l'appel direct du service est refusé par le récepteur.
    with pytest.raises(RegleMetierError, match="Validez le rapport depuis l'écran du rapport"):
        valider_etape(etape, by=rai)
    assert _etape18(rapport_soumis_reel).statut == StatutEtape.TERMINEE


def test_mode_fige_a_la_validation(
    rapport_soumis_reel: Rapport, rai: User, admin: User, signataire_factice: SignataireFactice
) -> None:
    modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION_ET_SIGNATURE", by=admin)
    r = valider_rapport(rapport_soumis_reel, by=rai)
    assert r.mode_signature == "CONFIRMATION_ET_SIGNATURE" and r.confirmation_validation
    modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION", by=admin)
    assert Rapport.objects.get(pk=r.pk).mode_signature == "CONFIRMATION_ET_SIGNATURE"


def test_mode_signature_electronique_seule_sans_confirmation(
    rapport_soumis_reel: Rapport, rai: User, admin: User, signataire_factice: SignataireFactice
) -> None:
    modifier_mode("VALIDATION_RAPPORT", mode="SIGNATURE_ELECTRONIQUE", by=admin)
    r = valider_rapport(rapport_soumis_reel, by=rai)
    assert r.mode_signature == "SIGNATURE_ELECTRONIQUE"
    assert r.confirmation_validation is None and r.statut == StatutRapport.VALIDE


def test_renvoi_puis_resoumission(rapport_soumis_reel: Rapport, rai: User, chef: User) -> None:
    with pytest.raises(RegleMetierError, match="motif"):
        renvoyer_rapport(rapport_soumis_reel, motif="  ", by=rai)
    r = renvoyer_rapport(rapport_soumis_reel, motif="Précisez la conclusion.", by=rai)
    assert r.statut == StatutRapport.RENVOYE and r.motif_renvoi == "Précisez la conclusion."
    assert _etape18(r).statut == StatutEtape.RENVOYEE
    evenement = EvenementRapport.objects.get(rapport=r, type="RENVOYE")
    assert (evenement.statut_avant, evenement.statut_apres) == ("SOUMIS", "RENVOYE")
    assert evenement.motif == "Précisez la conclusion."
    # Un rapport renvoyé ne se valide pas.
    with pytest.raises(RegleMetierError, match="n'est pas soumis"):
        valider_rapport(r, by=rai)
    r2 = soumettre_rapport(r, by=chef)
    assert r2.cycle == 2 and _etape18(r2).statut == StatutEtape.TERMINEE
    r3 = valider_rapport(r2, by=rai)
    assert r3.confirmation_validation is not None
    assert r3.confirmation_validation.donnees["cycle"] == 2


def test_renvoyer_exige_le_rai(rapport_soumis_reel: Rapport, chef: User) -> None:
    with pytest.raises(PermissionDenied):
        renvoyer_rapport(rapport_soumis_reel, motif="Non.", by=chef)


def test_validation_refusee_si_empreinte_alteree(rapport_soumis_reel: Rapport, rai: User) -> None:
    with connection.cursor() as c:
        c.execute(
            "UPDATE communication_rapport SET empreinte_soumise = %s WHERE id = %s",
            ["a" * 64, rapport_soumis_reel.pk],
        )
    with pytest.raises(RegleMetierError, match="empreinte"):
        valider_rapport(rapport_soumis_reel, by=rai)
    assert _etape18(rapport_soumis_reel).statut == StatutEtape.TERMINEE


def test_validation_refusee_si_instantane_altere(rapport_soumis_reel: Rapport, rai: User) -> None:
    with connection.cursor() as c:
        c.execute(
            "UPDATE communication_rapport SET instantane_soumis = %s::jsonb WHERE id = %s",
            ['{"synthese": "Falsifiée"}', rapport_soumis_reel.pk],
        )
    with pytest.raises(RegleMetierError, match="empreinte"):
        valider_rapport(rapport_soumis_reel, by=rai)


def test_validation_refusee_hors_communication(rapport_soumis_reel: Rapport, rai: User) -> None:
    Mission.objects.filter(pk=rapport_soumis_reel.mission_id).update(statut="RAPPORT_DIFFUSE")
    with pytest.raises(RegleMetierError, match="phase"):
        valider_rapport(rapport_soumis_reel, by=rai)


def test_validation_deux_fois_refusee(rapport_valide: Rapport, rai: User) -> None:
    with pytest.raises(RegleMetierError, match="n'est pas soumis"):
        valider_rapport(rapport_valide, by=rai)


def test_version_finale_suit_la_confirmation(rapport_valide: Rapport) -> None:
    assert version_finale(rapport_valide) is None
    creer_version(rapport_valide, statut="EN_COURS")
    assert version_finale(rapport_valide) is None
    v1 = creer_version(rapport_valide)
    assert version_finale(rapport_valide) == v1
    v2 = creer_version(rapport_valide)
    assert version_finale(rapport_valide) == v2
    autre = creer_version(rapport_valide, confirmation_id=None)
    assert version_finale(rapport_valide) == v2 and autre.confirmation_id is None


def test_generation_automatique_apres_validation(
    rapport_soumis_reel: Rapport, rai: User, django_capture_on_commit_callbacks: Any
) -> None:
    with patch("apps.documents.services.generation.demander_generation") as demander:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            valider_rapport(rapport_soumis_reel, by=rai)
        demander.assert_not_called()  # jamais avant la validation de la transaction
        for callback in callbacks:
            callback()
    types = [appel.kwargs["type_document"] for appel in demander.call_args_list]
    assert types == ["RAPPORT_FINAL", "NOTE_SYNTHETIQUE"]
    assert all(a.kwargs["objet_id"] == rapport_soumis_reel.pk for a in demander.call_args_list)


def test_echec_de_generation_ne_bloque_pas(
    rapport_soumis_reel: Rapport, rai: User, django_capture_on_commit_callbacks: Any
) -> None:
    with patch(
        "apps.documents.services.generation.demander_generation", side_effect=RuntimeError("x")
    ) as demander:
        with django_capture_on_commit_callbacks(execute=True):
            r = valider_rapport(rapport_soumis_reel, by=rai)
    assert demander.call_count == 2
    assert Rapport.objects.get(pk=r.pk).statut == StatutRapport.VALIDE

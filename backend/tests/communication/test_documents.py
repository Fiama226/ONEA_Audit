"""Types de documents de la communication (lot 7, T9) : contrats, fournisseurs, gabarits."""

import datetime
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from django.db import connection
from django.utils import timezone

from apps.communication.models import Rapport, RapportProvisoire
from apps.communication.services.assemblage import assembler
from apps.constats.models import Constat
from apps.core.exceptions import RegleMetierError
from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.contrats import EXEMPLE_COMMUN, ecarts_contexte
from apps.documents.moteur.provisoires import construire_gabarit_provisoire
from apps.documents.moteur.registre import type_document
from apps.missions.models import Mission, Reunion, TypeReunion
from apps.signatures.models import TypeDocumentSignable
from apps.users.models import Role, User
from tests.communication.factories import RapportProvisoireFactory
from tests.factories import ConfirmationFactory, ReunionFactory, make_user

CODES = (
    "PV_CLOTURE",
    "RAPPORT_PROVISOIRE",
    "RAPPORT_FINAL",
    "NOTE_SYNTHETIQUE",
    "FICHE_SUIVI_MISSION",
)
RACINE_DOCS = Path(__file__).resolve().parents[3] / "docs" / "documents" / "contrats"


def _valider(rapport: Rapport, correction: dict[str, Any] | None = None) -> Rapport:
    """Rapport VALIDE (transitions réelles) dont la confirmation porte l'instantané assemblé."""
    instantane = assembler(rapport, provisoire=False)
    if correction:
        instantane["rapport"].update(correction)
    rai = make_user(Role.RAI)
    rapport.soumettre()
    rapport.cycle = 1
    rapport.soumis_par = rai
    rapport.soumis_le = timezone.now()
    rapport.instantane_soumis = instantane
    rapport.empreinte_soumise = "a" * 64
    rapport.save()
    confirmation = ConfirmationFactory(
        objet=rapport,
        type_document=TypeDocumentSignable.VALIDATION_RAPPORT,
        signataire=rai,
        donnees=instantane | {"cycle": 1, "empreinte_soumise": rapport.empreinte_soumise},
    )
    rapport.valider()
    rapport.valide_par = rai
    rapport.valide_le = timezone.now()
    rapport.confirmation_validation = confirmation
    rapport.save()
    return rapport


def _transiter(rapport: Rapport, transition: str) -> None:
    getattr(rapport, transition)()
    rapport.save()


@pytest.fixture
def rapport_valide(rapport_redige: Rapport) -> Rapport:
    return _valider(rapport_redige)


@pytest.fixture
def pv_cloture(mission_en_communication: Mission) -> Reunion:
    reunion: Reunion = ReunionFactory(
        mission=mission_en_communication,
        type=TypeReunion.CLOTURE,
        tenue_le=timezone.now(),
        participants_externes="M. Traoré — Cabinet\n\n",
    )
    return reunion


@pytest.fixture
def provisoire(rapport_redige: Rapport) -> RapportProvisoire:
    instantane = assembler(rapport_redige, provisoire=True)
    provisoire: RapportProvisoire = RapportProvisoireFactory(
        rapport=rapport_redige,
        instantane=instantane,
        date_limite_reponses=datetime.date(2026, 12, 31),
    )
    return provisoire


def _sans_none(valeur: Any) -> bool:
    if valeur is None:
        return False
    if isinstance(valeur, dict):
        return all(_sans_none(v) for v in valeur.values())
    if isinstance(valeur, list):
        return all(_sans_none(v) for v in valeur)
    return True


@pytest.fixture
def sources(
    rapport_valide: Rapport, pv_cloture: Reunion, provisoire: RapportProvisoire
) -> dict[str, Any]:
    return {
        "PV_CLOTURE": pv_cloture,
        "RAPPORT_PROVISOIRE": provisoire,
        "RAPPORT_FINAL": rapport_valide,
        "NOTE_SYNTHETIQUE": rapport_valide,
        "FICHE_SUIVI_MISSION": rapport_valide.mission,
    }


@pytest.fixture
def contexte_de(sources: dict[str, Any]) -> Callable[[str], dict[str, Any]]:
    def _contexte(code: str) -> dict[str, Any]:
        t = type_document(code)
        return dict(EXEMPLE_COMMUN) | t.fournisseur.contexte(sources[code])

    return _contexte


def test_contexte_rapport_final_depuis_donnees_signees(
    rapport_valide: Rapport, constat_valide: Constat
) -> None:
    fournisseur = type_document("RAPPORT_FINAL").fournisseur
    avant = fournisseur.contexte(rapport_valide)
    assert constat_valide.titre in {c["titre"] for c in avant["constats"]}
    with connection.cursor() as curseur:  # SQL direct : la garde du modèle gèle le constat
        curseur.execute(
            "UPDATE constats_constat SET titre = %s WHERE id = %s",
            ["Titre modifié après validation", constat_valide.pk],
        )
    apres = fournisseur.contexte(Rapport.objects.get(pk=rapport_valide.pk))
    assert apres == avant
    assert "Titre modifié après validation" not in str(apres)
    assert apres["validation"]["empreinte"] == rapport_valide.confirmation_validation.empreinte


def test_rapport_non_valide_refuse_le_contexte(rapport_redige: Rapport) -> None:
    fournisseur = type_document("RAPPORT_FINAL").fournisseur
    assert fournisseur.raison_non_generable(rapport_redige) == "Le rapport n'est pas encore validé."
    with pytest.raises(RegleMetierError):
        fournisseur.contexte(rapport_redige)


@pytest.mark.parametrize("code", ["RAPPORT_FINAL", "NOTE_SYNTHETIQUE"])
def test_regeneration_refusee_apres_diffusion(code: str, rapport_valide: Rapport) -> None:
    fournisseur = type_document(code).fournisseur
    assert fournisseur.raison_non_generable(rapport_valide) is None
    for transition in ("diffuser", "remplacer"):
        _transiter(rapport_valide, transition)
        assert fournisseur.raison_non_generable(rapport_valide) == (
            "Le rapport est diffusé : émettez un rapport corrigé."
        )


def test_rapport_corrige_porte_la_mention(rapport_redige: Rapport) -> None:
    rapport = _valider(rapport_redige, {"corrige_de": 1, "motif_correction": "Erreur de date"})
    contexte = type_document("RAPPORT_FINAL").fournisseur.contexte(rapport)
    assert contexte["rapport"]["mention_correction"] == (
        "Rapport corrigé — remplace le rapport 1. Motif : Erreur de date"
    )


def test_pv_cloture_exige_reunion_tenue(mission_en_communication: Mission) -> None:
    reunion = ReunionFactory(mission=mission_en_communication, type=TypeReunion.CLOTURE)
    fournisseur = type_document("PV_CLOTURE").fournisseur
    assert fournisseur.raison_non_generable(reunion) == (
        "Marquez la réunion de clôture comme tenue avant de générer le PV."
    )
    Reunion.objects.filter(pk=reunion.pk).update(tenue_le=timezone.now())
    reunion.refresh_from_db()
    assert fournisseur.raison_non_generable(reunion) is None


def test_pv_cloture_modalites_et_constats(
    constat_valide: Constat, pv_cloture: Reunion, provisoire: RapportProvisoire
) -> None:
    contexte = type_document("PV_CLOTURE").fournisseur.contexte(pv_cloture)
    assert contexte["modalites"]["date_limite_reponses"] == "31/12/2026"
    assert contexte["reunion"]["participants_externes"] == ["M. Traoré — Cabinet"]
    assert [c["reference"] for c in contexte["constats_presentes"]] == [constat_valide.reference]


@pytest.mark.parametrize("code", CODES)
def test_contexte_sans_none(code: str, contexte_de: Callable[[str], dict[str, Any]]) -> None:
    assert _sans_none(contexte_de(code))


@pytest.mark.parametrize("code", CODES)
def test_contexte_conforme_au_contrat(
    code: str, contexte_de: Callable[[str], dict[str, Any]]
) -> None:
    assert ecarts_contexte(type_document(code).contrat, contexte_de(code)) == []


@pytest.mark.parametrize("code", CODES)
def test_gabarit_provisoire_valide(code: str) -> None:
    t = type_document(code)
    balises = analyser_gabarit(
        construire_gabarit_provisoire(t), t.contrat, nom_fichier="p.docx", taille_max_mo=10
    )
    assert "mission" in balises


def test_documentation_contrats_a_jour() -> None:
    for code in (*CODES, "PLAN_ACTIONS"):
        assert (RACINE_DOCS / f"{code}.md").exists()


@pytest.mark.parametrize("code", CODES)
def test_contextes_requetes_bornees(
    code: str, sources: dict[str, Any], django_assert_max_num_queries: Any
) -> None:
    fournisseur = type_document(code).fournisseur
    with django_assert_max_num_queries(25):
        fournisseur.contexte(sources[code])


def test_droits_fournisseurs(
    rapport_valide: Rapport,
    pv_cloture: Reunion,
    provisoire: RapportProvisoire,
    mission_en_communication: Mission,
    chef: User,
    audite_affecte: User,
    rai: User,
) -> None:
    Mission.objects.filter(pk=mission_en_communication.pk).update(
        ordre_mission_emis_le=timezone.now()
    )
    dg = make_user(Role.DG)
    admin = make_user(Role.ADMIN)
    final = type_document("RAPPORT_FINAL").fournisseur
    note = type_document("NOTE_SYNTHETIQUE").fournisseur
    prov = type_document("RAPPORT_PROVISOIRE").fournisseur
    pv = type_document("PV_CLOTURE").fournisseur
    fiche = type_document("FICHE_SUIVI_MISSION").fournisseur

    # L'audité reçoit le rapport provisoire et le PV de clôture, pas le rapport ni la note.
    assert prov.peut_consulter(audite_affecte, provisoire)
    assert pv.peut_consulter(audite_affecte, pv_cloture)
    assert not final.peut_consulter(audite_affecte, rapport_valide)
    assert not note.peut_consulter(audite_affecte, rapport_valide)
    assert not fiche.peut_consulter(audite_affecte, mission_en_communication)
    # Équipe : tout. DG et administrateur : aucune route `/documents/` (D13).
    for fournisseur, objet in (
        (final, rapport_valide),
        (note, rapport_valide),
        (prov, provisoire),
        (pv, pv_cloture),
        (fiche, mission_en_communication),
    ):
        assert fournisseur.peut_consulter(rai, objet)
        assert fournisseur.peut_consulter(chef, objet)
        assert not fournisseur.peut_consulter(dg, objet)
        assert not fournisseur.peut_consulter(admin, objet)
        assert fournisseur.peut_generer(rai, objet)
        assert not fournisseur.peut_generer(audite_affecte, objet)
    # Après diffusion, l'audité voit le rapport final et la note (missions affectées).
    _transiter(rapport_valide, "diffuser")
    assert final.peut_consulter(audite_affecte, rapport_valide)
    assert note.peut_consulter(audite_affecte, rapport_valide)
    assert not final.peut_consulter(dg, rapport_valide)


def test_objets_de_mission(
    rapport_valide: Rapport,
    pv_cloture: Reunion,
    provisoire: RapportProvisoire,
    mission_en_communication: Mission,
) -> None:
    assert type_document("RAPPORT_FINAL").fournisseur.objets_de_mission(
        mission_en_communication
    ) == [rapport_valide]
    assert type_document("RAPPORT_PROVISOIRE").fournisseur.objets_de_mission(
        mission_en_communication
    ) == [provisoire]
    assert type_document("PV_CLOTURE").fournisseur.objets_de_mission(mission_en_communication) == [
        pv_cloture
    ]

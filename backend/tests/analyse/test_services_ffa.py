import pytest

from apps.analyse.models import ForceFaiblesse
from apps.analyse.services import forces_faiblesses as ffa
from apps.analyse.services import marc
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, RisqueMission
from apps.users.models import User

pytestmark = pytest.mark.django_db

MSG_LIEE = "Cette ligne suit la matrice MARC : modifiez la ligne MARC."


def test_ffa_suit_l_evaluation(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    assert ffa.synchroniser(ligne, by=chef) is None
    marc.modifier_ligne_marc(
        ligne, by=chef, controle_existant="Double signature", evaluation="ADEQUATE"
    )
    ff = ligne.forces_faiblesses.get()
    assert (ff.type, ff.libelle) == ("FORCE", "Double signature")
    marc.modifier_ligne_marc(ligne, by=chef, evaluation="INSUFFISANTE")
    ff2 = ligne.forces_faiblesses.get()
    assert ff2.pk == ff.pk and ff2.type == "FAIBLESSE"
    marc.modifier_ligne_marc(ligne, by=chef, evaluation="")
    assert ligne.forces_faiblesses.count() == 0
    # Cycle D8 : réévaluation après effacement, sans IntegrityError.
    marc.modifier_ligne_marc(ligne, by=chef, evaluation="ADEQUATE")
    assert ligne.forces_faiblesses.get().type == "FORCE"


def test_ffa_controle_absent(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(
        mission_en_analyse, risque=risque_eleve, by=chef, evaluation="ABSENTE"
    )
    ff = ligne.forces_faiblesses.get()
    assert ff.type == "FAIBLESSE"
    assert ff.libelle == "Absence de contrôle : Garantir l'exactitude des paiements."


def test_libelle_reformule_conserve(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="Contrôle",
        evaluation="ADEQUATE",
    )
    ff = ligne.forces_faiblesses.get()
    ffa.modifier_force_faiblesse(ff, by=chef, libelle="Reformulé", consequence="Aucune")
    marc.modifier_ligne_marc(ligne, by=chef, evaluation="INSUFFISANTE")
    ff.refresh_from_db()
    assert (ff.libelle, ff.consequence, ff.type) == ("Reformulé", "Aucune", "FAIBLESSE")


def test_ffa_liee_non_retirable(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    ligne = marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="Contrôle",
        evaluation="ADEQUATE",
    )
    ff = ligne.forces_faiblesses.get()
    with pytest.raises(RegleMetierError, match="suit la matrice MARC"):
        ffa.retirer_force_faiblesse(ff, by=chef)
    with pytest.raises(RegleMetierError) as e:
        ffa.modifier_force_faiblesse(ff, by=chef, type="FAIBLESSE")
    assert e.value.message == MSG_LIEE


def test_ffa_manuelle_crud(mission_en_analyse: Mission, chef: User) -> None:
    ff = ffa.ajouter_force_faiblesse(
        mission_en_analyse, type="FAIBLESSE", libelle="Archivage absent", by=chef
    )
    assert ff.ligne_marc_id is None
    ffa.modifier_force_faiblesse(ff, by=chef, type="FORCE", consequence="x")
    ff.refresh_from_db()
    assert ff.type == "FORCE"
    ffa.retirer_force_faiblesse(ff, by=chef)
    assert not ForceFaiblesse.objects.filter(pk=ff.pk).exists()


def test_ffa_manuelle_libelle_obligatoire(mission_en_analyse: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError) as e:
        ffa.ajouter_force_faiblesse(mission_en_analyse, type="FORCE", libelle=" ", by=chef)
    assert "libelle" in e.value.errors

"""Tests prévus : création, modification par groupe (D5), suppression, compléments (D6)."""

from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.core.services import enregistrer, refuser, relire
from apps.missions.acces import role_dans_mission
from apps.missions.models import ROLES_INTERVENANTS, Mission, RisqueMission
from apps.users.models import User

from ..droits import ETAPE_COMPLEMENTAIRES, ETAPE_CONTENU, ETAPE_RESSOURCES
from ..managers import prochain_numero
from ..models import FicheDeTest, ProgrammeDeTravail, StatutFiche, StatutTest, TestPrevu
from ._fenetres_programme import Droit, exiger_droit, exiger_fenetre, verrouiller

CHAMPS_CONTENU = frozenset(
    {
        "libelle",
        "objectif_test",
        "nature",
        "procedure",
        "population",
        "taille_echantillon",
        "methode_selection",
        "risque_mission",
    }
)
CHAMPS_RESSOURCES = frozenset(
    {"auditeur", "charge_prevue_jours", "date_debut_prevue", "date_fin_prevue"}
)
MSG_AUDITEUR = "L'auditeur doit être un intervenant de la mission."
MSG_RISQUE = "Ce risque n'appartient pas à la mission."
MSG_MOTIF = "Le motif est obligatoire."


def _inconnus(champs: dict[str, Any]) -> None:
    inconnus = set(champs) - CHAMPS_CONTENU - CHAMPS_RESSOURCES
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")


def _renseigne(valeur: Any) -> bool:
    return valeur not in (None, "")


def _exiger_fenetres(
    mission: Mission, by: User, *, complementaire: bool, contenu: bool, ressources: bool
) -> None:
    """Droit puis fenêtre de chaque groupe touché : VIII / IX, ou XII pour un complément."""
    if complementaire:
        exiger_droit(by, mission, Droit.COMPLEMENTAIRES)
        exiger_fenetre(mission.pk, ETAPE_COMPLEMENTAIRES)
        return
    if contenu or not ressources:
        exiger_droit(by, mission, Droit.CONTENU)
    if ressources:
        exiger_droit(by, mission, Droit.RESSOURCES)
    if contenu or not ressources:
        exiger_fenetre(mission.pk, ETAPE_CONTENU)
    if ressources:
        exiger_fenetre(mission.pk, ETAPE_RESSOURCES)


def _controler(test: TestPrevu, mission: Mission) -> None:
    """Références à la mission et valeurs : tous les défauts sont remontés ensemble."""
    erreurs: dict[str, str] = {}
    test.libelle = test.libelle.strip()
    for champ in ("objectif_test", "procedure", "population"):
        setattr(test, champ, getattr(test, champ).strip())
    auditeur = test.auditeur
    if auditeur is not None and role_dans_mission(auditeur, mission) not in ROLES_INTERVENANTS:
        erreurs["auditeur"] = MSG_AUDITEUR
    if (
        test.risque_mission_id is not None
        and not RisqueMission.objects.filter(pk=test.risque_mission_id, mission=mission).exists()
    ):
        erreurs["risque_mission"] = MSG_RISQUE
    if test.charge_prevue_jours is not None and test.charge_prevue_jours < Decimal(0):
        erreurs["charge_prevue_jours"] = "La charge prévue ne peut pas être négative."
    debut, fin = test.date_debut_prevue, test.date_fin_prevue
    if debut is not None and fin is not None and fin < debut:
        erreurs["date_fin_prevue"] = "La date de fin ne peut pas précéder la date de début."
    if erreurs:
        raise refuser("Données invalides.", **erreurs)


def _creer(
    programme: ProgrammeDeTravail, *, by: User, complementaire: bool, champs: dict[str, Any]
) -> TestPrevu:
    _inconnus(champs)
    mission = verrouiller(programme.mission)
    ressources = any(_renseigne(champs.get(c)) for c in CHAMPS_RESSOURCES)
    _exiger_fenetres(
        mission, by, complementaire=complementaire, contenu=True, ressources=ressources
    )
    programme = relire(programme)
    test = TestPrevu(mission=mission, programme=programme, complementaire=complementaire)
    for champ, valeur in champs.items():
        setattr(test, champ, valeur)
    _controler(test, mission)
    # Le numéro est attribué en dernier, sous le verrou de la mission : un refus n'en brûle aucun.
    test.numero = prochain_numero(TestPrevu, mission.pk)
    test.code = f"T-{test.numero:02d}"
    test.ordre = test.numero
    enregistrer(test, by=by, creation=True)
    return test


@transaction.atomic
def creer_test(
    programme: ProgrammeDeTravail, *, libelle: str, nature: str, by: User, **champs: Any
) -> TestPrevu:
    champs = {"libelle": libelle, "nature": nature, **champs}
    return _creer(programme, by=by, complementaire=False, champs=champs)


@transaction.atomic
def creer_test_complementaire(
    programme: ProgrammeDeTravail, *, by: User, **champs: Any
) -> TestPrevu:
    """Test ajouté pendant l'étape XII par le RAI ou le chef (D6), sans rouvrir VIII."""
    champs.setdefault("libelle", "")
    return _creer(programme, by=by, complementaire=True, champs=champs)


@transaction.atomic
def modifier_test(test: TestPrevu, *, by: User, **changes: Any) -> TestPrevu:
    _inconnus(changes)
    mission = verrouiller(test.mission)
    test = relire(test)
    if test.statut != StatutTest.PREVU:
        raise refuser("Ce test est abandonné : il ne peut plus être modifié.")
    modifies = {c: v for c, v in changes.items() if getattr(test, c) != v}
    if not modifies:
        return test
    _exiger_fenetres(
        mission,
        by,
        complementaire=test.complementaire,
        contenu=bool(modifies.keys() & CHAMPS_CONTENU),
        ressources=bool(modifies.keys() & CHAMPS_RESSOURCES),
    )
    for champ, valeur in modifies.items():
        setattr(test, champ, valeur)
    _controler(test, mission)
    enregistrer(test, by=by)
    return test


@transaction.atomic
def supprimer_test(test: TestPrevu, *, by: User) -> None:
    mission = verrouiller(test.mission)
    test = relire(test)
    _exiger_fenetres(
        mission, by, complementaire=test.complementaire, contenu=True, ressources=False
    )
    if FicheDeTest.objects.filter(test=test).exists():
        raise refuser(f"Le test {test.code} a une fiche : il ne peut pas être supprimé.")
    test.soft_delete(by)


@transaction.atomic
def abandonner_test(test: TestPrevu, *, motif: str, by: User) -> TestPrevu:
    """Abandon d'un test prévu pendant XII (D6) : motif obligatoire, aucune fiche validée."""
    mission = verrouiller(test.mission)
    exiger_droit(by, mission, Droit.COMPLEMENTAIRES)
    exiger_fenetre(mission.pk, ETAPE_COMPLEMENTAIRES)
    test = relire(test)
    if test.statut != StatutTest.PREVU:
        raise refuser(f"Le test {test.code} est déjà abandonné.")
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    if FicheDeTest.objects.filter(test=test, statut=StatutFiche.VALIDE).exists():
        raise refuser(
            f"La fiche du test {test.code} est validée : rouvrez-la avant d'abandonner le test."
        )
    test.statut = StatutTest.ABANDONNE
    test.motif_abandon = motif
    enregistrer(test, by=by)
    return test

"""Gardes de gel de l'accomplissement (D5, D7, D8 du plan du lot 6).

Comme celles du lot 3, elles lisent l'état EN BASE (jamais l'instance seule) : une instance est
comparée à sa ligne, groupe de champs par groupe de champs. Elles sont appelées par
`exiger_travaux_ouverts()` des modèles, donc par `save()`, `update`, `bulk_update` et
`bulk_create`.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from apps.missions.gardes import exiger_etape_ouverte

from .exceptions import FicheValideeError, FicheVerrouilleeError, PieceImmuableError
from .models import FicheDeTest, PieceJustificative, StatutFiche, TestPrevu

ETAPE_CONTENU = 8
ETAPE_RESSOURCES = 9
ETAPE_FICHES = 12
ETAPE_VALIDATION_PREUVES = 13

# Champs d'un test prévu (D5). Tout champ non listé ailleurs relève du contenu (étape VIII).
CHAMPS_RESSOURCES: frozenset[str] = frozenset(
    {"auditeur", "charge_prevue_jours", "date_debut_prevue", "date_fin_prevue"}
)
CHAMPS_CONTENU: frozenset[str] = frozenset(
    {
        "libelle",
        "objectif_test",
        "nature",
        "procedure",
        "population",
        "taille_echantillon",
        "methode_selection",
        "risque_mission",
        "programme",
        "mission",
        "code",
        "numero",
        "complementaire",
        "ordre",
        "deleted_at",
    }
)
# Abandon d'un test : fenêtre de l'étape XII (D6).
CHAMPS_ABANDON: frozenset[str] = frozenset({"statut", "motif_abandon"})

CHAMPS_TECHNIQUES: frozenset[str] = frozenset({"updated_at", "updated_by"})

# Transitions d'une fiche : portées par XII (soumission) ou XIII (validation, renvoi, réouverture).
CHAMPS_TRANSITION_FICHE: frozenset[str] = frozenset(
    {"statut", "soumise_par", "soumise_le", "validee_par", "validee_le", "motif_renvoi"}
)

# Champs immuables d'une pièce déposée (D8), plus son rattachement.
CHAMPS_FICHIER: frozenset[str] = frozenset(
    {
        "cle_stockage",
        "empreinte_sha256",
        "taille_octets",
        "type_mime",
        "nom_fichier_original",
        "deposee_par",
        "deposee_le",
        "fiche",
        "mission",
        "numero",
    }
)

# Pk de la fiche en cours de réouverture (seule écriture permise sur une fiche VALIDE).
_REOUVERTURE: ContextVar[UUID | None] = ContextVar("reouverture_fiche", default=None)


@contextmanager
def reouverture(fiche_id: UUID) -> Iterator[None]:
    """Autorise l'écriture de la réouverture d'une fiche validée dans ce bloc."""
    jeton = _REOUVERTURE.set(fiche_id)
    try:
        yield
    finally:
        _REOUVERTURE.reset(jeton)


def champs_ecrits(champs: Iterable[str]) -> set[str]:
    """Noms de champs de modèle visés (`fiche_id` et `fiche` désignent le même champ)."""
    return {c.removesuffix("_id") for c in champs} | set(champs)


def champs_modifies(objet: Any, en_base: Any) -> set[str]:
    """Champs concrets dont la valeur diffère entre l'instance et sa ligne en base."""
    return {
        f.name
        for f in type(objet)._meta.concrete_fields
        if f.name not in CHAMPS_TECHNIQUES
        and getattr(objet, f.attname) != getattr(en_base, f.attname)
    }


def controler_test(test: TestPrevu) -> None:
    """Gel D5 : contenu -> VIII, ressources -> IX, abandon -> XII ; complémentaire -> XII."""
    en_base = None if test._state.adding else TestPrevu.all_objects.filter(pk=test.pk).first()
    if en_base is None:
        exiger_etape_ouverte(test.mission_id, ETAPE_FICHES if test.complementaire else 8)
        return
    modifies = champs_modifies(test, en_base)
    if not modifies:
        return
    complementaire = en_base.complementaire
    ressources = modifies & CHAMPS_RESSOURCES
    abandon = modifies & CHAMPS_ABANDON
    contenu = modifies - ressources - abandon
    if contenu:
        exiger_etape_ouverte(test.mission_id, ETAPE_FICHES if complementaire else ETAPE_CONTENU)
    if ressources:
        exiger_etape_ouverte(test.mission_id, ETAPE_FICHES if complementaire else ETAPE_RESSOURCES)
    if abandon:
        exiger_etape_ouverte(test.mission_id, ETAPE_FICHES)


def _code_test(test_id: UUID) -> str:
    return str(
        TestPrevu.all_objects.filter(pk=test_id).values_list("code", flat=True).first() or ""
    )


def controler_fiche(fiche: FicheDeTest) -> None:
    """Gel D7 : contenu -> XII ; VALIDE -> immuable ; validation / renvoi / réouverture -> XIII."""
    en_base = None if fiche._state.adding else FicheDeTest.all_objects.filter(pk=fiche.pk).first()
    if en_base is None:
        exiger_etape_ouverte(fiche.mission_id, ETAPE_FICHES)
        return
    if en_base.statut == StatutFiche.VALIDE and _REOUVERTURE.get() != fiche.pk:
        raise FicheValideeError(_code_test(fiche.test_id))
    modifies = champs_modifies(fiche, en_base)
    if modifies - CHAMPS_TRANSITION_FICHE:
        exiger_etape_ouverte(fiche.mission_id, ETAPE_FICHES)
    if modifies & CHAMPS_TRANSITION_FICHE:
        validation = fiche.statut in (StatutFiche.VALIDE, StatutFiche.RENVOYE) or (
            en_base.statut == StatutFiche.VALIDE
        )
        exiger_etape_ouverte(
            fiche.mission_id, ETAPE_VALIDATION_PREUVES if validation else ETAPE_FICHES
        )


def controler_piece(piece: PieceJustificative) -> None:
    """Gel D8 : champs de fichier immuables ; fiche BROUILLON / RENVOYE en base ; XII ouverte."""
    if not piece._state.adding:
        en_base = PieceJustificative.all_objects.filter(pk=piece.pk).first()
        if en_base is not None and champs_modifies(piece, en_base) & CHAMPS_FICHIER:
            raise PieceImmuableError
    ligne = (
        FicheDeTest.all_objects.filter(pk=piece.fiche_id)
        .values_list("statut", "test__code")
        .first()
    )
    if ligne is not None:
        statut, code = ligne
        if statut == StatutFiche.VALIDE:
            raise FicheValideeError(code)
        if statut == StatutFiche.SOUMIS:
            raise FicheVerrouilleeError(code)
    exiger_etape_ouverte(piece.mission_id, ETAPE_FICHES)

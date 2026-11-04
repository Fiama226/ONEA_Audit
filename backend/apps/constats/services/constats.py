"""Constats, causes et recommandations (D10 du plan du lot 6).

Chaque service d'écriture : droits (403), puis verrouillage mission, étape XIV, constat (dans
cet ordre), puis règles métier (422). Tout est atomique : un refus ne laisse rien et ne
consomme aucun numéro.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.accomplissement.models import ConclusionTest, FicheDeTest
from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.acces import est_chef, peut_contribuer, peut_valider_travaux
from apps.missions.models import Mission, RisqueMission
from apps.missions.notifications import audites
from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.signatures.services import empreinte, normaliser
from apps.users.models import Role, User

from ..managers import prochain_numero_constat
from ..models import (
    CategorieCause,
    CauseConstat,
    Constat,
    EvenementConstat,
    PrioriteRecommandation,
    Recommandation,
    StatutConstat,
    TypeEvenementConstat,
)
from ._fenetres import ouvrir_xiv

MSG_DROIT_CONTRIBUER = "Vous n'avez pas le droit de modifier les constats de cette mission."
MSG_DROIT_SOUMETTRE = "Seuls le chef de mission ou le RAI peuvent soumettre un constat."
MSG_DROIT_VALIDER = "Vous n'avez pas le droit de valider ce constat."
MSG_DROIT_AUTEUR = "Vous ne pouvez pas traiter un constat dont vous êtes l'auteur ou le soumetteur."
MSG_MOTIF = "Le motif est obligatoire."
_EDITABLES = (StatutConstat.BROUILLON, StatutConstat.RENVOYE)
_CHAMPS = {
    "entite",
    "processus",
    "risque_mission",
    "fait_constate",
    "referentiel",
    "consequence",
    "conclusion",
    "probabilite",
    "impact",
}
_MODIFIABLES = _CHAMPS | {"titre", "fiches"}
_CLES_CAUSE = {"id", "categorie", "description", "ordre"}
_CLES_RECO = {"id", "libelle", "priorite", "ordre"}


# --------------------------------------------------------------------------- droits


def _exiger_contributeur(by: User, mission: Mission) -> None:
    if not peut_contribuer(by, mission):
        raise PermissionDenied(MSG_DROIT_CONTRIBUER)


def _exiger_soumetteur(by: User, mission: Mission) -> None:
    if not (peut_contribuer(by, mission) and (by.role == Role.RAI or est_chef(by, mission))):
        raise PermissionDenied(MSG_DROIT_SOUMETTRE)


def _exiger_valideur(by: User, mission: Mission) -> None:
    if not peut_valider_travaux(by, mission):
        raise PermissionDenied(MSG_DROIT_VALIDER)


def _exiger_pas_auteur(constat: Constat, by: User) -> None:
    if by.pk in (constat.created_by_id, constat.soumis_par_id):
        raise PermissionDenied(MSG_DROIT_AUTEUR)


# --------------------------------------------------------------------------- validations


def _exiger_statut(constat: Constat, *statuts: str) -> None:
    if constat.statut not in statuts:
        raise RegleMetierError(
            f"Le constat {constat.reference} est {StatutConstat(constat.statut).label.lower()} : "
            "cette action n'est pas possible."
        )


def _motif(motif: str) -> str:
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    return motif


def _verifier_fiches(mission: Mission, fiches: Iterable[FicheDeTest]) -> list[FicheDeTest]:
    resultat: list[FicheDeTest] = []
    for fiche in fiches:
        trouvee = (
            FicheDeTest.objects.select_related("test").filter(pk=fiche.pk, mission=mission).first()
        )
        if trouvee is None:
            # L'identifiant seul : le code d'un test d'une autre mission ne doit pas fuiter.
            message = f"La fiche {fiche.pk} n'appartient pas à la mission."
            raise refuser(message, fiches=message)
        resultat.append(trouvee)
    return resultat


def _verifier_rattachements(mission: Mission, valeurs: Mapping[str, Any]) -> None:
    entite = valeurs.get("entite")
    if entite is not None and not mission.entites.filter(pk=entite.pk).exists():
        message = "L'entité doit être une entité de la mission."
        raise refuser(message, entite=message)
    processus = valeurs.get("processus")
    if processus is not None and not mission.processus.filter(pk=processus.pk).exists():
        message = "Le processus doit être un processus de la mission."
        raise refuser(message, processus=message)
    risque = valeurs.get("risque_mission")
    if (
        risque is not None
        and not RisqueMission.objects.filter(pk=risque.pk, mission=mission).exists()
    ):
        message = "Le risque doit être un risque de la mission."
        raise refuser(message, risque_mission=message)


def _verifier_notes(valeurs: Mapping[str, Any]) -> None:
    for champ, libelle in (("probabilite", "La probabilité"), ("impact", "L'impact")):
        valeur = valeurs.get(champ)
        if valeur is not None and not 1 <= valeur <= 5:
            message = f"{libelle} doit être comprise entre 1 et 5."
            if champ == "impact":
                message = "L'impact doit être compris entre 1 et 5."
            raise refuser(message, **{champ: message})


def _nettoyer_causes(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    propres: list[dict[str, Any]] = []
    for item in items:
        if set(item) - _CLES_CAUSE:
            raise refuser("Cause invalide.", causes="Cause invalide.")
        if item.get("categorie") not in CategorieCause.values:
            message = "La catégorie de la cause est inconnue."
            raise refuser(message, causes=message)
        description = str(item.get("description", "")).strip()
        if not description:
            message = "La description de la cause est obligatoire."
            raise refuser(message, causes=message)
        propres.append({**item, "description": description})
    return propres


def _nettoyer_recommandations(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    propres: list[dict[str, Any]] = []
    for item in items:
        if set(item) - _CLES_RECO:
            raise refuser("Recommandation invalide.", recommandations="Recommandation invalide.")
        if item.get("priorite") not in PrioriteRecommandation.values:
            message = "La priorité doit être HAUTE, MOYENNE ou FAIBLE."
            raise refuser(message, recommandations=message)
        libelle = str(item.get("libelle", "")).strip()
        if not libelle:
            message = "Le libellé de la recommandation est obligatoire."
            raise refuser(message, recommandations=message)
        propres.append({**item, "libelle": libelle})
    return propres


# --------------------------------------------------------------------------- listes


def _remplacer[T: (CauseConstat, Recommandation)](
    constat: Constat,
    modele: type[T],
    items: list[dict[str, Any]],
    champs: tuple[str, ...],
    champ_erreur: str,
    by: User,
) -> None:
    """Remplace l'ensemble : mises à jour par `id`, créations sans `id`, retraits supprimés."""
    existants = {str(o.pk): o for o in modele.objects.filter(constat=constat)}
    conserves: set[str] = set()
    for rang, item in enumerate(items, start=1):
        cle = item.get("id")
        if cle is None:
            objet: Any = modele(mission=constat.mission, constat=constat)
            creation = True
        else:
            cle = str(cle)
            if cle not in existants or cle in conserves:
                message = "Élément inconnu pour ce constat."
                raise refuser(message, **{champ_erreur: message})
            conserves.add(cle)
            objet = existants[cle]
            creation = False
        for champ in champs:
            setattr(objet, champ, item[champ])
        objet.ordre = item.get("ordre", rang)
        enregistrer(objet, by=by, creation=creation)
    with actor_scope(by):
        for cle, objet in existants.items():
            if cle not in conserves:
                objet.soft_delete(by)


def _ecrire_listes(
    constat: Constat,
    causes: list[dict[str, Any]] | None,
    recommandations: list[dict[str, Any]] | None,
    by: User,
) -> None:
    if causes is not None:
        _remplacer(constat, CauseConstat, causes, ("categorie", "description"), "causes", by)
    if recommandations is not None:
        _remplacer(
            constat,
            Recommandation,
            recommandations,
            ("libelle", "priorite"),
            "recommandations",
            by,
        )


# --------------------------------------------------------------------------- création


@transaction.atomic
def creer_constat(
    mission: Mission,
    *,
    titre: str,
    by: User,
    fiches: Iterable[FicheDeTest] = (),
    causes: Iterable[Mapping[str, Any]] = (),
    recommandations: Iterable[Mapping[str, Any]] = (),
    **champs: Any,
) -> Constat:
    _exiger_contributeur(by, mission)
    mission = ouvrir_xiv(mission)
    titre = titre.strip()
    if not titre:
        raise refuser("Le titre est obligatoire.", titre="Le titre est obligatoire.")
    for obligatoire, libelle in (("entite", "L'entité"), ("processus", "Le processus")):
        if champs.get(obligatoire) is None:
            message = f"{libelle} est obligatoire."
            raise refuser(message, **{obligatoire: message})
    inconnus = set(champs) - _CHAMPS
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")
    _verifier_rattachements(mission, champs)
    _verifier_notes(champs)
    liees = _verifier_fiches(mission, fiches)
    causes_ok = _nettoyer_causes(causes)
    recos_ok = _nettoyer_recommandations(recommandations)

    numero = prochain_numero_constat(mission.pk)
    constat = Constat(mission=mission, titre=titre, numero=numero, reference=f"C-{numero:02d}")
    appliquer(constat, champs, _CHAMPS)
    enregistrer(constat, by=by, creation=True)
    with actor_scope(by):
        if liees:
            constat.fiches.add(*liees)
    _ecrire_listes(constat, causes_ok, recos_ok, by)
    constat.refresh_from_db(fields=["score", "niveau"])
    return constat


# --------------------------------------------------------------------------- modification


@transaction.atomic
def modifier_constat(
    constat: Constat,
    *,
    by: User,
    causes: Iterable[Mapping[str, Any]] | None = None,
    recommandations: Iterable[Mapping[str, Any]] | None = None,
    **changes: Any,
) -> Constat:
    mission = constat.mission
    _exiger_contributeur(by, mission)
    mission = ouvrir_xiv(mission)
    constat = relire(constat)
    _exiger_statut(constat, *_EDITABLES)
    inconnus = set(changes) - _MODIFIABLES
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")
    fiches = changes.pop("fiches", None)
    if "titre" in changes:
        changes["titre"] = changes["titre"].strip()
        if not changes["titre"]:
            raise refuser("Le titre est obligatoire.", titre="Le titre est obligatoire.")
    for obligatoire, libelle in (("entite", "L'entité"), ("processus", "Le processus")):
        if obligatoire in changes and changes[obligatoire] is None:
            message = f"{libelle} est obligatoire."
            raise refuser(message, **{obligatoire: message})
    _verifier_rattachements(mission, changes)
    _verifier_notes(changes)
    liees = _verifier_fiches(mission, fiches) if fiches is not None else None
    causes_ok = _nettoyer_causes(causes) if causes is not None else None
    recos_ok = _nettoyer_recommandations(recommandations) if recommandations is not None else None
    appliquer(constat, changes, _MODIFIABLES)
    enregistrer(constat, by=by)
    with actor_scope(by):
        if liees is not None:
            constat.fiches.set(liees)
    _ecrire_listes(constat, causes_ok, recos_ok, by)
    constat.refresh_from_db(fields=["score", "niveau"])
    return constat


@transaction.atomic
def supprimer_constat(constat: Constat, *, by: User) -> None:
    mission = constat.mission
    _exiger_contributeur(by, mission)
    ouvrir_xiv(mission)
    constat = relire(constat)
    _exiger_statut(constat, *_EDITABLES)
    with actor_scope(by):
        for cause in CauseConstat.objects.filter(constat=constat):
            cause.soft_delete(by)
        for reco in Recommandation.objects.filter(constat=constat):
            reco.soft_delete(by)
        constat.soft_delete(by)


# --------------------------------------------------------------------------- transitions


def _version_soumise(constat: Constat) -> dict[str, Any]:
    constat.refresh_from_db(fields=["score", "niveau"])
    return {
        "reference": constat.reference,
        "titre": constat.titre,
        "entite": constat.entite.code,
        "processus": constat.processus.code,
        "fait_constate": constat.fait_constate,
        "referentiel": constat.referentiel,
        "consequence": constat.consequence,
        "conclusion": constat.conclusion,
        "probabilite": constat.probabilite,
        "impact": constat.impact,
        "score": constat.score,
        "niveau": constat.niveau,
        "fiches": sorted(f.test.code for f in constat.fiches.select_related("test")),
        "causes": [
            {"categorie": c.categorie, "description": c.description}
            for c in CauseConstat.objects.filter(constat=constat)
        ],
        "recommandations": [
            {"libelle": r.libelle, "priorite": r.priorite}
            for r in Recommandation.objects.filter(constat=constat)
        ],
    }


def _exigences(constat: Constat) -> dict[str, list[str]]:
    erreurs: dict[str, list[str]] = {}
    textes = (
        ("fait_constate", "Le fait constaté est obligatoire."),
        ("referentiel", "Le référentiel (critère) est obligatoire."),
        ("consequence", "La conséquence est obligatoire."),
    )
    for champ, message in textes:
        if not getattr(constat, champ).strip():
            erreurs[champ] = [message]
    if constat.probabilite is None:
        erreurs["probabilite"] = ["La probabilité est obligatoire."]
    if constat.impact is None:
        erreurs["impact"] = ["L'impact est obligatoire."]
    if not CauseConstat.objects.filter(constat=constat).exists():
        erreurs["causes"] = ["Au moins une cause est obligatoire."]
    if not Recommandation.objects.filter(constat=constat).exists():
        erreurs["recommandations"] = ["Au moins une recommandation est obligatoire."]
    if not constat.fiches.filter(
        conclusion=ConclusionTest.ANOMALIE, deleted_at__isnull=True
    ).exists():
        erreurs["fiches"] = ["Au moins une fiche de test de conclusion ANOMALIE est obligatoire."]
    return erreurs


def _evenement(constat: Constat, type_: str, by: User, avant: str, motif: str = "") -> None:
    with actor_scope(by):
        EvenementConstat.journaliser(constat, type_, par=by, motif=motif, statut_avant=avant)


def _notifier_audites(constat: Constat, by: User) -> None:
    """Prévient les audités de la direction concernée qu'un constat attend leur réponse."""
    entite = constat.entite
    if entite is None:
        return
    codes = {entite.code, getattr(entite.parent, "code", None)}
    concernes = [
        u
        for u in audites(constat.mission)
        if u.direction_code and u.direction_code in codes and u.pk != by.pk
    ]
    for user in concernes:
        notifier(
            [user],
            type=TypeNotification.CONSTAT_SOUMIS,
            titre="Un constat attend votre réponse",
            message=f"{constat.mission.reference} : {constat.reference} — {constat.titre[:200]}.",
            lien=f"/missions/{constat.mission_id}/constats/{constat.pk}",
            objet=constat,
            cle=f"CONSTAT_SOUMIS:{constat.pk}:{constat.cycle}:{user.pk}",
        )


@transaction.atomic
def soumettre_constat(constat: Constat, *, by: User) -> Constat:
    _exiger_soumetteur(by, constat.mission)
    ouvrir_xiv(constat.mission)
    constat = relire(constat)
    _exiger_statut(constat, *_EDITABLES)
    erreurs = _exigences(constat)
    if erreurs:
        raise RegleMetierError("Le constat est incomplet.", erreurs)
    avant = constat.statut
    constat.soumettre()
    constat.cycle += 1
    constat.soumis_par = by
    constat.soumis_le = timezone.now()
    constat.motif_renvoi = ""
    constat.version_soumise = normaliser(_version_soumise(constat))
    constat.empreinte_soumise = empreinte(
        f"{constat.reference} {constat.titre}", constat.version_soumise
    )
    enregistrer(constat, by=by)
    _evenement(constat, TypeEvenementConstat.SOUMIS, by, avant)
    _notifier_audites(constat, by)
    return constat


@transaction.atomic
def valider_constat(constat: Constat, *, by: User) -> Constat:
    _exiger_valideur(by, constat.mission)
    ouvrir_xiv(constat.mission)
    constat = relire(constat)
    _exiger_pas_auteur(constat, by)
    _exiger_statut(constat, StatutConstat.SOUMIS)
    avant = constat.statut
    constat.valider()
    constat.validee_par = by
    constat.validee_le = timezone.now()
    enregistrer(constat, by=by)
    _evenement(constat, TypeEvenementConstat.VALIDE, by, avant)
    return constat


@transaction.atomic
def renvoyer_constat(constat: Constat, *, motif: str, by: User) -> Constat:
    _exiger_valideur(by, constat.mission)
    ouvrir_xiv(constat.mission)
    constat = relire(constat)
    _exiger_pas_auteur(constat, by)
    motif = _motif(motif)
    _exiger_statut(constat, StatutConstat.SOUMIS)
    avant = constat.statut
    constat.renvoyer()
    constat.motif_renvoi = motif
    enregistrer(constat, by=by)
    _evenement(constat, TypeEvenementConstat.RENVOYE, by, avant, motif)
    return constat


@transaction.atomic
def rouvrir_constat(constat: Constat, *, motif: str, by: User) -> Constat:
    _exiger_valideur(by, constat.mission)
    ouvrir_xiv(constat.mission)
    constat = relire(constat)
    _exiger_pas_auteur(constat, by)
    motif = _motif(motif)
    _exiger_statut(constat, StatutConstat.VALIDE)
    avant = constat.statut
    constat.rouvrir()
    constat.validee_par = None
    constat.validee_le = None
    enregistrer(constat, by=by)
    _evenement(constat, TypeEvenementConstat.ROUVERT, by, avant, motif)
    return constat

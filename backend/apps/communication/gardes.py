"""Gardes de gel de la communication (D4, D11 du plan du lot 7).

Elles lisent l'état EN BASE (jamais l'instance seule) et sont appelées par
`exiger_travaux_ouverts()` des modèles, donc par `save()`, ainsi que par les QuerySets
(`update`, `bulk_update`, `bulk_create`).

Rapport : les sections et l'appréciation globale ne changent qu'en BROUILLON ou RENVOYE (mission
`EN_COMMUNICATION`) ; un changement de statut ne peut écrire que la liste blanche de champs de sa
transition ; toute autre écriture est refusée.
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from django.db.models.expressions import Combinable

from apps.core.exceptions import RegleMetierError
from apps.missions.gardes import exiger_etape_ouverte, refuser_si_figee
from apps.missions.models import Mission, StatutMission

from .exceptions import (
    MSG_AUTRE_MISSION,
    MSG_DESTINATAIRES_FIGES,
    MSG_RAPPORT_HORS_COMMUNICATION,
    MSG_SUIVI_HORS_DIFFUSION,
    MSG_TRANSITION_CHAMPS,
    MSG_TRANSITION_INTERDITE,
    RapportFigeError,
)
from .models import (
    DestinataireDiffusion,
    Rapport,
    ReponseRapport,
    StatutRapport,
)

ETAPE_REPONSES = 16

STATUTS_REDACTION: frozenset[str] = frozenset({StatutRapport.BROUILLON, StatutRapport.RENVOYE})
STATUTS_LISTE_FIGEE: frozenset[str] = frozenset({StatutRapport.DIFFUSE, StatutRapport.REMPLACE})

# Champs de rédaction (D5) : seuls modifiables en BROUILLON ou RENVOYE.
CHAMPS_REDACTION: frozenset[str] = frozenset(
    {
        "synthese",
        "appreciation_globale",
        "commentaire_appreciation",
        "contexte",
        "objectifs_texte",
        "perimetre_texte",
        "methodologie",
        "conclusion",
        "note_synthetique",
        "annexes_texte",
    }
)
# Champs sans effet métier, ignorés par la comparaison.
CHAMPS_TECHNIQUES: frozenset[str] = frozenset({"updated_at", "updated_by_id"})

# Liste blanche des champs (noms de colonne) qu'une sauvegarde de transition peut changer.
_SORTIE_VALIDATION = frozenset(
    {"valide_par_id", "valide_le", "confirmation_validation_id", "mode_signature", "motif_renvoi"}
)
CHAMPS_TRANSITION: dict[tuple[str, str], frozenset[str]] = {
    (StatutRapport.BROUILLON, StatutRapport.SOUMIS): frozenset(
        {
            "statut",
            "cycle",
            "soumis_par_id",
            "soumis_le",
            "instantane_soumis",
            "empreinte_soumise",
            "motif_renvoi",
        }
    ),
    (StatutRapport.RENVOYE, StatutRapport.SOUMIS): frozenset(
        {
            "statut",
            "cycle",
            "soumis_par_id",
            "soumis_le",
            "instantane_soumis",
            "empreinte_soumise",
            "motif_renvoi",
        }
    ),
    (StatutRapport.SOUMIS, StatutRapport.VALIDE): frozenset(
        {"statut", "valide_par_id", "valide_le", "confirmation_validation_id", "mode_signature"}
    ),
    (StatutRapport.SOUMIS, StatutRapport.RENVOYE): frozenset({"statut", "motif_renvoi"}),
    (StatutRapport.VALIDE, StatutRapport.DIFFUSE): frozenset({"statut"}),
    (StatutRapport.DIFFUSE, StatutRapport.REMPLACE): frozenset({"statut"}),
    (StatutRapport.SOUMIS, StatutRapport.BROUILLON): frozenset({"statut"}) | _SORTIE_VALIDATION,
    (StatutRapport.VALIDE, StatutRapport.BROUILLON): frozenset({"statut"}) | _SORTIE_VALIDATION,
    (StatutRapport.RENVOYE, StatutRapport.BROUILLON): frozenset({"statut"}) | _SORTIE_VALIDATION,
}

# Champs de suivi d'un destinataire (D11) : écrits par les services, rapport DIFFUSE seulement.
CHAMPS_SUIVI: frozenset[str] = frozenset(
    {"notifie_le", "premiere_consultation_le", "accuse_reception_le", "remis_hors_plateforme_le"}
)


def refuser_mission(mission_id: UUID | None) -> None:
    refuser_si_figee(mission_id)


def _modifies(ligne: Mapping[str, Any], apres: Mapping[str, Any]) -> set[str]:
    """Colonnes de `apres` dont la valeur diffère de la ligne en base (hors champs techniques)."""
    return {
        c
        for c, v in apres.items()
        if c not in CHAMPS_TECHNIQUES and (isinstance(v, Combinable) or v != ligne[c])
    }


def _label(statut: str) -> str:
    """Libellé du statut, en minuscule initiale pour la phrase d'erreur."""
    libelle = str(StatutRapport(statut).label)
    return libelle[0].lower() + libelle[1:]


def _noms(colonnes: set[str]) -> str:
    return ", ".join(sorted(c.removesuffix("_id") for c in colonnes))


def _mission_ouverte_a_la_redaction(ligne: Mapping[str, Any]) -> bool:
    """Mission EN_COMMUNICATION ; un rapport corrigé (D12) vit sous une mission RAPPORT_DIFFUSE."""
    statut = (
        Mission.all_objects.filter(pk=ligne["mission_id"]).values_list("statut", flat=True).first()
    )
    return statut == StatutMission.EN_COMMUNICATION or (
        ligne["corrige_de_id"] is not None and statut == StatutMission.RAPPORT_DIFFUSE
    )


def controler_modification(ligne: Mapping[str, Any], apres: Mapping[str, Any]) -> None:
    """Garde commune à `save`, `update` et `bulk_update` d'un rapport existant.

    `ligne` : valeurs en base ; `apres` : valeurs écrites, par nom de colonne.
    """
    modifies = _modifies(ligne, apres)
    if not modifies:
        return
    avant = ligne["statut"]
    if "statut" in modifies:
        cible = apres["statut"]
        autorises = None if isinstance(cible, Combinable) else CHAMPS_TRANSITION.get((avant, cible))
        if autorises is None:
            raise RegleMetierError(
                MSG_TRANSITION_INTERDITE.format(avant=_label(avant), apres=str(cible))
            )
        interdits = modifies - autorises
        if interdits:
            raise RegleMetierError(MSG_TRANSITION_CHAMPS.format(champs=_noms(interdits)))
        return
    if avant not in STATUTS_REDACTION or modifies - CHAMPS_REDACTION - {"deleted_at"}:
        raise RapportFigeError(_label(avant))
    if not _mission_ouverte_a_la_redaction(ligne):
        raise RegleMetierError(MSG_RAPPORT_HORS_COMMUNICATION)


def _colonnes(objet: Any, ecrits: frozenset[str] | None) -> set[str]:
    """Colonnes écrites : celles de `update_fields`, sinon toutes."""
    if ecrits is None:
        return {f.attname for f in objet._meta.concrete_fields}
    return {objet._meta.get_field(n).attname for n in ecrits}


def controler_rapport(rapport: Rapport) -> None:
    """Garde de `Rapport.save()` : compare les colonnes écrites à la ligne en base."""
    if rapport._state.adding:
        return
    ligne = Rapport.all_objects.filter(pk=rapport.pk).values().first()
    if ligne is None:
        return
    colonnes = _colonnes(rapport, rapport._champs_ecrits)
    controler_modification(ligne, {c: getattr(rapport, c) for c in colonnes})


def _rapport(rapport_id: UUID) -> tuple[str, UUID] | None:
    return Rapport.all_objects.filter(pk=rapport_id).values_list("statut", "mission_id").first()


def controler_meme_mission(objet: Any, **liaisons: Any) -> None:
    """Chaque liaison (nom -> modèle, identifiant) appartient à la mission de l'objet."""
    for modele, identifiant in liaisons.values():
        if identifiant is None:
            continue
        mission_id = (
            modele.all_objects.filter(pk=identifiant).values_list("mission_id", flat=True).first()
        )
        if mission_id is not None and mission_id != objet.mission_id:
            raise RegleMetierError(MSG_AUTRE_MISSION)


def controler_provisoire(provisoire: Any) -> None:
    controler_meme_mission(provisoire, rapport=(Rapport, provisoire.rapport_id))


def controler_diffusion(diffusion: Any) -> None:
    controler_meme_mission(diffusion, rapport=(Rapport, diffusion.rapport_id))


def controler_reponse(reponse: ReponseRapport) -> None:
    """Gel de D7 : une réponse s'ajoute tant que l'étape XVI n'est pas close."""
    from apps.constats.models import Constat

    from .models import RapportProvisoire

    controler_meme_mission(
        reponse,
        provisoire=(RapportProvisoire, reponse.provisoire_id),
        constat=(Constat, reponse.constat_id),
    )
    exiger_etape_ouverte(reponse.mission_id, ETAPE_REPONSES)


def controler_modification_destinataire(ligne: Mapping[str, Any], apres: Mapping[str, Any]) -> None:
    """Garde commune à `save`, `update` et `bulk_update` d'un destinataire existant (D11)."""
    modifies = _modifies(ligne, apres)
    if not modifies:
        return
    rapports = {ligne["rapport_id"], apres.get("rapport_id", ligne["rapport_id"])}
    for rapport_id in rapports:
        courant = _rapport(rapport_id)
        statut = courant[0] if courant else None
        if statut == StatutRapport.DIFFUSE:
            if modifies - CHAMPS_SUIVI:
                raise RegleMetierError(MSG_DESTINATAIRES_FIGES)
        elif statut == StatutRapport.REMPLACE:
            raise RegleMetierError(MSG_DESTINATAIRES_FIGES)
        elif modifies & CHAMPS_SUIVI:
            raise RegleMetierError(MSG_SUIVI_HORS_DIFFUSION)


def controler_destinataire(destinataire: DestinataireDiffusion) -> None:
    """Garde de `DestinataireDiffusion.save()` : ajout, modification, suppression."""
    controler_meme_mission(destinataire, rapport=(Rapport, destinataire.rapport_id))
    if destinataire._state.adding:
        courant = _rapport(destinataire.rapport_id)
        if courant is not None and courant[0] in STATUTS_LISTE_FIGEE:
            raise RegleMetierError(MSG_DESTINATAIRES_FIGES)
        return
    ligne = DestinataireDiffusion.all_objects.filter(pk=destinataire.pk).values().first()
    if ligne is None:
        return
    colonnes = _colonnes(destinataire, destinataire._champs_ecrits)
    controler_modification_destinataire(ligne, {c: getattr(destinataire, c) for c in colonnes})

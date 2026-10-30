"""Relances automatiques J-15 / J / J+15 des actions à suivre (R9, lot 8 T7).

Périmètre des destinataires : le responsable de l'action (To) et, au palier J+15, le chef de la
mission (Cc) ; le RAI reçoit seulement une notification interne. Le contenu des e-mails se limite
à la référence de mission, au libellé de l'action, à l'échéance et à un lien : aucun texte de
constat ni de recommandation.
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from smtplib import SMTPException
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.mail import BadHeaderError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.core.mail import send_mail_template
from apps.missions.models import AffectationMission, Mission, RoleMission, StatutMission
from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.users.models import Role, User

from . import sources
from .models import (
    STATUTS_RELANCABLES,
    PalierRelance,
    Relance,
    StatutRelance,
    SuiviAction,
)

logger = logging.getLogger(__name__)

DELAI_PALIER = 15
LIBELLE_MAX = 200
# Du plus urgent au moins urgent : ordre d'affichage dans l'e-mail.
TITRES_PALIERS: dict[str, str] = {
    PalierRelance.J_PLUS_15: "En retard de 15 jours",
    PalierRelance.J: "Échéance aujourd'hui",
    PalierRelance.J_MOINS_15: "Échéance dans 15 jours",
}
ERREURS_ENVOI = (SMTPException, OSError, BadHeaderError)


def palier_atteint(echeance: date, aujourd_hui: date) -> PalierRelance | None:
    """Palier le plus haut atteint (rattrapage : un seul palier, jamais les précédents)."""
    delai = timedelta(days=DELAI_PALIER)
    if aujourd_hui >= echeance + delai:
        return PalierRelance.J_PLUS_15
    if aujourd_hui >= echeance:
        return PalierRelance.J
    if aujourd_hui >= echeance - delai:
        return PalierRelance.J_MOINS_15
    return None


def _suivis_relancables() -> Any:
    return SuiviAction.objects.filter(
        statut__in=STATUTS_RELANCABLES,
        mission__statut=StatutMission.EN_SUIVI,
        responsable__is_active=True,
        responsable__desactive_le__isnull=True,
    )


def _actif(user: User | None) -> bool:
    return user is not None and user.is_active and user.desactive_le is None


def _chefs(mission_ids: set[Any]) -> dict[Any, User]:
    affectations = AffectationMission.objects.filter(
        mission_id__in=mission_ids, role_mission=RoleMission.CHEF_MISSION
    ).select_related("utilisateur")
    return {a.mission_id: a.utilisateur for a in affectations if _actif(a.utilisateur)}


def _lien_relatif(suivi: SuiviAction) -> str:
    return f"/recommandations/actions/{suivi.action_id}"


def _lien_absolu(suivi: SuiviAction) -> str:
    return f"{settings.PLATEFORME_URL.rstrip('/')}{_lien_relatif(suivi)}"


def _notifier(relance: Relance, suivi: SuiviAction, rai: list[User]) -> None:
    detail = (
        f"{TITRES_PALIERS[relance.palier]} : action de la mission {suivi.mission.reference}, "
        f"échéance du {relance.echeance_reference:%d/%m/%Y}."
    )
    notifier(
        [suivi.responsable],
        type=TypeNotification.RELANCE,
        titre="Relance : action à traiter",
        message=detail,
        lien=_lien_relatif(suivi),
        objet=suivi,
        cle=f"relance:{relance.pk}",
    )
    if relance.palier == PalierRelance.J_PLUS_15 and rai:
        notifier(
            rai,
            type=TypeNotification.RELANCE,
            titre="Action en retard de 15 jours",
            message=detail,
            lien=_lien_relatif(suivi),
            objet=suivi,
            cle=f"relance-rai:{relance.pk}",
        )


def planifier_relances(aujourd_hui: date | None = None) -> list[Relance]:
    """Crée les relances dues (idempotent) ; renvoie celles qui viennent d'être créées."""
    jour = aujourd_hui or timezone.localdate()
    suivis = list(_suivis_relancables().select_related("responsable", "mission"))
    dues = [(s, p) for s in suivis if (p := palier_atteint(s.echeance, jour)) is not None]
    if not dues:
        return []
    existantes = set(
        Relance.all_objects.filter(suivi__in=[s.pk for s, _ in dues]).values_list(
            "suivi_id", "palier", "echeance_reference"
        )
    )
    a_creer = [(s, p) for s, p in dues if (s.pk, p, s.echeance) not in existantes]
    if not a_creer:
        return []
    chefs = _chefs({s.mission_id for s, _ in a_creer})
    lignes = [
        Relance(
            suivi=s,
            palier=p,
            echeance_reference=s.echeance,
            destinataire=s.responsable,
            copie=chefs.get(s.mission_id) if p == PalierRelance.J_PLUS_15 else None,
            statut=(StatutRelance.A_ENVOYER if s.responsable.email else StatutRelance.SANS_ADRESSE),
        )
        for s, p in a_creer
    ]
    Relance.all_objects.bulk_create(lignes, ignore_conflicts=True)
    # Les identifiants sont générés côté client : seules les lignes réellement insérées existent.
    crees = list(Relance.all_objects.filter(pk__in=[r.pk for r in lignes]))
    par_suivi = {s.pk: s for s, _ in a_creer}
    rai = list(User.objects.filter(role=Role.RAI, is_active=True, desactive_le__isnull=True))
    for relance in crees:
        _notifier(relance, par_suivi[relance.suivi_id], rai)
    return crees


def _a_envoyer() -> Any:
    """Relances à envoyer pertinentes (suivi relançable, échéance et responsable inchangés)."""
    return Relance.objects.filter(
        Q(statut=StatutRelance.A_ENVOYER)
        | Q(statut=StatutRelance.ECHEC, tentatives__lt=settings.RELANCES_TENTATIVES_MAX),
        suivi__statut__in=STATUTS_RELANCABLES,
        suivi__mission__statut=StatutMission.EN_SUIVI,
        suivi__echeance=F("echeance_reference"),
        suivi__responsable=F("destinataire"),
        destinataire__is_active=True,
        destinataire__desactive_le__isnull=True,
    )


def regrouper_par_destinataire(limite: int) -> list[tuple[int, list[UUID]]]:
    """Une entrée par destinataire (donc un e-mail), au plus `limite` destinataires."""
    groupes: dict[int, list[UUID]] = defaultdict(list)
    for destinataire_id, relance_id in (
        _a_envoyer().order_by("created_at", "pk").values_list("destinataire_id", "pk")
    ):
        if destinataire_id not in groupes and len(groupes) >= limite:
            continue
        groupes[destinataire_id].append(relance_id)
    return list(groupes.items())


def _nettoyer(texte: str) -> str:
    """Texte saisi par un utilisateur : une seule ligne, sans caractère de contrôle, borné."""
    propre = "".join(c if c.isprintable() else " " for c in texte)
    return " ".join(propre.split())[:LIBELLE_MAX]


def _contexte(destinataire: User, lignes: list[Relance]) -> dict[str, Any]:
    libelles = sources.libelles_actions([r.suivi.action_id for r in lignes])
    groupes = []
    for palier, titre in TITRES_PALIERS.items():
        actions = [
            {
                "mission": r.suivi.mission.reference,
                "libelle": _nettoyer(libelles.get(r.suivi.action_id, "")),
                "echeance": r.echeance_reference,
                "lien": _lien_absolu(r.suivi),
            }
            for r in lignes
            if r.palier == palier
        ]
        if actions:
            groupes.append({"titre": titre, "actions": actions})
    return {
        "name": _nettoyer(destinataire.nom_complet or destinataire.get_username()),
        "groupes": groupes,
        "nombre": len(lignes),
    }


def _copies(lignes: list[Relance], destinataire: User) -> list[str]:
    adresses: dict[str, str] = {}
    for r in lignes:
        copie = r.copie
        if _actif(copie) and copie is not None and copie.email:
            adresses.setdefault(copie.email.lower(), copie.email)
    adresses.pop(destinataire.email.lower(), None)
    return list(adresses.values())


def _regler(lignes: list[Relance], **champs: Any) -> None:
    for r in lignes:
        for nom, valeur in champs.items():
            setattr(r, nom, valeur)
        r.save(update_fields=[*champs, "updated_at"])


def envoyer_lot(destinataire_id: int, relance_ids: list[str]) -> int:
    """Envoie UN e-mail regroupant les relances encore dues du destinataire ; renvoie leur nombre.

    Les lignes sont verrouillées (`skip_locked`) : deux exécutions concurrentes n'envoient pas
    deux fois. Une relance dont le suivi n'est plus relançable, dont l'échéance ou le responsable
    ont changé, est écartée sans envoi et sans changement de statut.
    """
    with transaction.atomic():
        lignes = list(
            _a_envoyer()
            .filter(pk__in=relance_ids, destinataire_id=destinataire_id)
            .select_for_update(skip_locked=True, of=("self",))
            .select_related("suivi__mission", "destinataire", "copie")
            .order_by("created_at", "pk")
        )
        if not lignes:
            return 0
        destinataire = lignes[0].destinataire
        if not destinataire.email:
            _regler(lignes, statut=StatutRelance.SANS_ADRESSE)
            return 0
        try:
            contexte = _contexte(destinataire, lignes)
            send_mail_template(
                [destinataire.email],
                f"Suivi des recommandations : {len(lignes)} action(s) à traiter",
                "relance_actions",
                contexte,
                cc=_copies(lignes, destinataire) or None,
            )
        except ERREURS_ENVOI as exc:
            # Seul le type est conservé : le message du relais peut contenir des détails d'infra.
            logger.warning("Échec d'envoi de relance (destinataire %s) : %r", destinataire_id, exc)
            for r in lignes:
                _regler(
                    [r],
                    statut=StatutRelance.ECHEC,
                    tentatives=r.tentatives + 1,
                    erreur=type(exc).__name__[:500],
                )
            return 0
        _regler(lignes, statut=StatutRelance.ENVOYEE, envoyee_le=timezone.now(), erreur="")
        return len(lignes)


def executer_relances(aujourd_hui: date | None = None, *, asynchrone: bool = False) -> int:
    """Planifie puis envoie (`asynchrone` : via Celery) ; renvoie le nombre d'e-mails traités."""
    planifier_relances(aujourd_hui)
    lots = regrouper_par_destinataire(settings.RELANCES_MAX_EMAILS_PAR_EXECUTION)
    for destinataire_id, ids in lots:
        cles = [str(i) for i in ids]
        if asynchrone:
            from .tasks import envoyer_lot_relances

            envoyer_lot_relances.delay(destinataire_id, cles)
        else:
            envoyer_lot(destinataire_id, cles)
    return len(lots)


def simuler(aujourd_hui: date | None = None) -> list[tuple[Mission, SuiviAction, str, bool]]:
    """Ce que l'exécution ferait, sans rien écrire : (mission, suivi, palier, déjà planifiée)."""
    jour = aujourd_hui or timezone.localdate()
    resultat = []
    for s in _suivis_relancables().select_related("mission"):
        palier = palier_atteint(s.echeance, jour)
        if palier is None:
            continue
        deja = Relance.all_objects.filter(
            suivi=s, palier=palier, echeance_reference=s.echeance
        ).exists()
        resultat.append((s.mission, s, PalierRelance(palier).label, deja))
    return resultat

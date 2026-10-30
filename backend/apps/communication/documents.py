"""Types de documents du lot 7 enregistrés auprès du moteur de documents (lot 4, D10, D13).

Les fournisseurs construisent le contexte depuis les données figées : le rapport final dérive de
`confirmation.donnees` (donc de l'instantané signé), le rapport provisoire de
`RapportProvisoire.instantane`. Appelé par `CommunicationConfig.ready` ; l'enregistrement est
idempotent. Le type `PLAN_ACTIONS` est fourni par `apps.recommandations.documents`.
"""

from typing import Any
from uuid import UUID

from django.db.models import F, OuterRef, Subquery
from django.db.models.functions import JSONObject
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.constats.models import (
    CategorieCause,
    Constat,
    PositionAudite,
    PrioriteRecommandation,
    ReponseAudite,
    StatutConstat,
)
from apps.core.exceptions import RegleMetierError
from apps.documents.generators.missions import _chef, _date, _heure, contexte_mission
from apps.documents.moteur.registre import TypeDocument, enregistrer_type
from apps.missions.acces import missions_visibles, peut_contribuer
from apps.missions.models import Mission, Reunion, StatutEtape, TypeReunion
from apps.missions.services.declarations import nom_complet
from apps.missions.services.suivi import fiche_de_suivi
from apps.referentiel.models import NiveauRisque
from apps.signatures.models import Confirmation, ModeSignature
from apps.users.models import User

from . import contrats
from .droits import peut_lire_rapport_interne
from .models import Rapport, RapportProvisoire, StatutRapport
from .services.assemblage import _points_forts

MODELE_NUMERO = "{mission}/{code}-{sequence:02d}"
MSG_PV_NON_TENU = "Marquez la réunion de clôture comme tenue avant de générer le PV."
MSG_NON_VALIDE = "Le rapport n'est pas encore validé."
MSG_DIFFUSE = "Le rapport est diffusé : émettez un rapport corrigé."
STATUTS_DIFFUSES = (StatutRapport.DIFFUSE, StatutRapport.REMPLACE)
ETIQUETTES_ENGAGEMENT = {
    "CONFIRME": "Confirmé",
    "A_RENOUVELER": "À renouveler",
    "NON_CONFIRME": "Non confirmé",
}
_RANG_NIVEAU = {NiveauRisque.ELEVE: 0, NiveauRisque.MOYEN: 1, NiveauRisque.FAIBLE: 2}


def _s(valeur: Any) -> str:
    return "" if valeur is None else str(valeur)


def _libelle(enum: Any, valeur: Any) -> str:
    return str(enum(valeur).label) if valeur in enum.values else _s(valeur)


def _position(donnees: dict[str, Any] | None) -> str:
    if not donnees:
        return ""
    position = _libelle(PositionAudite, donnees.get("position"))
    commentaire = _s(donnees.get("commentaire")).strip()
    return f"{position} — {commentaire}" if commentaire else position


def _causes_texte(causes: dict[str, list[str]] | None) -> str:
    return "\n".join(
        f"{_libelle(CategorieCause, categorie)} : {' ; '.join(descriptions)}"
        for categorie, descriptions in (causes or {}).items()
    )


def _recommandations_texte(recommandations: list[dict[str, Any]]) -> str:
    lignes: list[str] = []
    for r in recommandations:
        priorite = _libelle(PrioriteRecommandation, r.get("priorite"))
        lignes.append(f"{r.get('ordre')}. {_s(r.get('libelle'))} (Priorité : {priorite})")
        acceptation = r.get("acceptation")
        if acceptation:
            lignes.append(f"Risque accepté : {_s(acceptation.get('justification'))}")
    return "\n".join(lignes)


def _constat_rapport(c: dict[str, Any]) -> dict[str, Any]:
    recommandations = c.get("recommandations") or []
    reponse = c.get("reponse_direction") or {}
    return {
        "reference": _s(c.get("reference")),
        "titre": _s(c.get("titre")),
        "entite": _s(c.get("entite")),
        "niveau": _libelle(NiveauRisque, c.get("niveau")),
        "fait_constate": _s(c.get("fait_constate")),
        "referentiel": _s(c.get("referentiel")),
        "causes_texte": _causes_texte(c.get("causes")),
        "consequence": _s(c.get("consequence")),
        "conclusion": _s(c.get("conclusion")),
        "position_audite": _position(c.get("position_audite")),
        "reponse_direction": _s(reponse.get("commentaire")),
        "recommandations_texte": _recommandations_texte(recommandations),
        "plan_actions": [
            {
                "reference": _s(a.get("reference")),
                "libelle": _s(a.get("libelle")),
                "responsable": _s(a.get("responsable")),
                "echeance": _date(a.get("echeance")),
                "indicateur": _s(a.get("indicateur")),
            }
            for r in recommandations
            for a in r.get("actions") or []
        ],
    }


def _totaux(donnees: dict[str, Any]) -> dict[str, str]:
    totaux = donnees.get("totaux") or {}
    par_niveau = totaux.get("par_niveau") or {}
    constats = donnees.get("constats") or []
    return {
        "nb_constats": str(len(constats)),
        "nb_eleves": str(par_niveau.get(NiveauRisque.ELEVE, 0)),
        "nb_moyens": str(par_niveau.get(NiveauRisque.MOYEN, 0)),
        "nb_faibles": str(par_niveau.get(NiveauRisque.FAIBLE, 0)),
        "nb_recommandations": str(sum(len(c.get("recommandations") or []) for c in constats)),
        "nb_actions": str(totaux.get("nb_actions", 0)),
    }


def _points_forts_rapport(donnees: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "code": _s(p.get("code")),
            "libelle": _s(p.get("libelle")),
            "commentaire": _s(p.get("commentaire")),
        }
        for p in donnees.get("points_forts") or []
    ]


def _validation(confirmation: Confirmation | None) -> dict[str, str]:
    if confirmation is None:
        return dict(contrats.VALIDATION_VIDE)
    return {
        "par": nom_complet(confirmation.signataire),
        "le": _date(confirmation.confirme_le),
        "heure": _heure(confirmation.confirme_le),
        "empreinte": confirmation.empreinte,
        "mode": str(ModeSignature(confirmation.mode).label),
    }


def _mention_correction(rapport: dict[str, Any]) -> str:
    remplace = rapport.get("corrige_de")
    if remplace is None:
        return ""
    mention = f"Rapport corrigé — remplace le rapport {remplace}"
    motif = _s(rapport.get("motif_correction")).strip()
    return f"{mention}. Motif : {motif}" if motif else mention


def _sections(donnees: dict[str, Any]) -> dict[str, str]:
    s = donnees.get("sections") or {}
    objectifs = _s(s.get("objectifs_texte")) or "\n".join(
        f"{o.get('code')} — {o.get('libelle')}" for o in donnees.get("objectifs") or []
    )
    return {
        "synthese": _s(s.get("synthese")),
        "appreciation": _s(s.get("appreciation_libelle")),
        "commentaire_appreciation": _s(s.get("commentaire_appreciation")),
        "contexte": _s(s.get("contexte")),
        "objectifs": objectifs,
        "perimetre": _s(s.get("perimetre_texte")),
        "methodologie": _s(s.get("methodologie")),
        "conclusion": _s(s.get("conclusion")),
        "annexes": _s(s.get("annexes_texte")),
    }


def _contexte_rapport(
    donnees: dict[str, Any],
    *,
    provisoire: bool,
    date_limite: str,
    confirmation: Confirmation | None,
) -> dict[str, Any]:
    rapport = donnees.get("rapport") or {}
    return {
        "mission": donnees["mission"],
        "rapport": {
            "numero_version": _s(rapport.get("numero_version")),
            "mention_correction": _mention_correction(rapport),
            "provisoire": "Oui" if provisoire else "",
            "date_limite_reponses": date_limite,
        },
        "sections": _sections(donnees),
        "constats": [_constat_rapport(c) for c in donnees.get("constats") or []],
        "points_forts": _points_forts_rapport(donnees),
        "totaux": _totaux(donnees),
        "engagements": [
            {
                "responsable": _s(e.get("responsable")),
                "nb_actions": _s(e.get("nb_actions")),
                "etat": ETIQUETTES_ENGAGEMENT.get(_s(e.get("etat")), _s(e.get("etat"))),
            }
            for e in donnees.get("engagements") or []
        ],
        "validation": _validation(confirmation),
    }


def _contexte_note(donnees: dict[str, Any], confirmation: Confirmation | None) -> dict[str, Any]:
    s = donnees.get("sections") or {}
    eleves = []
    for c in donnees.get("constats") or []:
        if c.get("niveau") != NiveauRisque.ELEVE:
            continue
        recommandations = c.get("recommandations") or []
        eleves.append(
            {
                "reference": _s(c.get("reference")),
                "titre": _s(c.get("titre")),
                "recommandation_principale": _s(recommandations[0].get("libelle"))
                if recommandations
                else "",
            }
        )
    return {
        "mission": donnees["mission"],
        "synthese": _s(s.get("note_synthetique")) or _s(s.get("synthese")),
        "appreciation": _s(s.get("appreciation_libelle")),
        "commentaire_appreciation": _s(s.get("commentaire_appreciation")),
        "constats_eleves": eleves,
        "totaux": _totaux(donnees),
        "validation": _validation(confirmation),
    }


# ---------------------------------------------------------------- Rapports (final, note)


class FournisseurRapport:
    """Objet source : le `Rapport`. `note=True` : la note synthétique (même règles, D10, D13)."""

    def __init__(self, *, note: bool) -> None:
        self.note = note

    def objet(self, objet_id: UUID) -> Rapport:
        return get_object_or_404(Rapport, pk=objet_id)

    def mission_de(self, objet: Rapport) -> Mission:
        return objet.mission

    def objets_de_mission(self, mission: Mission) -> list[Rapport]:
        return list(Rapport.objects.filter(mission=mission).order_by("numero_version"))

    def peut_consulter(self, user: User, objet: Rapport) -> bool:
        mission = objet.mission
        if objet.statut in STATUTS_DIFFUSES:
            return missions_visibles(user).filter(pk=mission.pk).exists()
        return peut_lire_rapport_interne(user, mission)

    def peut_generer(self, user: User, objet: Rapport) -> bool:
        return peut_contribuer(user, objet.mission)

    def raison_non_generable(self, objet: Rapport) -> str | None:
        if objet.statut in STATUTS_DIFFUSES:
            return MSG_DIFFUSE
        if objet.statut != StatutRapport.VALIDE or objet.confirmation_validation_id is None:
            return MSG_NON_VALIDE
        return None

    def contexte(self, objet: Rapport) -> dict[str, Any]:
        confirmation = objet.confirmation_validation
        if confirmation is None:
            raise RegleMetierError(MSG_NON_VALIDE)
        if self.note:
            return _contexte_note(confirmation.donnees, confirmation)
        return _contexte_rapport(
            confirmation.donnees, provisoire=False, date_limite="", confirmation=confirmation
        )

    def confirmation(self, objet: Rapport) -> Confirmation | None:
        return objet.confirmation_validation


# ------------------------------------------------------------------- Rapport provisoire


class FournisseurRapportProvisoire:
    """Objet source : le `RapportProvisoire` transmis (instantané immuable, D6)."""

    def objet(self, objet_id: UUID) -> RapportProvisoire:
        return get_object_or_404(RapportProvisoire, pk=objet_id)

    def mission_de(self, objet: RapportProvisoire) -> Mission:
        return objet.mission

    def objets_de_mission(self, mission: Mission) -> list[RapportProvisoire]:
        return list(RapportProvisoire.objects.filter(mission=mission).order_by("numero"))

    def peut_consulter(self, user: User, objet: RapportProvisoire) -> bool:
        return missions_visibles(user).filter(pk=objet.mission_id).exists()

    def peut_generer(self, user: User, objet: RapportProvisoire) -> bool:
        return peut_contribuer(user, objet.mission)

    def raison_non_generable(self, objet: RapportProvisoire) -> str | None:
        return None

    def contexte(self, objet: RapportProvisoire) -> dict[str, Any]:
        return _contexte_rapport(
            objet.instantane,
            provisoire=True,
            date_limite=_date(objet.date_limite_reponses),
            confirmation=None,
        )

    def confirmation(self, objet: RapportProvisoire) -> Confirmation | None:
        return None


# ------------------------------------------------------------------------ PV de clôture


def _constats_presentes(mission: Mission) -> list[dict[str, str]]:
    position = (
        ReponseAudite.objects.filter(constat=OuterRef("pk"), cycle=OuterRef("cycle"))
        .order_by("-created_at", "-pk")
        .values(j=JSONObject(position=F("position"), commentaire=F("commentaire")))[:1]
    )
    constats = Constat.objects.filter(mission=mission, statut=StatutConstat.VALIDE).annotate(
        position_json=Subquery(position)
    )
    lignes: list[Any] = sorted(constats, key=lambda c: (_RANG_NIVEAU.get(c.niveau, 3), c.reference))
    return [
        {
            "reference": c.reference,
            "titre": c.titre,
            "niveau": _libelle(NiveauRisque, c.niveau),
            "position_audite": _position(c.position_json),
        }
        for c in lignes
    ]


def _date_limite_provisoire(mission: Mission) -> str:
    limite = (
        RapportProvisoire.objects.filter(mission=mission)
        .order_by("-numero")
        .values_list("date_limite_reponses", flat=True)
        .first()
    )
    return _date(limite)


class FournisseurPvCloture:
    """Objet source : la réunion de clôture (CLOTURE) de la mission."""

    def objet(self, objet_id: UUID) -> Reunion:
        reunion: Reunion | None = Reunion.objects.filter(
            pk=objet_id, type=TypeReunion.CLOTURE
        ).first()
        if reunion is None:
            raise Http404("Réunion de clôture introuvable.")
        return reunion

    def mission_de(self, objet: Reunion) -> Mission:
        return objet.mission

    def objets_de_mission(self, mission: Mission) -> list[Reunion]:
        reunion = Reunion.objects.filter(mission=mission, type=TypeReunion.CLOTURE).first()
        return [reunion] if reunion else []

    def peut_consulter(self, user: User, objet: Reunion) -> bool:
        return missions_visibles(user).filter(pk=objet.mission_id).exists()

    def peut_generer(self, user: User, objet: Reunion) -> bool:
        return peut_contribuer(user, objet.mission)

    def raison_non_generable(self, objet: Reunion) -> str | None:
        return None if objet.tenue_le else MSG_PV_NON_TENU

    def contexte(self, objet: Reunion) -> dict[str, Any]:
        mission = objet.mission
        chef = _chef(mission)
        participants = [
            {"nom": nom_complet(u), "fonction": u.fonction, "direction": u.direction_code}
            for u in objet.participants.order_by("last_name", "first_name", "username")
        ]
        externes = [
            ligne.strip() for ligne in objet.participants_externes.splitlines() if ligne.strip()
        ]
        return {
            "mission": contexte_mission(mission),
            "reunion": {
                "date": _date(objet.date),
                "heure": _heure(objet.date),
                "lieu": objet.lieu,
                "ordre_du_jour": objet.ordre_du_jour,
                "decisions": objet.decisions,
                "compte_rendu": objet.compte_rendu,
                "tenue_le": _date(objet.tenue_le),
                "participants": participants,
                "participants_externes": externes,
                "redacteur": nom_complet(chef) if chef else "",
            },
            "constats_presentes": _constats_presentes(mission),
            "points_forts": [
                {"code": p["code"], "libelle": p["libelle"], "commentaire": p["commentaire"]}
                for p in _points_forts(mission)
            ],
            "modalites": {"date_limite_reponses": _date_limite_provisoire(mission)},
        }

    def confirmation(self, objet: Reunion) -> Confirmation | None:
        return None


# ------------------------------------------------------------- Fiche de suivi de mission


class FournisseurFicheSuivi:
    """Objet source : la mission ; données : `fiche_de_suivi` (lot 3)."""

    def objet(self, objet_id: UUID) -> Mission:
        return get_object_or_404(Mission, pk=objet_id)

    def mission_de(self, objet: Mission) -> Mission:
        return objet

    def objets_de_mission(self, mission: Mission) -> list[Mission]:
        return [mission]

    def peut_consulter(self, user: User, objet: Mission) -> bool:
        return peut_lire_rapport_interne(user, objet)

    def peut_generer(self, user: User, objet: Mission) -> bool:
        return peut_contribuer(user, objet)

    def raison_non_generable(self, objet: Mission) -> str | None:
        return None

    def contexte(self, objet: Mission) -> dict[str, Any]:
        fiche = fiche_de_suivi(objet)
        return {
            "mission": contexte_mission(objet),
            "lignes": [
                {
                    "etape": f"{ligne.romain} — {ligne.titre}",
                    "statut": _libelle(StatutEtape, ligne.statut),
                    "debut_prevu": _date(ligne.debut_prevu),
                    "fin_prevue": _date(ligne.fin_prevue),
                    "debut_reel": _date(ligne.debut_reel),
                    "fin_reelle": _date(ligne.fin_reelle),
                    "ecart": _s(ligne.ecart_jours),
                    "charge_prevue": _s(ligne.charge_prevue),
                    "charge_reelle": _s(ligne.charge_reelle),
                }
                for ligne in fiche.lignes
            ],
            "totaux": {
                "budget_jours": _s(fiche.budget_jours),
                "charge_prevue": _s(fiche.total_prevu),
                "charge_reelle": _s(fiche.total_reel),
            },
        }

    def confirmation(self, objet: Mission) -> Confirmation | None:
        return None


# --------------------------------------------------------------------------- Registre

# code -> (contrat, étape, abréviation, fournisseur) ; abréviations de D10.
_TYPES: dict[str, tuple[Any, int, str, Any]] = {
    "PV_CLOTURE": (contrats.CONTRAT_PV_CLOTURE, 15, "PVC", FournisseurPvCloture()),
    "RAPPORT_PROVISOIRE": (
        contrats.CONTRAT_RAPPORT_PROVISOIRE,
        15,
        "RPP",
        FournisseurRapportProvisoire(),
    ),
    "RAPPORT_FINAL": (
        contrats.CONTRAT_RAPPORT_FINAL,
        18,
        "RAP",
        FournisseurRapport(note=False),
    ),
    "NOTE_SYNTHETIQUE": (
        contrats.CONTRAT_NOTE_SYNTHETIQUE,
        18,
        "NS",
        FournisseurRapport(note=True),
    ),
    "FICHE_SUIVI_MISSION": (
        contrats.CONTRAT_FICHE_SUIVI_MISSION,
        18,
        "FSM",
        FournisseurFicheSuivi(),
    ),
}


def enregistrer_types() -> None:
    """Enregistre les cinq types de la communication ; idempotent si l'application recharge."""
    for code, (contrat, etape, abreviation, fournisseur) in _TYPES.items():
        try:
            enregistrer_type(
                TypeDocument(
                    code=code,
                    libelle=contrat.libelle,
                    etape=etape,
                    contrat=contrat,
                    abreviation=abreviation,
                    modele_numero=MODELE_NUMERO,
                    portee_numero="MISSION",
                    fournisseur=fournisseur,
                )
            )
        except ValueError:
            continue

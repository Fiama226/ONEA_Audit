"""Document types « Ordre de mission » and « PV de la réunion d'ouverture » (lot 4, task 11).

Lot 3 data is read through its public services and models only.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from django.http import Http404
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.models import BaseModel
from apps.missions.acces import missions_visibles, peut_contribuer
from apps.missions.models import Mission, Reunion, RoleMission, TypeReunion
from apps.missions.services.declarations import nom_complet
from apps.signatures.models import Confirmation, ModeSignature, TypeDocumentSignable
from apps.signatures.services import derniere_confirmation
from apps.users.models import Role, User

from .. import signaux  # noqa: F401  (connects the D13 receiver)
from ..moteur.contrats import BLOC_MISSION, EXEMPLE_COMMUN, Champ, Contrat, TypeChamp
from ..moteur.registre import TypeDocument, enregistrer_type

MODELE_NUMERO = "{mission}/{code}-{sequence}"
FONCTION_RAI = "Responsable de l'Audit Interne"
MSG_ORDRE_NON_EMIS = "Émettez l'ordre de mission avant de générer le document."
MSG_PV_NON_TENU = "Marquez la réunion d'ouverture comme tenue avant de générer le PV."

ContexteMission = dict[str, str | list[dict[str, str]]]


def _date(valeur: date | datetime | str | None) -> str:
    """JJ/MM/AAAA from a date, a datetime (local time) or an ISO string ('' when empty)."""
    if not valeur:
        return ""
    if isinstance(valeur, str):
        valeur = datetime.fromisoformat(valeur)
    if isinstance(valeur, datetime) and timezone.is_aware(valeur):
        valeur = timezone.localtime(valeur)
    return valeur.strftime("%d/%m/%Y")


def _heure(valeur: datetime | None) -> str:
    return timezone.localtime(valeur).strftime("%H:%M") if valeur else ""


def _periode(debut: date | str | None, fin: date | str | None) -> str:
    if debut and fin:
        return f"du {_date(debut)} au {_date(fin)}"
    if debut:
        return f"à partir du {_date(debut)}"
    if fin:
        return f"jusqu'au {_date(fin)}"
    return ""


def _chef(mission: Mission) -> User | None:
    affectation = (
        mission.affectations.filter(role_mission=RoleMission.CHEF_MISSION)
        .select_related("utilisateur")
        .first()
    )
    return affectation.utilisateur if affectation else None


def contexte_mission(mission: Mission) -> ContexteMission:
    """The `mission` block of the contracts (strings only; reusable by other lots)."""
    processus = [{"code": p.code, "libelle": p.libelle} for p in mission.processus.order_by("code")]
    entites = [{"code": d.code, "libelle": d.libelle} for d in mission.entites.order_by("code")]
    chef = _chef(mission)
    return {
        "reference": mission.reference,
        "titre": mission.titre,
        "type": mission.get_type_display(),
        "processus": processus,
        "processus_texte": ", ".join(p["libelle"] for p in processus),
        "entites": entites,
        "entites_texte": ", ".join(e["libelle"] for e in entites),
        "periode": _periode(mission.periode_debut, mission.periode_fin),
        "date_debut_prevue": _date(mission.date_debut_prevue),
        "date_fin_prevue": _date(mission.date_fin_prevue),
        "chef_mission": nom_complet(chef) if chef else "",
    }


_EXEMPLE_MISSION: dict[str, Any] = {
    "reference": "DAI/2026/M01",
    "titre": "Audit du processus d'achat",
    "type": "Assurance",
    "processus": [{"code": "ACH", "libelle": "Achats"}],
    "processus_texte": "Achats",
    "entites": [{"code": "DCL", "libelle": "Direction du Commerce et de la Clientèle"}],
    "entites_texte": "Direction du Commerce et de la Clientèle",
    "periode": "du 01/01/2025 au 31/12/2025",
    "date_debut_prevue": "01/03/2026",
    "date_fin_prevue": "30/04/2026",
    "chef_mission": "Aminata Ouédraogo",
}


# ---------------------------------------------------------------- Ordre de mission

CONTRAT_ORDRE_MISSION = Contrat(
    code="ORDRE_MISSION",
    libelle="Ordre de mission",
    version=1,
    champs=(
        BLOC_MISSION,
        Champ(
            "ordre",
            TypeChamp.BLOC,
            "Ordre de mission tel que confirmé",
            (
                Champ("objectifs", TypeChamp.TEXTE_LONG, "Objectifs de la mission"),
                Champ("perimetre", TypeChamp.TEXTE_LONG, "Périmètre de la mission"),
                Champ("exclusions", TypeChamp.TEXTE_LONG, "Exclusions"),
                Champ("clients", TypeChamp.TEXTE_LONG, "Clients de la mission"),
                Champ("livrables_attendus", TypeChamp.TEXTE_LONG, "Livrables attendus"),
                Champ("periode", TypeChamp.TEXTE, "Période auditée"),
                Champ("date_debut_prevue", TypeChamp.TEXTE, "Date de début prévue (JJ/MM/AAAA)"),
                Champ("date_fin_prevue", TypeChamp.TEXTE, "Date de fin prévue (JJ/MM/AAAA)"),
                Champ(
                    "equipe",
                    TypeChamp.LISTE,
                    "Équipe de la mission",
                    (
                        Champ("nom", TypeChamp.TEXTE, "Nom de l'intervenant"),
                        Champ("role", TypeChamp.TEXTE, "Rôle dans la mission"),
                    ),
                ),
            ),
        ),
        Champ(
            "signature",
            TypeChamp.BLOC,
            "Confirmation horodatée de l'ordre",
            (
                Champ("signataire", TypeChamp.TEXTE, "Nom du signataire"),
                Champ("fonction", TypeChamp.TEXTE, "Fonction du signataire"),
                Champ("date", TypeChamp.TEXTE, "Date de la confirmation (JJ/MM/AAAA)"),
                Champ("heure", TypeChamp.TEXTE, "Heure de la confirmation (HH:MM)"),
                Champ("empreinte", TypeChamp.TEXTE, "Empreinte SHA-256 de la confirmation"),
                Champ("texte", TypeChamp.TEXTE_LONG, "Texte confirmé"),
                Champ("mode", TypeChamp.TEXTE, "Mode de signature"),
            ),
        ),
    ),
    exemple=EXEMPLE_COMMUN
    | {
        "mission": _EXEMPLE_MISSION,
        "ordre": {
            "objectifs": "Évaluer le dispositif de contrôle interne des achats.",
            "perimetre": "Direction des achats, exercice 2025.",
            "exclusions": "Achats de moins de 100 000 FCFA.",
            "clients": "Direction générale",
            "livrables_attendus": "Rapport d'audit\nPlan d'actions",
            "periode": "du 01/01/2025 au 31/12/2025",
            "date_debut_prevue": "01/03/2026",
            "date_fin_prevue": "30/04/2026",
            "equipe": [
                {"nom": "Aminata Ouédraogo", "role": "Chef de mission"},
                {"nom": "Issa Sawadogo", "role": "Auditeur"},
            ],
        },
        "signature": {
            "signataire": "Prénom Nom",
            "fonction": FONCTION_RAI,
            "date": "28/10/2026",
            "heure": "09:30",
            "empreinte": "0" * 64,
            "texte": "Je soussigné(e) Prénom Nom, Responsable de l'Audit Interne, émets l'ordre.",
            "mode": "Confirmation horodatée",
        },
    },
)


def _mission(objet: BaseModel) -> Mission:
    if not isinstance(objet, Mission):
        raise TypeError("Mission attendue.")
    return objet


def _reunion(objet: BaseModel) -> Reunion:
    if not isinstance(objet, Reunion):
        raise TypeError("Réunion attendue.")
    return objet


def _libelle_role(code: str) -> str:
    return str(RoleMission(code).label) if code in RoleMission.values else code


def fonction_signataire(user: User) -> str:
    """Fonction du signataire (`User.fonction`), à défaut le titre du RAI."""
    return user.fonction.strip() or FONCTION_RAI


def _chaine(valeur: Any) -> str:
    return "" if valeur is None else str(valeur)


def _contexte_ordre(mission: Mission, confirmation: Confirmation) -> dict[str, Any]:
    d = confirmation.donnees
    return {
        "mission": contexte_mission(mission),
        "ordre": {
            "objectifs": _chaine(d.get("objectifs")),
            "perimetre": _chaine(d.get("perimetre")),
            "exclusions": _chaine(d.get("exclusions")),
            "clients": _chaine(d.get("clients")),
            "livrables_attendus": _chaine(d.get("livrables_attendus")),
            "periode": _periode(d.get("periode_debut"), d.get("periode_fin")),
            "date_debut_prevue": _date(d.get("date_debut_prevue")),
            "date_fin_prevue": _date(d.get("date_fin_prevue")),
            "equipe": [
                {
                    "nom": _chaine(m.get("nom")),
                    "role": _libelle_role(_chaine(m.get("role_mission"))),
                }
                for m in d.get("equipe", [])
            ],
        },
        "signature": {
            "signataire": nom_complet(confirmation.signataire),
            "fonction": fonction_signataire(confirmation.signataire),
            "date": _date(confirmation.confirme_le),
            "heure": _heure(confirmation.confirme_le),
            "empreinte": confirmation.empreinte,
            "texte": confirmation.texte,
            "mode": str(ModeSignature(confirmation.mode).label),
        },
    }


class FournisseurOrdreMission:
    """Source object: the mission; data: the last ORDRE_MISSION confirmation."""

    def objet(self, objet_id: UUID) -> BaseModel:
        mission = Mission.objects.filter(pk=objet_id).first()
        if mission is None:
            raise Http404("Mission introuvable.")
        return mission

    def mission_de(self, objet: BaseModel) -> Mission:
        return _mission(objet)

    def objets_de_mission(self, mission: Mission) -> list[BaseModel]:
        return [mission]

    def peut_consulter(self, user: User, objet: BaseModel) -> bool:
        return missions_visibles(user).filter(pk=objet.pk).exists()

    def peut_generer(self, user: User, objet: BaseModel) -> bool:
        return user.role == Role.RAI

    def raison_non_generable(self, objet: BaseModel) -> str | None:
        return None if self.confirmation(objet) else MSG_ORDRE_NON_EMIS

    def contexte(self, objet: BaseModel) -> dict[str, Any]:
        confirmation = self.confirmation(objet)
        if confirmation is None:
            raise RegleMetierError(MSG_ORDRE_NON_EMIS)
        return _contexte_ordre(self.mission_de(objet), confirmation)

    def confirmation(self, objet: BaseModel) -> Confirmation | None:
        return derniere_confirmation(objet, TypeDocumentSignable.ORDRE_MISSION)


# --------------------------------------------------------------- PV d'ouverture

CONTRAT_PV_OUVERTURE = Contrat(
    code="PV_OUVERTURE",
    libelle="PV de la réunion d'ouverture",
    version=1,
    champs=(
        BLOC_MISSION,
        Champ(
            "reunion",
            TypeChamp.BLOC,
            "Réunion d'ouverture",
            (
                Champ("date", TypeChamp.TEXTE, "Date de la réunion (JJ/MM/AAAA)"),
                Champ("heure", TypeChamp.TEXTE, "Heure de la réunion (HH:MM)"),
                Champ("lieu", TypeChamp.TEXTE, "Lieu de la réunion"),
                Champ("ordre_du_jour", TypeChamp.TEXTE_LONG, "Ordre du jour"),
                Champ("decisions", TypeChamp.TEXTE_LONG, "Décisions prises"),
                Champ("compte_rendu", TypeChamp.TEXTE_LONG, "Compte rendu"),
                Champ("tenue_le", TypeChamp.TEXTE, "Date à laquelle la réunion a été tenue"),
                Champ(
                    "participants",
                    TypeChamp.LISTE,
                    "Participants",
                    (
                        Champ("nom", TypeChamp.TEXTE, "Nom du participant"),
                        Champ("fonction", TypeChamp.TEXTE, "Fonction"),
                        Champ("direction", TypeChamp.TEXTE, "Direction (code)"),
                    ),
                ),
                Champ("participants_externes", TypeChamp.LISTE, "Participants externes"),
                Champ("redacteur", TypeChamp.TEXTE, "Rédacteur du PV (chef de mission)"),
            ),
        ),
    ),
    exemple=EXEMPLE_COMMUN
    | {
        "mission": _EXEMPLE_MISSION,
        "reunion": {
            "date": "02/03/2026",
            "heure": "09:00",
            "lieu": "Salle de réunion du siège",
            "ordre_du_jour": "Présentation de la mission\nCalendrier",
            "decisions": "Les accès aux données sont ouverts dès le 03/03/2026.",
            "compte_rendu": "La réunion s'est tenue en présence de la direction auditée.",
            "tenue_le": "02/03/2026",
            "participants": [
                {"nom": "Mme Kaboré", "fonction": "Directrice", "direction": "DCL"},
            ],
            "participants_externes": ["M. Traoré — Cabinet partenaire"],
            "redacteur": "Aminata Ouédraogo",
        },
    },
)


class FournisseurPvOuverture:
    """Source object: the opening meeting (OUVERTURE) of the mission."""

    def objet(self, objet_id: UUID) -> BaseModel:
        reunion: Reunion | None = Reunion.objects.filter(
            pk=objet_id, type=TypeReunion.OUVERTURE
        ).first()
        if reunion is None:
            raise Http404("Réunion d'ouverture introuvable.")
        return reunion

    def mission_de(self, objet: BaseModel) -> Mission:
        return _reunion(objet).mission

    def objets_de_mission(self, mission: Mission) -> list[BaseModel]:
        reunion = Reunion.objects.filter(mission=mission, type=TypeReunion.OUVERTURE).first()
        return [reunion] if reunion else []

    def peut_consulter(self, user: User, objet: BaseModel) -> bool:
        return missions_visibles(user).filter(pk=self.mission_de(objet).pk).exists()

    def peut_generer(self, user: User, objet: BaseModel) -> bool:
        return peut_contribuer(user, self.mission_de(objet))

    def raison_non_generable(self, objet: BaseModel) -> str | None:
        return None if _reunion(objet).tenue_le else MSG_PV_NON_TENU

    def contexte(self, objet: BaseModel) -> dict[str, Any]:
        objet = _reunion(objet)
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
        }

    def confirmation(self, objet: BaseModel) -> Confirmation | None:
        return None


enregistrer_type(
    TypeDocument(
        code="ORDRE_MISSION",
        libelle="Ordre de mission",
        etape=1,
        contrat=CONTRAT_ORDRE_MISSION,
        abreviation="OM",
        modele_numero=MODELE_NUMERO,
        portee_numero="MISSION",
        fournisseur=FournisseurOrdreMission(),
    )
)
enregistrer_type(
    TypeDocument(
        code="PV_OUVERTURE",
        libelle="PV de la réunion d'ouverture",
        etape=2,
        contrat=CONTRAT_PV_OUVERTURE,
        abreviation="PVO",
        modele_numero=MODELE_NUMERO,
        portee_numero="MISSION",
        fournisseur=FournisseurPvOuverture(),
    )
)

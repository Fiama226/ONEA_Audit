"""Type de document des constats enregistré auprès du moteur de documents (lot 4).

Contrat v1 : toute rupture exige une version 2. La page
`docs/documents/contrats/FICHE_OBSERVATION.md` est générée par
`python manage.py contrats_documents --ecrire`. L'objet source est le constat.
"""

from typing import Any
from uuid import UUID

from django.http import Http404

from apps.documents.moteur.contrats import BLOC_MISSION, EXEMPLE_COMMUN, Champ, Contrat, TypeChamp
from apps.documents.moteur.registre import TypeDocument, enregistrer_type
from apps.missions.acces import role_dans_mission
from apps.missions.models import ROLES_INTERVENANTS, Mission
from apps.signatures.models import Confirmation
from apps.users.models import Role, User

from .contextes import CODE_FICHE_OBSERVATION, contexte_fiche_observation
from .droits import constats_visibles
from .models import Constat, StatutConstat

T, TL, L, B = TypeChamp.TEXTE, TypeChamp.TEXTE_LONG, TypeChamp.LISTE, TypeChamp.BLOC

MSG_NON_SOUMIS = "Soumettez le constat avant de générer sa fiche d'observation."

_MISSION_EX: dict[str, Any] = {
    "reference": "DAI/2026/M01",
    "titre": "Audit du processus de passation des marchés",
    "type": "Mission planifiée",
    "processus": [{"code": "ACH", "libelle": "Achats"}],
    "processus_texte": "Achats",
    "entites": [{"code": "DAF", "libelle": "Direction administrative et financière"}],
    "entites_texte": "Direction administrative et financière",
    "periode": "01/01/2025 au 31/12/2025",
    "date_debut_prevue": "02/03/2026",
    "date_fin_prevue": "30/04/2026",
    "chef_mission": "A. Ouédraogo",
}

CONTRAT_FICHE_OBSERVATION = Contrat(
    code=CODE_FICHE_OBSERVATION,
    libelle="Fiche d'observation",
    version=1,
    champs=(
        BLOC_MISSION,
        Champ("provisoire", T, "« Oui » tant que le constat n'est pas validé, sinon vide"),
        Champ(
            "constat",
            B,
            "Constat",
            (
                Champ("reference", T, "Référence du constat (C-01)"),
                Champ("titre", T, "Titre"),
                Champ("entite", T, "Entité concernée"),
                Champ("processus", T, "Processus concerné"),
                Champ("fait_constate", TL, "Fait constaté"),
                Champ("referentiel", TL, "Référentiel (critère)"),
                Champ("consequence", TL, "Conséquence"),
                Champ("conclusion", TL, "Conclusion"),
                Champ("niveau", T, "Niveau du constat (vide tant qu'il n'est pas évalué)"),
                Champ("statut", T, "Statut du constat"),
                Champ("soumis_le", T, "Date de soumission (JJ/MM/AAAA)"),
                Champ("validee_le", T, "Date de validation (JJ/MM/AAAA)"),
            ),
        ),
        Champ(
            "causes",
            L,
            "Causes groupées par catégorie (méthode des 7M)",
            (
                Champ("categorie", T, "Catégorie de cause"),
                Champ("descriptions", L, "Descriptions des causes de la catégorie"),
            ),
        ),
        Champ(
            "recommandations",
            L,
            "Recommandations",
            (
                Champ("numero", T, "Numéro de la recommandation"),
                Champ("libelle", TL, "Recommandation"),
                Champ("priorite", T, "Priorité"),
            ),
        ),
        Champ(
            "reponse",
            B,
            "Dernière réponse de l'audité (vide s'il n'a pas répondu)",
            (
                Champ("position", T, "Accord ou Désaccord"),
                Champ("commentaire", TL, "Commentaire de l'audité"),
                Champ("le", T, "Date de la réponse (JJ/MM/AAAA)"),
            ),
        ),
    ),
    exemple=EXEMPLE_COMMUN
    | {
        "mission": _MISSION_EX,
        "provisoire": "",
        "constat": {
            "reference": "C-01",
            "titre": "Bons de commande à signature unique",
            "entite": "Direction administrative et financière",
            "processus": "Achats",
            "fait_constate": "Trois bons de commande sur 30 ne portent qu'une signature.",
            "referentiel": "Procédure d'achat, article 4.",
            "consequence": "Risque d'engagements non autorisés.",
            "conclusion": "Le contrôle n'est pas appliqué de façon systématique.",
            "niveau": "Élevé",
            "statut": "Validé",
            "soumis_le": "14/03/2026",
            "validee_le": "16/03/2026",
        },
        "causes": [
            {"categorie": "Méthodes", "descriptions": ["Procédure non diffusée."]},
            {"categorie": "Main-d'œuvre", "descriptions": ["Agents non formés."]},
        ],
        "recommandations": [
            {"numero": "1", "libelle": "Diffuser la procédure.", "priorite": "Haute"}
        ],
        "reponse": {"position": "Accord", "commentaire": "", "le": "18/03/2026"},
        "document": EXEMPLE_COMMUN["document"] | {"type": "Fiche d'observation"},
    },
)


def _intervenant(user: User, mission: Mission) -> bool:
    return user.role == Role.RAI or (
        user.role == Role.AUDITEUR and role_dans_mission(user, mission) in ROLES_INTERVENANTS
    )


class FournisseurFicheObservation:
    """L'objet source est le constat ; l'audité voit ceux qui lui sont soumis (D13)."""

    def objet(self, objet_id: UUID) -> Constat:
        try:
            constat: Constat = Constat.objects.select_related("mission").get(pk=objet_id)
            return constat
        except Constat.DoesNotExist:
            raise Http404 from None

    def mission_de(self, objet: Constat) -> Mission:
        return objet.mission

    def objets_de_mission(self, mission: Mission) -> list[Constat]:
        return list(Constat.objects.filter(mission=mission).order_by("numero"))

    def peut_consulter(self, user: User, objet: Constat) -> bool:
        return constats_visibles(user, objet.mission).filter(pk=objet.pk).exists()

    def peut_generer(self, user: User, objet: Constat) -> bool:
        return _intervenant(user, objet.mission)

    def raison_non_generable(self, objet: Constat) -> str | None:
        if objet.statut in (StatutConstat.SOUMIS, StatutConstat.VALIDE):
            return None
        return MSG_NON_SOUMIS

    def contexte(self, objet: Constat) -> dict[str, Any]:
        return contexte_fiche_observation(objet)

    def confirmation(self, objet: Constat) -> Confirmation | None:
        return None


def enregistrer_types() -> None:
    """Enregistre la fiche d'observation ; idempotent si l'application est rechargée."""
    try:
        enregistrer_type(
            TypeDocument(
                code=CODE_FICHE_OBSERVATION,
                libelle=CONTRAT_FICHE_OBSERVATION.libelle,
                etape=14,
                contrat=CONTRAT_FICHE_OBSERVATION,
                abreviation="FO",  # à confirmer avec l'ONEA
                modele_numero="{mission}/{code}-{sequence:02d}",
                portee_numero="MISSION",
                fournisseur=FournisseurFicheObservation(),  # type: ignore[arg-type]
            )
        )
    except ValueError:
        pass

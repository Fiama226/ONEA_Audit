"""Type de document « Plan d'actions » enregistré auprès du moteur de documents (lot 4, D10).

Contrat v1 : toute rupture exige une version 2. La page `docs/documents/contrats/PLAN_ACTIONS.md`
est générée par `contrats_documents --ecrire`. L'objet source est la mission. Appelé par
`RecommandationsConfig.ready` ; l'enregistrement est idempotent.
"""

from typing import Any
from uuid import UUID

from django.shortcuts import get_object_or_404

from apps.constats.models import PrioriteRecommandation
from apps.documents.generators.missions import _date, contexte_mission
from apps.documents.moteur.contrats import BLOC_MISSION, EXEMPLE_COMMUN, Champ, Contrat, TypeChamp
from apps.documents.moteur.registre import TypeDocument, enregistrer_type
from apps.missions.acces import peut_contribuer, role_dans_mission
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import ROLES_INTERVENANTS, EtapeMission, Mission
from apps.missions.services.declarations import nom_complet
from apps.signatures.models import Confirmation
from apps.users.models import Role, User

from .models import Action, StatutAction
from .services.statuts import LIBELLES
from .services.synthese import synthese_plan

CODE_PLAN_ACTIONS = "PLAN_ACTIONS"
ETAPE_PLAN = 16
ETIQUETTES_ENGAGEMENT = {
    "CONFIRME": "Confirmé",
    "A_RENOUVELER": "À renouveler",
    "NON_CONFIRME": "Non confirmé",
}

T, TL, L = TypeChamp.TEXTE, TypeChamp.TEXTE_LONG, TypeChamp.LISTE

CONTRAT_PLAN_ACTIONS = Contrat(
    code=CODE_PLAN_ACTIONS,
    libelle="Plan d'actions de mise en œuvre des recommandations",
    version=1,
    champs=(
        BLOC_MISSION,
        Champ("provisoire", T, "« Oui » tant que l'étape XVI n'est pas close, sinon vide"),
        Champ(
            "recommandations",
            L,
            "Recommandations des constats validés",
            (
                Champ("constat", T, "Référence du constat"),
                Champ("reference", T, "Référence de la recommandation"),
                Champ("priorite", T, "Priorité"),
                Champ("libelle", TL, "Recommandation"),
                Champ("statut", T, "Statut dérivé des actions"),
                Champ("acceptation", TL, "Justification de l'acceptation du risque (vide sinon)"),
            ),
        ),
        Champ(
            "actions",
            L,
            "Actions correctives",
            (
                Champ("reference", T, "Référence de l'action (A-nn)"),
                Champ("recommandation", T, "Référence de la recommandation"),
                Champ("libelle", TL, "Mesure corrective"),
                Champ("responsable", T, "Responsable"),
                Champ("echeance", T, "Échéance (JJ/MM/AAAA)"),
                Champ("indicateur", TL, "Indicateur de mise en œuvre"),
                Champ("moyens", TL, "Moyens (ressources et budget)"),
                Champ("statut", T, "Statut de l'action"),
            ),
        ),
        Champ(
            "engagements",
            L,
            "Engagement de chaque responsable",
            (
                Champ("responsable", T, "Responsable"),
                Champ("nb_actions", T, "Nombre d'actions"),
                Champ("prochaine_echeance", T, "Prochaine échéance (JJ/MM/AAAA)"),
                Champ("etat", T, "État de l'engagement"),
            ),
        ),
    ),
    exemple=EXEMPLE_COMMUN
    | {
        "mission": {
            "reference": "DAI/2026/M01",
            "titre": "Audit du processus de passation des marchés",
            "type": "Mission planifiée",
            "processus": [{"code": "ACH", "libelle": "Achats"}],
            "processus_texte": "Achats",
            "entites": [{"code": "DAF", "libelle": "Direction administrative et financière"}],
            "entites_texte": "Direction administrative et financière",
            "periode": "du 01/01/2025 au 31/12/2025",
            "date_debut_prevue": "02/03/2026",
            "date_fin_prevue": "30/04/2026",
            "chef_mission": "A. Ouédraogo",
        },
        "provisoire": "Oui",
        "recommandations": [
            {
                "constat": "C-01",
                "reference": "C-01-1",
                "priorite": "Haute",
                "libelle": "Rapprocher les factures des bons de livraison",
                "statut": "En cours",
                "acceptation": "",
            }
        ],
        "actions": [
            {
                "reference": "A-01",
                "recommandation": "C-01-1",
                "libelle": "Instaurer le rapprochement mensuel",
                "responsable": "A. Kaboré",
                "echeance": "30/06/2026",
                "indicateur": "Taux de factures rapprochées",
                "moyens": "Un agent à mi-temps",
                "statut": "En cours",
            }
        ],
        "engagements": [
            {
                "responsable": "A. Kaboré",
                "nb_actions": "1",
                "prochaine_echeance": "30/06/2026",
                "etat": "Confirmé",
            }
        ],
        "document": EXEMPLE_COMMUN["document"]
        | {"type": "Plan d'actions de mise en œuvre des recommandations"},
    },
)


def _interne(user: User, mission: Mission) -> bool:
    """RAI et intervenants de la mission : l'audité ne reçoit pas le plan complet (D13)."""
    if user.role == Role.RAI:
        return True
    return user.role == Role.AUDITEUR and role_dans_mission(user, mission) in ROLES_INTERVENANTS


def _reference(a: Action) -> str:
    return f"{a.recommandation.constat.reference}-{a.recommandation.ordre}"


class FournisseurPlanActions:
    """Fournisseur du moteur : l'objet source est la mission (un document par mission)."""

    def objet(self, objet_id: UUID) -> Mission:
        return get_object_or_404(Mission, pk=objet_id)

    def mission_de(self, objet: Mission) -> Mission:
        return objet

    def objets_de_mission(self, mission: Mission) -> list[Mission]:
        return [mission]

    def peut_consulter(self, user: User, objet: Mission) -> bool:
        return _interne(user, objet)

    def peut_generer(self, user: User, objet: Mission) -> bool:
        return peut_contribuer(user, objet)

    def raison_non_generable(self, objet: Mission) -> str | None:
        return None

    def contexte(self, objet: Mission) -> dict[str, Any]:
        synthese = synthese_plan(objet)
        actions = (
            Action.objects.filter(mission=objet)
            .select_related("responsable", "recommandation__constat")
            .order_by("numero")
        )
        statut_xvi = (
            EtapeMission.objects.filter(mission=objet, numero=ETAPE_PLAN)
            .values_list("statut", flat=True)
            .first()
        )
        return {
            "mission": contexte_mission(objet),
            "provisoire": "" if statut_xvi in STATUTS_ETAPE_CLOSE else "Oui",
            "recommandations": [
                {
                    "constat": ligne.constat,
                    "reference": ligne.reference,
                    "priorite": str(PrioriteRecommandation(ligne.priorite).label),
                    "libelle": ligne.libelle,
                    "statut": LIBELLES[ligne.statut_derive],
                    "acceptation": ligne.acceptation.justification if ligne.acceptation else "",
                }
                for ligne in synthese.recommandations
            ],
            "actions": [
                {
                    "reference": a.reference,
                    "recommandation": _reference(a),
                    "libelle": a.libelle,
                    "responsable": nom_complet(a.responsable) if a.responsable else "",
                    "echeance": _date(a.echeance),
                    "indicateur": a.indicateur,
                    "moyens": a.moyens,
                    "statut": str(StatutAction(a.statut).label),
                }
                for a in actions
            ],
            "engagements": [
                {
                    "responsable": nom_complet(ligne.utilisateur),
                    "nb_actions": str(ligne.nb_actions),
                    "prochaine_echeance": _date(ligne.prochaine_echeance),
                    "etat": ETIQUETTES_ENGAGEMENT[ligne.engagement],
                }
                for ligne in synthese.responsables
            ],
        }

    def confirmation(self, objet: Mission) -> Confirmation | None:
        return None


def enregistrer_types() -> None:
    """Enregistre le type ; idempotent si l'application est rechargée."""
    try:
        enregistrer_type(
            TypeDocument(
                code=CODE_PLAN_ACTIONS,
                libelle=CONTRAT_PLAN_ACTIONS.libelle,
                etape=ETAPE_PLAN,
                contrat=CONTRAT_PLAN_ACTIONS,
                abreviation="PA",
                modele_numero="{mission}/{code}-{sequence:02d}",
                portee_numero="MISSION",
                fournisseur=FournisseurPlanActions(),  # type: ignore[arg-type]
            )
        )
    except ValueError:
        return

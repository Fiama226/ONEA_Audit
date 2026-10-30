"""Assemblage du rapport : données validées -> dictionnaire figeable (D6).

Fonction pure, 10 requêtes au plus : les listes imbriquées (causes, actions, acceptation,
position de l'audité, réponse de la direction) sont agrégées en JSON par sous-requête.
"""

from collections import Counter, defaultdict
from typing import Any

from django.contrib.postgres.aggregates import JSONBAgg
from django.db.models import Count, F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, Concat, JSONObject, NullIf, Trim

from apps.accomplissement.models import (
    ConclusionTest,
    FicheDeTest,
    NatureTest,
    StatutFiche,
    StatutTest,
    TestPrevu,
)
from apps.analyse.services.objectifs import code_objectif, objectifs_retenus
from apps.constats.models import (
    CauseConstat,
    Constat,
    PrioriteRecommandation,
    Recommandation,
    ReponseAudite,
    StatutConstat,
)
from apps.documents.generators.missions import contexte_mission
from apps.missions.models import Entretien, Mission, StatutEntretien
from apps.recommandations.models import AcceptationRisque, Action, StatutAction
from apps.referentiel.models import NiveauRisque
from apps.signatures.services import normaliser
from apps.users.models import User

from ..gardes import CHAMPS_REDACTION
from ..models import AppreciationGlobale, Rapport, ReponseRapport

_RANG_NIVEAU = {NiveauRisque.ELEVE: 0, NiveauRisque.MOYEN: 1, NiveauRisque.FAIBLE: 2}


def _nom(prefixe: str) -> Any:
    """Nom complet SQL : « prénom nom », sinon l'identifiant."""
    return Coalesce(
        NullIf(
            Trim(Concat(F(f"{prefixe}first_name"), Value(" "), F(f"{prefixe}last_name"))),
            Value(""),
        ),
        F(f"{prefixe}username"),
    )


def _agreger(qs: Any, cle: str, objet: JSONObject, *ordre: str) -> Subquery:
    """Sous-requête : liste JSON des lignes de `qs` regroupées par `cle`."""
    return Subquery(
        qs.order_by().values(cle).annotate(j=JSONBAgg(objet, order_by=ordre)).values("j")
    )


def statut_derive(statuts_actions: list[str], *, acceptee: bool) -> str:
    """Statut dérivé d'une recommandation (D8, §14).

    Même règle que `recommandations.services.statuts.statut_recommandation` (T5), appliquée à
    des données déjà chargées : l'assemblage ne relit pas la base.
    """
    if acceptee:
        return "RISQUE_ACCEPTE"
    if not statuts_actions:
        return "SANS_ACTION"
    terminales = {StatutAction.REALISEE, StatutAction.ABANDONNEE}
    if all(s in terminales for s in statuts_actions) and StatutAction.REALISEE in statuts_actions:
        return str(StatutAction.REALISEE)
    if any(s in (StatutAction.EN_COURS, StatutAction.REALISEE) for s in statuts_actions):
        return str(StatutAction.EN_COURS)
    return str(StatutAction.A_LANCER)


def _etat_engagement(mission: Mission, user: User) -> str:
    """État de l'engagement d'un responsable (T5 : `engagements.etat_engagement`)."""
    # Module livré par la tâche 5 (parallèle) : absent tant qu'elle n'est pas fusionnée.
    from apps.recommandations.services.engagements import (  # type: ignore[import-not-found,unused-ignore]
        etat_engagement,
    )

    return str(etat_engagement(mission, user))


def _causes(brut: list[dict[str, str]] | None) -> dict[str, list[str]]:
    causes: dict[str, list[str]] = {}
    for c in brut or []:
        causes.setdefault(c["categorie"], []).append(c["description"])
    return causes


def _methodologie(mission: Mission) -> dict[str, Any]:
    lignes = (
        TestPrevu.objects.filter(mission=mission, statut=StatutTest.PREVU)
        .values("nature")
        .annotate(
            nb=Count("pk", distinct=True),
            fiches=Count(
                "fiche",
                filter=Q(fiche__statut=StatutFiche.VALIDE, fiche__deleted_at__isnull=True),
                distinct=True,
            ),
        )
        .order_by("nature")
    )
    natures = [
        {
            "nature": ligne["nature"],
            "libelle": str(NatureTest(ligne["nature"]).label),
            "nb": ligne["nb"],
        }
        for ligne in lignes
    ]
    return {
        "natures": natures,
        "nb_tests": sum(ligne["nb"] for ligne in lignes),
        "nb_fiches": sum(ligne["fiches"] for ligne in lignes),
    }


def _recommandations(
    ids_constats: list[Any], *, provisoire: bool
) -> dict[Any, list[dict[str, Any]]]:
    qs = Recommandation.objects.filter(constat_id__in=ids_constats).order_by("ordre", "created_at")
    if not provisoire:
        actions = Action.objects.filter(recommandation=OuterRef("pk"))
        acceptation = (
            AcceptationRisque.objects.filter(recommandation=OuterRef("pk"))
            .order_by("-created_at", "-pk")
            .values(
                j=JSONObject(
                    justification=F("justification"), par=_nom("auteur__"), le=F("created_at")
                )
            )[:1]
        )
        qs = qs.annotate(
            actions_json=_agreger(
                actions,
                "recommandation",
                JSONObject(
                    reference=F("reference"),
                    libelle=F("libelle"),
                    responsable=_nom("responsable__"),
                    responsable_id=F("responsable_id"),
                    echeance=F("echeance"),
                    indicateur=F("indicateur"),
                    moyens=F("moyens"),
                    statut=F("statut"),
                ),
                "numero",
            ),
            acceptation_json=Subquery(acceptation),
        )
    par_constat: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for reco in qs:
        actions_json: list[dict[str, Any]] = [] if provisoire else (reco.actions_json or [])
        acceptation_json = None if provisoire else reco.acceptation_json
        par_constat[reco.constat_id].append(
            {
                "ordre": reco.ordre,
                "libelle": reco.libelle,
                "priorite": reco.priorite,
                "statut_derive": None
                if provisoire
                else statut_derive(
                    [a["statut"] for a in actions_json], acceptee=acceptation_json is not None
                ),
                "acceptation": acceptation_json,
                "actions": [
                    {k: v for k, v in a.items() if k not in ("statut", "responsable_id")}
                    for a in actions_json
                ],
                "_responsables": [(a["responsable_id"], a["responsable"]) for a in actions_json],
            }
        )
    return par_constat


def _constats(rapport: Rapport, *, provisoire: bool) -> list[Constat]:
    qs = (
        Constat.objects.filter(mission_id=rapport.mission_id, statut=StatutConstat.VALIDE)
        .select_related("entite", "processus")
        .annotate(
            causes_json=_agreger(
                CauseConstat.objects.filter(constat=OuterRef("pk")),
                "constat",
                JSONObject(categorie=F("categorie"), description=F("description")),
                "ordre",
                "created_at",
            ),
            position_json=Subquery(
                ReponseAudite.objects.filter(constat=OuterRef("pk"), cycle=OuterRef("cycle"))
                .order_by("-created_at", "-pk")
                .values(
                    j=JSONObject(
                        position=F("position"),
                        commentaire=F("commentaire"),
                        le=F("created_at"),
                    )
                )[:1]
            ),
        )
    )
    if not provisoire:
        qs = qs.annotate(
            reponse_json=Subquery(
                ReponseRapport.objects.filter(
                    constat=OuterRef("pk"), provisoire__rapport_id=rapport.pk
                )
                .order_by("-created_at", "-pk")
                .values(
                    j=JSONObject(
                        commentaire=F("commentaire"),
                        auteur=_nom("auteur__"),
                        le=F("created_at"),
                        hors_delai=F("hors_delai"),
                    )
                )[:1]
            )
        )
    return sorted(
        qs,
        key=lambda c: (_RANG_NIVEAU.get(c.niveau, 3), c.reference),
    )


def _points_forts(mission: Mission) -> list[dict[str, str]]:
    fiches = (
        FicheDeTest.objects.filter(
            mission=mission, statut=StatutFiche.VALIDE, conclusion=ConclusionTest.POINT_FORT
        )
        .order_by("test__numero")
        .values_list("test__code", "test__libelle", "commentaire_conclusion")
    )
    return [{"code": c, "libelle": lb, "commentaire": cm} for c, lb, cm in fiches]


def _entretiens(mission: Mission) -> list[dict[str, Any]]:
    lignes = (
        Entretien.objects.filter(mission=mission, statut=StatutEntretien.REALISE)
        .order_by("date_prevue")
        .values_list(
            "objet", "date_prevue", "realise_le", "lieu", "themes", "autres_interlocuteurs"
        )
    )
    return [
        {
            "objet": objet,
            "date": realise_le or date_prevue,
            "lieu": lieu,
            "themes": themes,
            "interlocuteurs": autres,
        }
        for objet, date_prevue, realise_le, lieu, themes, autres in lignes
    ]


def _corrige_de(rapport: Rapport) -> int | None:
    if rapport.corrige_de_id is None:
        return None
    return (
        Rapport.all_objects.filter(pk=rapport.corrige_de_id)
        .values_list("numero_version", flat=True)
        .first()
    )


def assembler(rapport: Rapport, *, provisoire: bool) -> dict[str, Any]:
    """Assemble le rapport depuis les données validées de la mission (JSON strict).

    Clés de premier niveau :

    - `mission` : bloc du lot 4 (`contexte_mission`) ;
    - `rapport` : `numero_version`, `corrige_de` (numéro du rapport remplacé ou null),
      `motif_correction` ;
    - `sections` : sections saisies (D5) et `appreciation_libelle` ;
    - `objectifs` : `[{code, libelle}]` des objectifs retenus ;
    - `methodologie` : `natures` `[{nature, libelle, nb}]`, `nb_tests`, `nb_fiches` ;
    - `constats` : constats VALIDE par niveau décroissant puis référence ; chacun porte
      `reference`, `titre`, `entite`, `processus`, `niveau`, `score`, `fait_constate`,
      `referentiel`, `causes` `{categorie: [descriptions]}`, `consequence`, `conclusion`,
      `position_audite` `{position, commentaire, le}` ou null, `reponse_direction`
      `{commentaire, auteur, le, hors_delai}` ou null, `recommandations`
      `[{ordre, libelle, priorite, statut_derive, acceptation {justification, par, le} ou null,
      actions [{reference, libelle, responsable, echeance, indicateur, moyens}]}]` ;
    - `points_forts` : `[{code, libelle, commentaire}]` ;
    - `engagements` : `[{responsable, nb_actions, etat}]` ;
    - `entretiens` : entretiens réalisés (annexe) ;
    - `totaux` : `par_niveau`, `par_priorite`, `nb_actions`.

    `provisoire=True` : `reponse_direction`, `engagements`, `acceptation` et `actions` sont vides.
    """
    mission = rapport.mission
    constats = _constats(rapport, provisoire=provisoire)
    recos = _recommandations([c.pk for c in constats], provisoire=provisoire) if constats else {}
    responsables: Counter[tuple[Any, str]] = Counter()
    sortie: list[dict[str, Any]] = []
    par_niveau = {n: 0 for n in NiveauRisque.values}
    par_priorite = {p: 0 for p in PrioriteRecommandation.values}
    nb_actions = 0
    for c in constats:
        annote: Any = c  # annotations SQL (JSON) inconnues de mypy
        liste = recos.get(c.pk, [])
        for r in liste:
            par_priorite[r["priorite"]] += 1
            nb_actions += len(r["actions"])
            for resp in r.pop("_responsables"):
                if resp[0] is not None:
                    responsables[resp] += 1
        if c.niveau:
            par_niveau[c.niveau] += 1
        sortie.append(
            {
                "reference": c.reference,
                "titre": c.titre,
                "entite": c.entite.libelle,
                "processus": c.processus.libelle,
                "niveau": c.niveau,
                "score": c.score,
                "fait_constate": c.fait_constate,
                "referentiel": c.referentiel,
                "causes": _causes(annote.causes_json),
                "consequence": c.consequence,
                "conclusion": c.conclusion,
                "position_audite": annote.position_json,
                "reponse_direction": None if provisoire else annote.reponse_json,
                "recommandations": liste,
            }
        )
    engagements: list[dict[str, Any]] = []
    if responsables:
        utilisateurs = {u.pk: u for u in User.objects.filter(pk__in=[k[0] for k in responsables])}
        for (resp_id, resp_nom), nb in sorted(responsables.items(), key=lambda i: i[0][1]):
            engagements.append(
                {
                    "responsable": resp_nom,
                    "nb_actions": nb,
                    "etat": _etat_engagement(mission, utilisateurs[resp_id]),
                }
            )
    appreciation = rapport.appreciation_globale
    return normaliser(
        {
            "mission": contexte_mission(mission),
            "rapport": {
                "numero_version": rapport.numero_version,
                "corrige_de": _corrige_de(rapport),
                "motif_correction": rapport.motif_correction,
            },
            "sections": {
                **{champ: getattr(rapport, champ) for champ in sorted(CHAMPS_REDACTION)},
                "appreciation_libelle": str(AppreciationGlobale(appreciation).label)
                if appreciation
                else "",
            },
            "objectifs": [
                {"code": code_objectif(o), "libelle": o.libelle} for o in objectifs_retenus(mission)
            ],
            "methodologie": _methodologie(mission),
            "constats": sortie,
            "points_forts": _points_forts(mission),
            "engagements": [] if provisoire else engagements,
            "entretiens": _entretiens(mission),
            "totaux": {
                "par_niveau": par_niveau,
                "par_priorite": par_priorite,
                "nb_actions": 0 if provisoire else nb_actions,
            },
        }
    )

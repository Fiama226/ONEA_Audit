"""Agrégats des tableaux de bord : lectures pures (`aggregate` / `annotate` / `values`).

Aucune boucle de requêtes : chaque fonction émet un nombre fixe de requêtes, indépendant du volume.
La date du jour (`aujourd_hui`) et l'année sont toujours passées en paramètre.
"""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any, cast

from django.db.models import Count, Exists, OuterRef, Q, QuerySet, Subquery

from apps.accomplissement.models import FicheDeTest, StatutFiche, StatutTest, TestPrevu
from apps.constats.models import Constat, ReponseAudite, StatutConstat
from apps.missions.etapes import JALONS, PHASE_DU_STATUT, etape, romain
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import (
    EtapeMission,
    EvenementEtape,
    Mission,
    RisqueMission,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
)
from apps.referentiel.models import CartographieVersion, NiveauRisque, Risque, StatutCartographie
from apps.suivi.models import (
    STATUTS_CLOS,
    STATUTS_RELANCABLES,
    DemandeReport,
    Relance,
    StatutDemandeReport,
    StatutRelance,
    StatutSuivi,
    SuiviAction,
)
from apps.users.models import User

from .perimetres import missions_de_l_annee

NUMERO_ETAPE_TESTS = 12
NUMERO_ETAPE_REPONSES = 15

# Missions « en cours » : ni brouillon, ni planifiée, ni diffusée, ni figée.
STATUTS_MISSION_EN_COURS: frozenset[str] = frozenset(
    {
        StatutMission.EN_PLANIFICATION,
        StatutMission.EN_ACCOMPLISSEMENT,
        StatutMission.EN_COMMUNICATION,
    }
)
# Statuts d'une mission exigée à la date de fin prévue : avant la diffusion du rapport.
STATUTS_MISSION_AVANT_DIFFUSION: frozenset[str] = frozenset(
    {
        StatutMission.BROUILLON,
        StatutMission.PLANIFIEE,
        StatutMission.EN_PLANIFICATION,
        StatutMission.EN_ACCOMPLISSEMENT,
        StatutMission.EN_COMMUNICATION,
    }
)
STATUTS_ETAPE_NON_ATTENDUS: frozenset[str] = STATUTS_ETAPE_CLOSE | {StatutEtape.NON_APPLICABLE}


def EXPR_EN_RETARD(aujourd_hui: date) -> Q:  # noqa: N802
    """Retard d'un suivi (R2) : relançable et échéance dépassée ; le jour J n'est pas un retard.

    Copie de `suivi.services.commun.EXPR_EN_RETARD` (T5), à unifier en T10.
    """
    return Q(statut__in=STATUTS_RELANCABLES, echeance__lt=aujourd_hui)


def _taux(numerateur: int, denominateur: int) -> Decimal | None:
    if denominateur <= 0:
        return None
    return (Decimal(numerateur) / Decimal(denominateur)).quantize(Decimal("0.01"))


# --- Missions et étapes -----------------------------------------------------------------------


def missions_par_statut(qs: QuerySet[Mission]) -> list[dict[str, Any]]:
    lignes = {
        ligne["statut"]: ligne["nombre"]
        for ligne in qs.order_by().values("statut").annotate(nombre=Count("pk"))
    }
    return [
        {
            "statut": valeur,
            "libelle": libelle,
            "phase": PHASE_DU_STATUT[valeur].value if valeur in PHASE_DU_STATUT else None,
            "nombre": lignes[valeur],
        }
        for valeur, libelle in StatutMission.choices
        if valeur in lignes
    ]


def missions_en_retard(qs: QuerySet[Mission], aujourd_hui: date) -> list[dict[str, Any]]:
    lignes = (
        qs.filter(date_fin_prevue__lt=aujourd_hui, statut__in=STATUTS_MISSION_AVANT_DIFFUSION)
        .order_by("date_fin_prevue", "reference")
        .values("pk", "reference", "titre", "statut", "date_fin_prevue")
    )
    return [
        {
            "mission_id": ligne["pk"],
            "reference": ligne["reference"],
            "titre": ligne["titre"],
            "statut": ligne["statut"],
            "date_fin_prevue": ligne["date_fin_prevue"],
            "jours_retard": (aujourd_hui - cast(date, ligne["date_fin_prevue"])).days,
        }
        for ligne in lignes
    ]


def etapes_en_retard(qs: QuerySet[Mission], aujourd_hui: date) -> int:
    return (
        EtapeMission.objects.filter(
            mission__in=qs.filter(statut__in=STATUTS_MISSION_EN_COURS).values("pk"),
            date_fin_prevue__lt=aujourd_hui,
        )
        .exclude(statut__in=STATUTS_ETAPE_NON_ATTENDUS)
        .count()
    )


def jalons_a_valider(qs: QuerySet[Mission]) -> list[dict[str, Any]]:
    terminee_le = (
        EvenementEtape.objects.filter(etape=OuterRef("pk"), type=TypeEvenementEtape.TERMINEE)
        .order_by("-le")
        .values("le")[:1]
    )
    lignes = (
        EtapeMission.objects.filter(
            mission__in=qs.values("pk"), numero__in=JALONS, statut=StatutEtape.TERMINEE
        )
        .annotate(terminee_le=Subquery(terminee_le))
        .order_by("mission__reference", "numero")
        .values("mission_id", "mission__reference", "numero", "terminee_le")
    )
    return [
        {
            "mission_id": ligne["mission_id"],
            "reference": ligne["mission__reference"],
            "numero": ligne["numero"],
            "romain": romain(ligne["numero"]),
            "libelle": etape(ligne["numero"]).titre,
            "terminee_le": ligne["terminee_le"],
        }
        for ligne in lignes
    ]


# --- Suivi des recommandations ----------------------------------------------------------------


def _decompte_suivis(aujourd_hui: date) -> dict[str, Any]:
    """Décomptes communs aux actions par direction et aux taux (R12)."""
    echue = Q(echeance__lt=aujourd_hui)
    abandonnee = Q(statut=StatutSuivi.ABANDONNEE)
    cloturee = Q(statut=StatutSuivi.CLOTUREE)
    return {
        "cloturees": Count("pk", filter=cloturee),
        "abandonnees": Count("pk", filter=abandonnee),
        "total": Count("pk"),
        "echues": Count("pk", filter=echue & ~abandonnee),
        "cloturees_echues": Count("pk", filter=echue & cloturee),
    }


def _taux_de(ligne: Mapping[str, Any]) -> dict[str, Any]:
    cloturees, abandonnees, total = ligne["cloturees"], ligne["abandonnees"], ligne["total"]
    return {
        "cloturees": cloturees,
        "abandonnees": abandonnees,
        "total": total,
        "taux": _taux(cloturees, total - abandonnees),
        "echues": ligne["echues"],
        "cloturees_echues": ligne["cloturees_echues"],
        "taux_echues": _taux(ligne["cloturees_echues"], ligne["echues"]),
    }


def actions_par_direction(suivis: QuerySet[SuiviAction], aujourd_hui: date) -> list[dict[str, Any]]:
    retard = EXPR_EN_RETARD(aujourd_hui)
    lignes = (
        suivis.order_by()
        .values("entite_id", "entite__code", "entite__libelle")
        .annotate(
            cloturees=Count("pk", filter=Q(statut=StatutSuivi.CLOTUREE)),
            ouvertes_dans_les_delais=Count("pk", filter=~Q(statut__in=STATUTS_CLOS) & ~retard),
            en_retard=Count("pk", filter=retard),
            abandonnees=Count("pk", filter=Q(statut=StatutSuivi.ABANDONNEE)),
        )
        .order_by("entite__code")
    )
    return [
        {
            "direction_id": ligne["entite_id"],
            "code": ligne["entite__code"],
            "libelle": ligne["entite__libelle"],
            "cloturees": ligne["cloturees"],
            "ouvertes_dans_les_delais": ligne["ouvertes_dans_les_delais"],
            "en_retard": ligne["en_retard"],
            "abandonnees": ligne["abandonnees"],
        }
        for ligne in lignes
    ]


def file_decisions_rai() -> dict[str, int]:
    suivis = SuiviAction.objects.aggregate(
        a_cloturer=Count("pk", filter=Q(statut=StatutSuivi.VERIFIEE)),
        abandons_proposes=Count("pk", filter=Q(statut=StatutSuivi.ABANDON_PROPOSE)),
    )
    relances = Relance.objects.aggregate(
        relances_en_echec=Count("pk", filter=Q(statut=StatutRelance.ECHEC)),
        relances_sans_adresse=Count("pk", filter=Q(statut=StatutRelance.SANS_ADRESSE)),
    )
    non_clos = SuiviAction.objects.filter(mission=OuterRef("pk")).exclude(statut__in=STATUTS_CLOS)
    missions_a_cloturer = (
        Mission.objects.filter(statut__in=[StatutMission.RAPPORT_DIFFUSE, StatutMission.EN_SUIVI])
        .filter(~Exists(non_clos))
        .count()
    )
    return {
        "a_cloturer": suivis["a_cloturer"],
        "abandons_proposes": suivis["abandons_proposes"],
        "reports_en_attente": DemandeReport.objects.filter(
            statut=StatutDemandeReport.EN_ATTENTE
        ).count(),
        "missions_a_cloturer": missions_a_cloturer,
        "relances_en_echec": relances["relances_en_echec"],
        "relances_sans_adresse": relances["relances_sans_adresse"],
    }


def taux_mise_en_oeuvre(suivis: QuerySet[SuiviAction], aujourd_hui: date) -> dict[str, Any]:
    """R12 : `taux = clôturées / (total - abandonnées)`, `None` si le dénominateur est nul."""
    return _taux_de(suivis.order_by().aggregate(**_decompte_suivis(aujourd_hui)))


def taux_par_direction(suivis: QuerySet[SuiviAction], aujourd_hui: date) -> list[dict[str, Any]]:
    lignes = (
        suivis.order_by()
        .values("entite_id", "entite__code", "entite__libelle")
        .annotate(**_decompte_suivis(aujourd_hui))
        .order_by("entite__code")
    )
    return [
        {
            "direction_id": ligne["entite_id"],
            "code": ligne["entite__code"],
            "libelle": ligne["entite__libelle"],
            **_taux_de(ligne),
        }
        for ligne in lignes
    ]


def actions_a_verifier(suivis: QuerySet[SuiviAction]) -> list[dict[str, Any]]:
    """Actions déclarées réalisées, en attente de vérification (les plus anciennes d'abord)."""
    lignes = (
        suivis.filter(statut=StatutSuivi.REALISEE)
        .order_by("declaree_le", "created_at")
        .values("pk", "mission_id", "mission__reference", "action__libelle", "declaree_le")
    )
    return [
        {
            "suivi_id": ligne["pk"],
            "mission_id": ligne["mission_id"],
            "reference": ligne["mission__reference"],
            "libelle": ligne["action__libelle"],
            "declaree_le": ligne["declaree_le"],
        }
        for ligne in lignes
    ]


def mes_actions(
    suivis: QuerySet[SuiviAction], user: User, aujourd_hui: date
) -> list[dict[str, Any]]:
    """Actions non closes dont `user` est responsable, par échéance."""
    lignes = (
        suivis.filter(responsable=user)
        .exclude(statut__in=STATUTS_CLOS)
        .order_by("echeance", "created_at")
        .values("pk", "mission_id", "mission__reference", "action__libelle", "statut", "echeance")
    )
    resultat = []
    for ligne in lignes:
        en_retard = ligne["statut"] in STATUTS_RELANCABLES and ligne["echeance"] < aujourd_hui
        resultat.append(
            {
                "suivi_id": ligne["pk"],
                "mission_id": ligne["mission_id"],
                "reference": ligne["mission__reference"],
                "libelle": ligne["action__libelle"],
                "statut": ligne["statut"],
                "echeance": ligne["echeance"],
                "en_retard": en_retard,
                "jours_retard": (aujourd_hui - ligne["echeance"]).days if en_retard else None,
            }
        )
    return resultat


def mes_demandes_report(user: User) -> list[dict[str, Any]]:
    lignes = (
        DemandeReport.objects.filter(demandee_par=user)
        .order_by("-created_at")
        .values(
            "pk",
            "suivi_id",
            "mission__reference",
            "echeance_actuelle",
            "nouvelle_echeance",
            "statut",
        )
    )
    return [
        {
            "demande_id": ligne["pk"],
            "suivi_id": ligne["suivi_id"],
            "reference": ligne["mission__reference"],
            "echeance_actuelle": ligne["echeance_actuelle"],
            "nouvelle_echeance": ligne["nouvelle_echeance"],
            "statut": ligne["statut"],
        }
        for ligne in lignes
    ]


# --- Cartographie et couverture des risques ---------------------------------------------------


def _derniere_version_validee(annee: int) -> CartographieVersion | None:
    return (
        CartographieVersion.objects.filter(statut=StatutCartographie.VALIDEE, annee__lte=annee)
        .order_by("-annee", "-validee_le")
        .first()
    )


def cartographie(annee: int) -> dict[str, Any]:
    """Cellules probabilité x impact de la dernière cartographie validée (année <= `annee`)."""
    version = _derniere_version_validee(annee)
    if version is None:
        return {"version_id": None, "annee": None, "cellules": []}
    cellules = (
        Risque.objects.filter(version=version)
        .order_by("probabilite", "impact")
        .values("probabilite", "impact")
        .annotate(nombre=Count("pk"))
    )
    return {"version_id": version.pk, "annee": version.annee, "cellules": list(cellules)}


def risques_eleves(annee: int) -> dict[str, Any]:
    """R13 : risques élevés de la dernière cartographie validée et leur couverture."""
    version = _derniere_version_validee(annee)
    if version is None:
        return {"couverts": 0, "non_couverts": 0, "risques": []}
    risques = list(
        Risque.objects.filter(version=version, niveau=NiveauRisque.ELEVE)
        .order_by("code")
        .values("pk", "code", "libelle", "processus__code")
    )
    missions_annee = missions_de_l_annee(Mission.objects.all(), annee).exclude(
        statut__in=[StatutMission.BROUILLON, StatutMission.ANNULEE]
    )
    couvertures: dict[Any, list[str]] = {}
    for source_id, reference in (
        RisqueMission.objects.filter(
            mission__in=missions_annee.values("pk"),
            risque_source__in=[r["pk"] for r in risques],
        )
        .order_by("mission__reference")
        .values_list("risque_source_id", "mission__reference")
        .distinct()
    ):
        couvertures.setdefault(source_id, []).append(reference)
    lignes = [
        {
            "id": r["pk"],
            "code": r["code"],
            "libelle": r["libelle"],
            "processus_code": r["processus__code"],
            "couvert": r["pk"] in couvertures,
            "missions": couvertures.get(r["pk"], []),
        }
        for r in risques
    ]
    couverts = sum(1 for ligne in lignes if ligne["couvert"])
    return {"couverts": couverts, "non_couverts": len(lignes) - couverts, "risques": lignes}


# --- Auditeur et audité -----------------------------------------------------------------------


def mes_tests_a_documenter(user: User) -> list[dict[str, Any]]:
    """Tests prévus de `user`, sans fiche ou à fiche à reprendre, étape XII ouverte."""
    etape_close = EtapeMission.objects.filter(
        mission=OuterRef("mission"),
        numero=NUMERO_ETAPE_TESTS,
        statut__in=STATUTS_ETAPE_NON_ATTENDUS,
    )
    fiches = FicheDeTest.objects.filter(test=OuterRef("pk"))
    a_reprendre = fiches.filter(statut__in=[StatutFiche.BROUILLON, StatutFiche.RENVOYE])
    lignes = (
        TestPrevu.objects.filter(auditeur=user, statut=StatutTest.PREVU)
        .filter(~Exists(etape_close))
        .annotate(a_une_fiche=Exists(fiches), fiche_a_reprendre=Exists(a_reprendre))
        .filter(Q(a_une_fiche=False) | Q(fiche_a_reprendre=True))
        .order_by("mission__reference", "ordre", "numero")
        .values("pk", "mission_id", "mission__reference", "code", "libelle", "a_une_fiche")
    )
    return [
        {
            "test_id": ligne["pk"],
            "mission_id": ligne["mission_id"],
            "reference": ligne["mission__reference"],
            "code": ligne["code"],
            "libelle": ligne["libelle"],
            "sans_fiche": not ligne["a_une_fiche"],
        }
        for ligne in lignes
    ]


def constats_a_repondre(user: User) -> list[dict[str, Any]]:
    """Constats soumis ou validés de l'entité de l'audité, sans réponse au cycle courant."""
    from apps.missions.acces import missions_visibles

    reponse = ReponseAudite.objects.filter(constat=OuterRef("pk"), cycle=OuterRef("cycle"))
    etape_close = EtapeMission.objects.filter(
        mission=OuterRef("mission"),
        numero=NUMERO_ETAPE_REPONSES,
        statut__in=STATUTS_ETAPE_CLOSE,
    )
    lignes = (
        Constat.objects.filter(
            mission__in=missions_visibles(user).values("pk"),
            entite__code=user.direction_code,
            statut__in=[StatutConstat.SOUMIS, StatutConstat.VALIDE],
        )
        .filter(~Exists(reponse), ~Exists(etape_close))
        .order_by("soumis_le", "reference")
        .values(
            "pk", "mission_id", "mission__reference", "reference", "titre", "cycle", "soumis_le"
        )
    )
    return [
        {
            "constat_id": ligne["pk"],
            "mission_id": ligne["mission_id"],
            "mission_reference": ligne["mission__reference"],
            "reference": ligne["reference"],
            "titre": ligne["titre"],
            "cycle": ligne["cycle"],
            "soumis_le": ligne["soumis_le"],
        }
        for ligne in lignes
    ]


def mes_etapes_en_cours(qs: QuerySet[Mission], aujourd_hui: date) -> list[dict[str, Any]]:
    lignes = (
        EtapeMission.objects.filter(mission__in=qs.values("pk"), statut=StatutEtape.EN_COURS)
        .order_by("mission__reference", "numero")
        .values("mission_id", "mission__reference", "numero", "date_fin_prevue")
    )
    return [
        {
            "mission_id": ligne["mission_id"],
            "reference": ligne["mission__reference"],
            "numero": ligne["numero"],
            "romain": romain(ligne["numero"]),
            "libelle": etape(ligne["numero"]).titre,
            "date_fin_prevue": ligne["date_fin_prevue"],
            "en_retard": ligne["date_fin_prevue"] is not None
            and ligne["date_fin_prevue"] < aujourd_hui,
        }
        for ligne in lignes
    ]


def missions_resume(qs: QuerySet[Mission]) -> list[dict[str, Any]]:
    lignes = qs.order_by("reference", "created_at").values(
        "pk", "reference", "titre", "statut", "date_fin_prevue"
    )
    return [
        {
            "mission_id": ligne["pk"],
            "reference": ligne["reference"],
            "titre": ligne["titre"],
            "statut": ligne["statut"],
            "date_fin_prevue": ligne["date_fin_prevue"],
        }
        for ligne in lignes
    ]


def rapports_diffuses(qs: QuerySet[Mission]) -> list[dict[str, Any]]:
    """Missions au rapport diffusé, avec le décompte de leurs actions."""
    valides = Q(suivis_actions__deleted_at__isnull=True)
    lignes = (
        qs.annotate(
            nombre_actions=Count("suivis_actions", filter=valides),
            actions_cloturees=Count(
                "suivis_actions", filter=valides & Q(suivis_actions__statut=StatutSuivi.CLOTUREE)
            ),
        )
        .order_by("reference", "created_at")
        .values("pk", "reference", "titre", "statut", "nombre_actions", "actions_cloturees")
    )
    return [
        {
            "mission_id": ligne["pk"],
            "reference": ligne["reference"],
            "titre": ligne["titre"],
            "statut": ligne["statut"],
            "nombre_actions": ligne["nombre_actions"],
            "actions_cloturees": ligne["actions_cloturees"],
        }
        for ligne in lignes
    ]

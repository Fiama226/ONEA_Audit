"""Analyse de démonstration : étapes III à VIII des missions dont le niveau visé est >= 3.

Chaque étape est conduite par les services (livrables, contrôles, jalons) jusqu'à celle visée,
qui reste en cours (sauf VI, soumise au RAI). Les étapes IX à XVIII ne sont pas atteintes :
leurs livrables relèvent des lots 6 à 8 (les contrôles correspondants n'existent pas encore).
"""

from collections.abc import Callable

from apps.core.demo import ContexteDemo
from apps.missions.demo import SuiviMission
from apps.missions.models import EtapeMission
from apps.missions.services.etapes import demarrer_etape, terminer_etape, valider_etape
from apps.missions.services.risques import ajouter_risque_mission
from apps.referentiel.models import Risque

from .models import (
    Appreciation,
    CategorieObjectif,
    Composante,
    CouvertureOrdre,
    EvaluationConception,
    MotifNonTest,
    NatureControle,
    QuestionQuestionnaire,
    TypeAvis,
    TypeQuestionnaire,
    TypologieProcessus,
    VarianteOrientation,
)
from .services.descriptions import enregistrer_description
from .services.marc import initialiser_marc, modifier_ligne_marc
from .services.objectifs import initialiser_objectifs, modifier_objectif
from .services.orientation import enregistrer_rapport
from .services.questionnaires import creer_questionnaire, modifier_question
from .services.referentiel import deposer_avis

DERNIERE_ETAPE_ATTEINTE = 8


def _etape(s: SuiviMission, numero: int) -> EtapeMission:
    etape: EtapeMission = EtapeMission.objects.get(mission=s.mission, numero=numero)
    return etape


def _etape_iii(ctx: ContexteDemo, s: SuiviMission) -> None:
    par = s.redacteur
    for p in s.mission.processus.order_by("code"):
        enregistrer_description(
            s.mission,
            processus=p,
            by=par,
            typologie=TypologieProcessus.REALISATION,
            categories_objectifs=[CategorieObjectif.OPERATIONNELS, CategorieObjectif.CONFORMITE],
            description=f"Le processus « {p.libelle} » est décrit par les procédures en vigueur.",
            objectifs="Assurer la qualité de service et la conformité des opérations.",
            indicateurs="Délais de traitement, taux d'anomalies.",
            sources="Entretiens, procédures internes, tableaux de bord.",
        )
    questionnaire = creer_questionnaire(
        s.mission, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=par
    )
    for question in QuestionQuestionnaire.objects.filter(questionnaire=questionnaire):
        modifier_question(
            question,
            by=par,
            reponse="Réponse recueillie lors des entretiens de prise de connaissance.",
            appreciation=ctx.rng.choice(list(Appreciation)),
        )


def _etape_iv(ctx: ContexteDemo, s: SuiviMission) -> None:
    par = s.redacteur
    for p in s.mission.processus.order_by("code"):
        candidats = list(
            Risque.objects.filter(version=s.mission.cartographie, processus=p).order_by("numero")
        )
        for risque in ctx.rng.sample(candidats, k=min(3, len(candidats))):
            ajouter_risque_mission(s.mission, risque_source=risque, by=par)
        if s.rang % 3 == 0:
            ajouter_risque_mission(
                s.mission,
                processus=p,
                libelle=f"Risque propre à la mission : retard de remontée des données ({p.code})",
                probabilite=3,
                impact=4,
                by=par,
            )


def _etape_v(ctx: ContexteDemo, s: SuiviMission) -> None:
    rng, par = ctx.rng, s.redacteur
    lignes = initialiser_marc(s.mission, by=par)
    for i, ligne in enumerate(lignes):
        if i == 0:  # au moins un contrôle clé adéquat : alimente l'étape VII
            evaluation, cle = EvaluationConception.ADEQUATE, True
        else:
            evaluation = rng.choices(list(EvaluationConception), weights=(50, 35, 15), k=1)[0]
            cle = evaluation != EvaluationConception.ABSENTE and rng.random() < 0.4
        modifier_ligne_marc(
            ligne,
            by=par,
            operation="Traitement de l'opération concernée",
            controle_existant=(
                ""
                if evaluation == EvaluationConception.ABSENTE
                else "Double validation et rapprochement périodique."
            ),
            composante=rng.choice(list(Composante)),
            nature=rng.choice(list(NatureControle)),
            evaluation=evaluation,
            cle=cle,
        )


def _etape_vi(ctx: ContexteDemo, s: SuiviMission) -> None:
    for audite in s.audites[:1]:
        deposer_avis(
            s.mission, avis=TypeAvis.ACCORD, commentaire="Référentiel conforme à nos pratiques.",
            by=audite,
        )  # fmt: skip


def _etape_vii(ctx: ContexteDemo, s: SuiviMission) -> None:
    par = s.redacteur
    objectifs = initialiser_objectifs(s.mission, by=par)
    for rang, objectif in enumerate(objectifs):
        if rang > 0 and rang % 3 == 0:
            modifier_objectif(
                objectif,
                by=par,
                retenu=False,
                motif_non_test=MotifNonTest.CONCEPTION_ADAPTEE,
                justification="Conception jugée adaptée : pas de test complémentaire.",
            )
    enregistrer_rapport(
        s.mission,
        by=par,
        variante=VarianteOrientation.COMPLET,
        contexte="Mission inscrite au programme annuel d'audit interne.",
        approche="Tests des contrôles clés et revue documentaire.",
        observations="Aucune observation particulière à ce stade.",
        couverture_ordre=CouvertureOrdre.EXACTE,
    )


TRAVAUX: dict[int, Callable[[ContexteDemo, SuiviMission], None]] = {
    3: _etape_iii,
    4: _etape_iv,
    5: _etape_v,
    6: _etape_vi,
    7: _etape_vii,
}


def _avancer(ctx: ContexteDemo, s: SuiviMission) -> None:
    cible = min(s.etape, DERNIERE_ETAPE_ATTEINTE)
    rai, chef = ctx.rai, s.chef
    if chef is None:
        raise RuntimeError("Mission sans chef.")
    for numero in range(3, cible + 1):
        demarrer_etape(_etape(s, numero), by=rai)
        travail = TRAVAUX.get(numero)
        if travail is None:  # étape VIII : aucun livrable géré avant le lot 6
            break
        travail(ctx, s)
        if numero < cible:
            terminer_etape(_etape(s, numero), by=chef)
            if numero == 6:
                valider_etape(_etape(s, numero), by=rai)
        elif numero == 6:  # jalon soumis, en attente de la validation du RAI
            terminer_etape(_etape(s, numero), by=chef)


def peupler(ctx: ContexteDemo) -> None:
    for s in ctx.etat["suivis"]:
        if s.etape >= 3:
            _avancer(ctx, s)
        if s.etape > DERNIERE_ETAPE_ATTEINTE:  # pragma: no cover - garde de cohérence
            ctx.avertir(f"{s.mission.reference} : étapes au-delà de {DERNIERE_ETAPE_ATTEINTE}.")

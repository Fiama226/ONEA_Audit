from typing import Any

import factory

from apps.accomplissement.models import ConclusionTest, FicheDeTest, StatutFiche
from apps.constats.managers import prochain_numero_constat
from apps.constats.models import (
    CategorieCause,
    CauseConstat,
    Constat,
    PositionAudite,
    PrioriteRecommandation,
    Recommandation,
    ReponseAudite,
)
from apps.signatures.models import TypeDocumentSignable
from apps.users.models import Role
from tests.accomplissement.factories import FicheFactory
from tests.factories import (
    ConfirmationFactory,
    DirectionFactory,
    MissionFactory,
    ProcessusFactory,
    UserFactory,
)


def fiche_anomalie(mission: Any) -> FicheDeTest:
    """Fiche VALIDE de conclusion ANOMALIE : la première de la mission, sinon une nouvelle."""
    existante = FicheDeTest.objects.filter(
        mission=mission, statut=StatutFiche.VALIDE, conclusion=ConclusionTest.ANOMALIE
    ).first()
    if existante is not None:
        return existante
    fiche: FicheDeTest = FicheFactory(
        test__mission=mission,
        test__programme__mission=mission,
        statut=StatutFiche.VALIDE,
        conclusion=ConclusionTest.ANOMALIE,
    )
    return fiche


def _ajouter_contenu(obj: Constat, create: bool, extracted: Any, **kwargs: Any) -> None:
    if not create:
        return
    obj.fiches.add(*(extracted or [fiche_anomalie(obj.mission)]))
    CauseFactory(constat=obj, mission=obj.mission)
    RecommandationFactory(constat=obj, mission=obj.mission)


class ConstatFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Constat
        skip_postgeneration_save = True

    mission = factory.SubFactory(MissionFactory)
    numero = factory.LazyAttribute(lambda o: prochain_numero_constat(o.mission.pk))
    reference = factory.LazyAttribute(lambda o: f"C-{o.numero:02d}")
    titre = factory.Sequence(lambda n: f"Constat {n}")
    entite = factory.SubFactory(DirectionFactory)
    processus = factory.SubFactory(ProcessusFactory)
    fait_constate = "Les rapprochements ne sont pas réalisés."
    referentiel = "Procédure comptable, art. 4."
    consequence = "Risque d'erreur non détectée."
    conclusion = "Le contrôle est insuffisant."
    probabilite = 3
    impact = 5

    fiches = factory.PostGeneration(_ajouter_contenu)


class CauseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CauseConstat

    constat = factory.SubFactory(ConstatFactory)
    mission = factory.SelfAttribute("constat.mission")
    categorie = CategorieCause.METHODES
    description = "Procédure non formalisée."
    ordre = 1


class RecommandationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Recommandation

    constat = factory.SubFactory(ConstatFactory)
    mission = factory.SelfAttribute("constat.mission")
    libelle = "Formaliser et appliquer la procédure de rapprochement."
    priorite = PrioriteRecommandation.HAUTE
    ordre = 1


class ReponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReponseAudite

    constat = factory.SubFactory(ConstatFactory)
    mission = factory.SelfAttribute("constat.mission")
    auteur = factory.SubFactory(UserFactory, role=Role.AUDITE)
    cycle = 1
    position = PositionAudite.ACCORD
    confirmation = factory.SubFactory(
        ConfirmationFactory,
        objet=factory.SelfAttribute("..constat"),
        type_document=TypeDocumentSignable.REPONSE_CONSTAT,
        signataire=factory.SelfAttribute("..auteur"),
    )

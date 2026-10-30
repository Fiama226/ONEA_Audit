import datetime

import factory

from apps.recommandations.managers import prochain_numero_action
from apps.recommandations.models import (
    AcceptationRisque,
    Action,
    EngagementPlanActions,
)
from apps.signatures.models import TypeDocumentSignable
from apps.users.models import Role
from tests.constats.factories import RecommandationFactory
from tests.factories import ConfirmationFactory, MissionFactory, UserFactory


class ActionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Action

    recommandation = factory.SubFactory(RecommandationFactory)
    mission = factory.SelfAttribute("recommandation.mission")
    numero = factory.LazyAttribute(lambda o: prochain_numero_action(o.mission.pk))
    reference = factory.LazyAttribute(lambda o: f"A-{o.numero:02d}")
    libelle = "Formaliser la procédure de rapprochement."
    responsable = factory.SubFactory(UserFactory, role=Role.AUDITE)
    echeance = factory.LazyFunction(lambda: datetime.date.today() + datetime.timedelta(days=90))
    indicateur = "Rapprochements mensuels signés."
    moyens = "Temps agent."
    ordre = 1
    proposee_par = factory.SubFactory(UserFactory, role=Role.AUDITEUR)


class AcceptationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AcceptationRisque

    recommandation = factory.SubFactory(RecommandationFactory)
    mission = factory.SelfAttribute("recommandation.mission")
    justification = "Coût de mise en œuvre supérieur au risque."
    auteur = factory.SubFactory(UserFactory, role=Role.AUDITE)
    confirmation = factory.SubFactory(
        ConfirmationFactory,
        objet=factory.SelfAttribute("..recommandation"),
        type_document=TypeDocumentSignable.ACCEPTATION_RISQUE,
        signataire=factory.SelfAttribute("..auteur"),
    )


class EngagementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EngagementPlanActions

    mission = factory.SubFactory(MissionFactory)
    auteur = factory.SubFactory(UserFactory, role=Role.AUDITE)
    confirmation = factory.SubFactory(
        ConfirmationFactory,
        objet=factory.SelfAttribute("..mission"),
        type_document=TypeDocumentSignable.ENGAGEMENT_PLAN_ACTIONS,
        signataire=factory.SelfAttribute("..auteur"),
    )
    empreinte_actions = "0" * 64

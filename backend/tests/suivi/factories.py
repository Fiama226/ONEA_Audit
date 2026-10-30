import datetime
import hashlib

import factory

from apps.suivi.models import (
    DemandeReport,
    PalierRelance,
    PreuveMiseEnOeuvre,
    Relance,
    SuiviAction,
)
from apps.users.models import Role
from tests.factories import UserFactory
from tests.recommandations.factories import ActionFactory


class SuiviActionFactory(factory.django.DjangoModelFactory):
    """Suivi A_LANCER d'une action (créée au besoin) ; les copies viennent de l'action."""

    class Meta:
        model = SuiviAction

    action = factory.SubFactory(ActionFactory)
    mission = factory.SelfAttribute("action.mission")
    recommandation = factory.SelfAttribute("action.recommandation")
    entite = factory.LazyAttribute(lambda o: o.action.recommandation.constat.entite)
    responsable = factory.SelfAttribute("action.responsable")
    echeance_initiale = factory.SelfAttribute("action.echeance")
    echeance = factory.SelfAttribute("echeance_initiale")
    diffuse_le = factory.LazyFunction(datetime.date.today)


class PreuveFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PreuveMiseEnOeuvre

    suivi = factory.SubFactory(SuiviActionFactory)
    mission = factory.SelfAttribute("suivi.mission")
    numero = factory.Sequence(lambda n: n + 1)
    libelle = "Procédure signée"
    cle_stockage = factory.Sequence(lambda n: f"suivi/preuves/{n:06d}.pdf")
    empreinte_sha256 = factory.LazyAttribute(
        lambda o: hashlib.sha256(o.cle_stockage.encode()).hexdigest()
    )
    taille_octets = 1024
    type_mime = "application/pdf"
    nom_fichier_original = "procedure.pdf"
    deposee_par = factory.SubFactory(UserFactory, role=Role.AUDITE)


class DemandeReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DemandeReport

    suivi = factory.SubFactory(SuiviActionFactory)
    mission = factory.SelfAttribute("suivi.mission")
    echeance_actuelle = factory.SelfAttribute("suivi.echeance")
    nouvelle_echeance = factory.LazyAttribute(
        lambda o: o.echeance_actuelle + datetime.timedelta(days=30)
    )
    motif = "Marché de fournitures retardé."
    demandee_par = factory.SelfAttribute("suivi.responsable")


class RelanceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Relance

    suivi = factory.SubFactory(SuiviActionFactory)
    palier = PalierRelance.J_MOINS_15
    echeance_reference = factory.SelfAttribute("suivi.echeance")
    destinataire = factory.SelfAttribute("suivi.responsable")

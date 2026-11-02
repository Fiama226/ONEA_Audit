import datetime
import string

import factory
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.analyse.models import (
    AvisAudite,
    DescriptionProcessus,
    ForceFaiblesse,
    GrilleSeparation,
    LigneMARC,
    ObjectifAudit,
    Questionnaire,
    QuestionQuestionnaire,
    RapportOrientation,
    TypeAvis,
    TypeForceFaiblesse,
    TypeQuestionnaire,
)
from apps.missions.models import (
    AffectationMission,
    DeclarationIndependance,
    Entretien,
    EtapeMission,
    Mission,
    Reunion,
    RisqueMission,
    RoleMission,
    StatutDeclaration,
    TypeMission,
    TypeReunion,
)
from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    FamilleProcessus,
    NatureObjet,
    ObjetAuditable,
    PrioriteRisque,
    Processus,
    Risque,
    StatutCartographie,
    TypeEntite,
)
from apps.signatures.models import Confirmation, TypeDocumentSignable
from apps.signatures.services import empreinte as empreinte_de
from apps.users.models import Role, User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@onea.test")
    first_name = "Awa"
    last_name = "Ouedraogo"
    role = Role.AUDITEUR
    direction_code = "DAI"
    fonction = "Auditeur interne"

    @factory.post_generation
    def password(self, create: bool, extracted: str | None, **kwargs: object) -> None:
        self.set_password(extracted or "pass-test-12345")
        if create:
            self.save(update_fields=["password"])


def make_user(role: str = Role.AUDITEUR, **kwargs: object) -> User:
    user = UserFactory(role=role, **kwargs)
    assert isinstance(user, User)
    return user


class DirectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Direction

    code = factory.Sequence(lambda n: f"DIR{n}")
    libelle = factory.Sequence(lambda n: f"Direction {n}")
    type = TypeEntite.DIRECTION
    parent = None


def _code_lettres(n: int) -> str:
    """Code processus de 3 lettres majuscules, unique pour un entier donné."""
    a = string.ascii_uppercase
    return a[(n // 676) % 26] + a[(n // 26) % 26] + a[n % 26]


class ProcessusFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Processus

    code = factory.Sequence(_code_lettres)
    libelle = factory.Sequence(lambda n: f"Processus {n}")
    famille = FamilleProcessus.REALISATION
    ordre = factory.Sequence(lambda n: n)


class ObjetAuditableFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ObjetAuditable

    processus = factory.SubFactory(ProcessusFactory)
    parent = None
    nature = NatureObjet.DOMAINE
    libelle = factory.Sequence(lambda n: f"Objet auditable {n}")
    description = ""
    ordre = 0


class CartographieVersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CartographieVersion

    annee = factory.Sequence(lambda n: 2000 + n % 101)
    libelle = factory.LazyAttribute(lambda o: f"Cartographie des risques {o.annee}")


class RisqueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Risque

    version = factory.SubFactory(CartographieVersionFactory)
    processus = factory.SubFactory(ProcessusFactory)
    numero = factory.Sequence(lambda n: n + 1)
    rang = factory.SelfAttribute("numero")
    code = factory.LazyAttribute(lambda o: f"{o.numero}-{o.processus.code}-R{o.rang}")
    libelle = factory.Sequence(lambda n: f"Risque {n}")
    probabilite = 3
    impact = 3
    priorite = PrioriteRisque.AMELIORATION


class ConfirmationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Confirmation

    class Params:
        objet = factory.SubFactory(DirectionFactory)

    type_document = TypeDocumentSignable.ORDRE_MISSION
    content_type = factory.LazyAttribute(lambda o: ContentType.objects.get_for_model(o.objet))
    object_id = factory.LazyAttribute(lambda o: o.objet.pk)
    signataire = factory.SubFactory(UserFactory, role=Role.RAI)
    confirme_le = factory.LazyFunction(timezone.now)
    texte = "Je soussigné(e) confirme."
    donnees = factory.LazyFunction(lambda: {"titre": "Mission"})
    empreinte = factory.LazyAttribute(lambda o: empreinte_de(o.texte, o.donnees))


def reset_sequences() -> None:
    """Reset sequences whose values must stay in range (years) or predictable."""
    CartographieVersionFactory.reset_sequence()
    RisqueFactory.reset_sequence()


class MissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Mission
        skip_postgeneration_save = True

    class Params:
        avec_processus_et_entites = factory.Trait(
            ajouts=factory.PostGeneration(
                lambda obj, create, extracted, **kw: _ajouter_m2m(obj, create)
            )
        )

    titre = factory.Sequence(lambda n: f"Audit du processus {n}")
    type = TypeMission.ASSURANCE
    reference = ""
    cartographie = factory.LazyFunction(lambda: _cartographie_validee())

    ajouts = factory.PostGeneration(lambda obj, create, extracted, **kw: None)


def _ajouter_m2m(mission: Mission, create: bool) -> None:
    if create:
        mission.processus.add(ProcessusFactory())
        mission.entites.add(DirectionFactory())


def _cartographie_validee() -> CartographieVersion:
    existante = CartographieVersion.objects.filter(statut=StatutCartographie.VALIDEE).first()
    if existante is not None:
        return existante
    version = CartographieVersionFactory()
    CartographieVersion._base_manager.filter(pk=version.pk).update(  # noqa: SLF001
        statut=StatutCartographie.VALIDEE,
        validee_le=timezone.now(),
        validee_par=make_user(Role.RAI),
    )
    version.refresh_from_db()
    return version


class AffectationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AffectationMission

    mission = factory.SubFactory(MissionFactory)
    utilisateur = factory.SubFactory(UserFactory)
    role_mission = RoleMission.AUDITEUR
    responsable_entite = False


class DeclarationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeclarationIndependance

    affectation = factory.SubFactory(AffectationFactory)
    statut = StatutDeclaration.EN_ATTENTE


class EtapeMissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EtapeMission

    mission = factory.SubFactory(MissionFactory)
    numero = factory.Sequence(lambda n: n % 18 + 1)


class ReunionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Reunion

    mission = factory.SubFactory(MissionFactory)
    type = TypeReunion.OUVERTURE
    date = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=7))
    lieu = "Salle de réunion DAI"


class EntretienFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Entretien

    mission = factory.SubFactory(MissionFactory)
    objet = factory.Sequence(lambda n: f"Entretien {n}")
    date_prevue = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=3))


class RisqueMissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RisqueMission

    mission = factory.SubFactory(MissionFactory)
    processus = factory.SubFactory(ProcessusFactory)
    libelle = factory.Sequence(lambda n: f"Risque de mission {n}")
    probabilite = 3
    impact = 3


class QuestionnaireFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Questionnaire

    mission = factory.SubFactory(MissionFactory)
    type = TypeQuestionnaire.PRISE_CONNAISSANCE
    titre = "Questionnaire de prise de connaissance"


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuestionQuestionnaire

    questionnaire = factory.SubFactory(QuestionnaireFactory)
    mission = factory.SelfAttribute("questionnaire.mission")
    theme = "Objectifs"
    libelle = factory.Sequence(lambda n: f"Question {n} ?")
    ordre = factory.Sequence(lambda n: n)


class DescriptionProcessusFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DescriptionProcessus

    mission = factory.SubFactory(MissionFactory)
    processus = factory.SubFactory(ProcessusFactory)
    description = "Description du processus."
    objectifs = "Objectifs du processus."


class GrilleSeparationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GrilleSeparation

    mission = factory.SubFactory(MissionFactory)
    processus = factory.SubFactory(ProcessusFactory)
    taches = factory.LazyFunction(lambda: ["Saisir la commande"])
    acteurs = factory.LazyFunction(lambda: ["Agent"])
    cellules = factory.LazyFunction(list)


class LigneMARCFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LigneMARC

    mission = factory.SubFactory(MissionFactory)
    risque = factory.SubFactory(RisqueMissionFactory, mission=factory.SelfAttribute("..mission"))
    operation = factory.Sequence(lambda n: f"Opération {n}")
    objectif_controle = "S'assurer de la régularité des opérations."
    controle_attendu = "Double validation."
    ordre = factory.Sequence(lambda n: n)


class ForceFaiblesseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ForceFaiblesse

    mission = factory.SubFactory(MissionFactory)
    type = TypeForceFaiblesse.FAIBLESSE
    libelle = factory.Sequence(lambda n: f"Faiblesse {n}")
    ordre = factory.Sequence(lambda n: n)


class AvisAuditeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AvisAudite

    mission = factory.SubFactory(MissionFactory)
    auteur = factory.SubFactory(UserFactory, role=Role.AUDITE)
    avis = TypeAvis.ACCORD


class ObjectifAuditFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ObjectifAudit

    mission = factory.SubFactory(MissionFactory)
    ligne_marc = factory.SubFactory(LigneMARCFactory, mission=factory.SelfAttribute("..mission"))
    numero = factory.Sequence(lambda n: n + 1)
    libelle = factory.Sequence(lambda n: f"Objectif {n}")


class RapportOrientationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RapportOrientation

    mission = factory.SubFactory(MissionFactory)

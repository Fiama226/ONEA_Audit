import string

import factory

from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    FamilleProcessus,
    NatureObjet,
    ObjetAuditable,
    PrioriteRisque,
    Processus,
    Risque,
    TypeEntite,
)
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


def reset_sequences() -> None:
    """Reset sequences whose values must stay in range (years) or predictable."""
    CartographieVersionFactory.reset_sequence()
    RisqueFactory.reset_sequence()

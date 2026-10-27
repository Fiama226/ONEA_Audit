import factory

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

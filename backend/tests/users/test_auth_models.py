from datetime import timedelta

import pytest
from auditlog.models import LogEntry
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.users.models import CodeOtp, DelegationGestionComptes, ObjetOtp, User
from config.settings import base


def test_password_hash_is_argon2(settings) -> None:
    # The test settings use a fast MD5 hasher; check the production list from base.
    settings.PASSWORD_HASHERS = base.PASSWORD_HASHERS
    assert make_password("un-mot-de-passe-long-1!").startswith("argon2$argon2id$")


def test_min_length_12_rejected(settings) -> None:
    settings.AUTH_PASSWORD_VALIDATORS = base.AUTH_PASSWORD_VALIDATORS
    with pytest.raises(ValidationError):
        validate_password("Court1!")
    validate_password("Un-mot-de-passe-sûr-42")


@pytest.mark.django_db
def test_new_user_fields_have_safe_defaults(user: User) -> None:
    assert user.doit_changer_mot_de_passe is False
    assert user.mot_de_passe_expire_le is None
    assert user.echecs_connexion == 0
    assert user.verrouille_jusqu_a is None
    assert user.otp_connexion_actif is False


def _otp(user: User, objet: str = ObjetOtp.RESET, **kw) -> CodeOtp:
    return CodeOtp.objects.create(
        user=user,
        objet=objet,
        code_hash="h",
        expire_le=timezone.now() + timedelta(minutes=10),
        **kw,
    )


@pytest.mark.django_db
def test_one_active_otp_per_objet(user: User) -> None:
    _otp(user)
    with pytest.raises(IntegrityError), transaction.atomic():
        _otp(user)
    # Another objet is independent.
    _otp(user, ObjetOtp.LOGIN)


@pytest.mark.django_db
def test_used_otp_does_not_block_a_new_one(user: User) -> None:
    _otp(user, utilise_le=timezone.now())
    _otp(user, utilise_le=timezone.now())
    _otp(user)  # one active alongside several used
    assert CodeOtp.objects.filter(user=user, utilise_le__isnull=True).count() == 1


@pytest.mark.django_db
def test_otp_defaults(user: User) -> None:
    otp = _otp(user)
    assert otp.essais == 0
    assert otp.utilise_le is None
    assert otp.created_at is not None


@pytest.mark.django_db
def test_delegation_is_one_per_user(user: User, admin: User) -> None:
    DelegationGestionComptes.objects.create(user=user, accorde_par=admin)
    with pytest.raises(IntegrityError), transaction.atomic():
        DelegationGestionComptes.objects.create(user=user, accorde_par=admin)


@pytest.mark.django_db
def test_delegation_flags_default_false_and_audited(user: User, admin: User) -> None:
    d = DelegationGestionComptes.objects.create(user=user, accorde_par=admin, creer=True)
    assert (d.creer, d.reinitialiser, d.roles, d.desactiver) == (True, False, False, False)
    assert d.accorde_le is not None
    assert LogEntry.objects.get_for_object(d).count() == 1

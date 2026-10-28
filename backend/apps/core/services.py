"""Helpers de services partagés par les apps métier (gardes, enregistrement, verrous)."""

from collections.abc import Callable
from typing import Any

from django.core.exceptions import NON_FIELD_ERRORS as NON_FIELD
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.http import Http404

from apps.users.models import User

from .audit import actor_scope
from .exceptions import RegleMetierError
from .models import BaseModel


def refuser(message: str, **errors: str) -> RegleMetierError:
    return RegleMetierError(message, {champ: [msg] for champ, msg in errors.items()})


def enregistrer(
    obj: BaseModel,
    *,
    by: User,
    creation: bool = False,
    controle: Callable[[], None] | None = None,
) -> None:
    """Valide (validateurs, contraintes) puis sauvegarde en traçant l'acteur.

    `controle` : garde optionnelle exécutée après la validation et avant l'écriture
    (ex. unicité du code, avec message par champ).
    """
    if creation:
        obj.created_by = by
    obj.updated_by = by
    try:
        # Les contraintes d'unicité sont vérifiées explicitement (messages par champ) ;
        # la base reste l'ultime garde.
        obj.full_clean(validate_constraints=False)
    except ValidationError as e:
        erreurs = dict(e.message_dict)
        if NON_FIELD in erreurs:
            erreurs["non_field_errors"] = erreurs.pop(NON_FIELD)
        raise RegleMetierError("Données invalides.", erreurs) from e
    if controle is not None:
        controle()
    with actor_scope(by), transaction.atomic():
        obj.save()


def relire[T: models.Model](obj: T) -> T:
    """Relit la ligne sous verrou : évite de modifier/ressusciter une instance périmée."""
    model: Any = type(obj)
    try:
        return model.objects.select_for_update().get(pk=obj.pk)  # type: ignore[no-any-return]
    except ObjectDoesNotExist as e:
        raise Http404("Non trouvé.") from e


def verrouiller_actif[T: models.Model](obj: T, champ: str) -> T:
    """Verrouille une cible référencée (parent, processus...) ; refuse si supprimée."""
    model: Any = type(obj)
    fresh = model.objects.select_for_update(no_key=True).filter(pk=obj.pk).first()
    if fresh is None:
        msg = "Cet élément a été supprimé."
        raise refuser(msg, **{champ: msg})
    return fresh  # type: ignore[no-any-return]


def appliquer(
    obj: Any,
    changes: dict[str, Any],
    autorises: set[str],
    *,
    m2m: frozenset[str] | set[str] = frozenset(),
) -> None:
    """Applique les champs modifiables ; les M2M (`m2m`) sont ignorés (posés par le service)."""
    inconnus = set(changes) - autorises
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")
    for champ, valeur in changes.items():
        if champ not in m2m:
            setattr(obj, champ, valeur)

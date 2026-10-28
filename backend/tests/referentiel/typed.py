"""Typed wrappers around the (untyped) factory_boy factories, for mypy."""

from typing import Any, cast

from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    ObjetAuditable,
    Processus,
    Risque,
)
from tests import factories


def version(**kw: Any) -> CartographieVersion:
    return cast(CartographieVersion, factories.CartographieVersionFactory(**kw))


def processus(**kw: Any) -> Processus:
    return cast(Processus, factories.ProcessusFactory(**kw))


def objet(**kw: Any) -> ObjetAuditable:
    return cast(ObjetAuditable, factories.ObjetAuditableFactory(**kw))


def direction(**kw: Any) -> Direction:
    return cast(Direction, factories.DirectionFactory(**kw))


def risque(**kw: Any) -> Risque:
    return cast(Risque, factories.RisqueFactory(**kw))

"""Managers de la communication : gel du rapport et objets en ajout seul.

Les gardes de `save()` ne suffisent pas : `update`, `bulk_update` et
`bulk_create(update_conflicts=True)` les appliquent aussi (défaut récurrent du HANDOFF §5).
Limite connue : SQL brut, `_base_manager` et `hard_delete()` contournent ces gardes.
"""

from collections.abc import Iterable
from typing import Any

from django.db.models import Model

from apps.core.exceptions import RegleMetierError
from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet
from apps.missions.managers import (
    MissionEnfantAllManager,
    MissionEnfantManager,
    MissionEnfantQuerySet,
)

from .exceptions import MSG_UPSERT_INTERDIT, AjoutSeulError


def _attname(modele: type[Model], champ: str) -> str:
    champ_modele: Any = modele._meta.get_field(champ)
    return str(champ_modele.attname)


def _normaliser(champ: str, valeur: Any, modele: type[Model]) -> tuple[str, Any]:
    """(nom de colonne, valeur comparable) d'un argument de `update`."""
    attname = _attname(modele, champ)
    return attname, getattr(valeur, "pk", valeur) if isinstance(valeur, Model) else valeur


# --- Rapport : gel par statut -------------------------------------------------------------


class RapportQuerySet[T: Model](MissionEnfantQuerySet[T]):
    def update(self, **kwargs: Any) -> int:
        from . import gardes

        apres = dict(_normaliser(c, v, self.model) for c, v in kwargs.items())
        for ligne in list(self.order_by().values()):
            gardes.refuser_mission(ligne["mission_id"])
            gardes.controler_modification(ligne, apres)
        return super(MissionEnfantQuerySet, self).update(**kwargs)

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        from . import gardes

        objs = list(objs)
        fields = list(fields)
        tous: Any = self.model.all_objects  # type: ignore[attr-defined]
        lignes = {ligne["id"]: ligne for ligne in tous.filter(pk__in=[o.pk for o in objs]).values()}
        attnames = [_attname(self.model, f) for f in fields]
        for obj in objs:
            ligne = lignes.get(obj.pk)
            if ligne is not None:
                gardes.refuser_mission(ligne["mission_id"])
                gardes.controler_modification(ligne, {a: getattr(obj, a) for a in attnames})
        return super(MissionEnfantQuerySet, self).bulk_update(objs, fields, batch_size)

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise RegleMetierError(MSG_UPSERT_INTERDIT)
        return super().bulk_create(objs, *args, **kwargs)


class RapportManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> RapportQuerySet[T]:
        return RapportQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class RapportAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> RapportQuerySet[T]:
        return RapportQuerySet(self.model, using=self._db)


# --- Destinataires de diffusion : gel après diffusion --------------------------------------


class DestinataireQuerySet[T: Model](MissionEnfantQuerySet[T]):
    def update(self, **kwargs: Any) -> int:
        from . import gardes

        apres = dict(_normaliser(c, v, self.model) for c, v in kwargs.items())
        for ligne in list(self.order_by().values()):
            gardes.refuser_mission(ligne["mission_id"])
            gardes.controler_modification_destinataire(ligne, apres)
        return super(MissionEnfantQuerySet, self).update(**kwargs)

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        from . import gardes

        objs = list(objs)
        fields = list(fields)
        tous: Any = self.model.all_objects  # type: ignore[attr-defined]
        lignes = {ligne["id"]: ligne for ligne in tous.filter(pk__in=[o.pk for o in objs]).values()}
        attnames = [_attname(self.model, f) for f in fields]
        for obj in objs:
            ligne = lignes.get(obj.pk)
            if ligne is not None:
                gardes.refuser_mission(ligne["mission_id"])
                gardes.controler_modification_destinataire(
                    ligne, {a: getattr(obj, a) for a in attnames}
                )
        return super(MissionEnfantQuerySet, self).bulk_update(objs, fields, batch_size)

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise RegleMetierError(MSG_UPSERT_INTERDIT)
        return super().bulk_create(objs, *args, **kwargs)


class DestinataireManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> DestinataireQuerySet[T]:
        return DestinataireQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class DestinataireAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> DestinataireQuerySet[T]:
        return DestinataireQuerySet(self.model, using=self._db)


# --- Objets en ajout seul (provisoire, réponse, diffusion) ---------------------------------


class AjoutSeulQuerySet[T: Model](MissionEnfantQuerySet[T]):
    """`update`, `bulk_update` et l'upsert lèvent l'erreur d'ajout seul du modèle."""

    def _erreur(self) -> AjoutSeulError:
        return AjoutSeulError(self.model.NOM_AJOUT_SEUL)  # type: ignore[attr-defined]

    def update(self, **kwargs: Any) -> int:
        raise self._erreur()

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        raise self._erreur()

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise self._erreur()
        return super().bulk_create(objs, *args, **kwargs)


class AjoutSeulManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> AjoutSeulQuerySet[T]:
        return AjoutSeulQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class AjoutSeulAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> AjoutSeulQuerySet[T]:
        return AjoutSeulQuerySet(self.model, using=self._db)


# --- Journal du rapport : ajout seul -------------------------------------------------------


class JournalQuerySet[T: Model](SoftDeleteQuerySet[T]):
    def update(self, **kwargs: Any) -> int:
        raise AjoutSeulError("Un événement de rapport")

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        raise AjoutSeulError("Un événement de rapport")

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise AjoutSeulError("Un événement de rapport")
        return super().bulk_create(objs, *args, **kwargs)


class JournalManager[T: Model](SoftDeleteManager[T]):
    def get_queryset(self) -> JournalQuerySet[T]:
        return JournalQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class JournalAllManager[T: Model](AllObjectsManager[T]):
    def get_queryset(self) -> JournalQuerySet[T]:
        return JournalQuerySet(self.model, using=self._db)

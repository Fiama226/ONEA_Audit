"""QuerySets qui appliquent aux écritures en masse les gardes de gel des objets de mission.

Même principe que `referentiel/managers.py` : les gardes de `save()` ne suffisent pas, `update`,
`bulk_update` et `bulk_create` (y compris la suppression logique par `update`) les contrôlent
aussi. Les lignes ciblées sont relues en base, puis contrôlées telles qu'elles seront après la
mise à jour (changement de mission, de type de réunion ou d'étape).

Limite connue (idem lot 2) : SQL brut, `_base_manager` et `hard_delete()` contournent ces gardes.
`MissionQuerySet` applique à la mission les mêmes règles que `Mission.save()` (gel, reprise,
annulation depuis SUSPENDUE, champs D17).
"""

import copy
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from django.db.models import Model
from django.db.models.expressions import Combinable

from apps.core.exceptions import RegleMetierError
from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet

if TYPE_CHECKING:
    from .models import Mission


class MissionEnfantQuerySet[T: Model](SoftDeleteQuerySet[T]):
    def update(self, **kwargs: Any) -> int:
        from . import gardes

        lignes = list(self.order_by())
        for ligne in lignes:
            gardes.controler_ecriture(ligne)
            apres = copy.copy(ligne)
            for champ, valeur in kwargs.items():
                if not isinstance(valeur, Combinable):
                    setattr(apres, champ, valeur)
            gardes.controler_ecriture(apres)
        return super().update(**kwargs)

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        from . import gardes

        objs = list(objs)
        tous: Any = self.model.all_objects  # type: ignore[attr-defined]
        for en_base in tous.filter(pk__in=[o.pk for o in objs]):
            gardes.controler_ecriture(en_base)
        for obj in objs:
            gardes.controler_ecriture(obj)
        return super().bulk_update(objs, list(fields), batch_size)

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        from . import gardes

        objs = list(objs)
        for obj in objs:
            gardes.controler_ecriture(obj)
        return super().bulk_create(objs, *args, **kwargs)


class MissionEnfantManager[T: Model](SoftDeleteManager[T]):
    def get_queryset(self) -> MissionEnfantQuerySet[T]:
        return MissionEnfantQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class MissionEnfantAllManager[T: Model](AllObjectsManager[T]):
    def get_queryset(self) -> MissionEnfantQuerySet[T]:
        return MissionEnfantQuerySet(self.model, using=self._db)


_MSG_AJOUT_SEUL = "Un événement d'étape ne peut pas être modifié : le journal est en ajout seul."


class EvenementQuerySet[T: Model](SoftDeleteQuerySet[T]):
    def update(self, **kwargs: Any) -> int:
        raise RegleMetierError(_MSG_AJOUT_SEUL)

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        raise RegleMetierError(_MSG_AJOUT_SEUL)


class EvenementManager[T: Model](SoftDeleteManager[T]):
    def get_queryset(self) -> EvenementQuerySet[T]:
        return EvenementQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class EvenementAllManager[T: Model](AllObjectsManager[T]):
    def get_queryset(self) -> EvenementQuerySet[T]:
        return EvenementQuerySet(self.model, using=self._db)


class MissionQuerySet(SoftDeleteQuerySet["Mission"]):
    """Mêmes règles que `Mission.save()` pour `update` et `bulk_update`."""

    def update(self, **kwargs: Any) -> int:
        from . import gardes

        lignes = list(self.order_by().values(*gardes._CHAMPS_LUS))  # noqa: SLF001
        gardes.controler_lignes_mission(lignes, lambda _l, champ: kwargs.get(champ), set(kwargs))
        return super().update(**kwargs)

    def bulk_update(
        self, objs: Iterable["Mission"], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        from . import gardes
        from .models import Mission

        objs = list(objs)
        fields = list(fields)
        par_pk = {o.pk: o for o in objs}
        lignes = list(
            Mission.all_objects.filter(pk__in=par_pk).values(*gardes._CHAMPS_LUS)  # noqa: SLF001
        )
        gardes.controler_lignes_mission(
            lignes, lambda ligne, champ: getattr(par_pk[ligne["pk"]], champ), set(fields)
        )
        return super().bulk_update(objs, fields, batch_size)


class MissionManager(SoftDeleteManager["Mission"]):
    def get_queryset(self) -> MissionQuerySet:
        return MissionQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class MissionAllManager(AllObjectsManager["Mission"]):
    def get_queryset(self) -> MissionQuerySet:
        return MissionQuerySet(self.model, using=self._db)

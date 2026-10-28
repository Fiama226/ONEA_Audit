"""Managers et QuerySets qui font respecter le gel d'une cartographie validée.

Le gel est garanti à trois niveaux : les services, `save()` des modèles et ces QuerySets
(`update`, `bulk_update`, `bulk_create`, y compris la suppression logique par `update`).

Un risque ne change jamais de cartographie (`version`) et le statut d'une cartographie ne
change que par `valider_version` : `update` / `bulk_update` refusent ces champs.

Limite connue : ces protections s'appliquent aux managers `objects` et `all_objects`. Elles
sont contournées par du SQL brut (`cursor.execute`, `RawSQL`), par les mises à jour passant
par `_base_manager`, par `hard_delete()` (maintenance) et par un accès direct à la base ;
aucun déclencheur en base n'est posé (décision de conception).

Les services lèvent `Http404` (et non une exception métier) quand une ligne a disparu entre
le chargement et l'écriture : un appelant hors HTTP (commande d'import...) doit l'intercepter.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from apps.core.exceptions import RegleMetierError
from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet

from .exceptions import CartographieFigeeError

if TYPE_CHECKING:
    from .models import CartographieVersion, Risque


def _versions_validees() -> Any:
    from .models import CartographieVersion, StatutCartographie

    return CartographieVersion.all_objects.filter(statut=StatutCartographie.VALIDEE)


def _refuser_si_gele(annee: int | None) -> None:
    if annee is not None:
        raise CartographieFigeeError(annee)


def _refuser_champs(champs: Iterable[str], interdits: set[str], message: str, cle: str) -> None:
    if interdits & set(champs):
        raise RegleMetierError(message, {cle: [message]})


_MSG_VERSION = "Un risque ne peut pas changer de cartographie."
_MSG_STATUT = "Le statut d'une cartographie ne change que par sa validation."


class RisqueQuerySet(SoftDeleteQuerySet["Risque"]):
    def update(self, **kwargs: Any) -> int:
        _refuser_champs(kwargs, {"version", "version_id"}, _MSG_VERSION, "version")
        _refuser_si_gele(
            _versions_validees()
            .filter(pk__in=self.order_by().values("version_id"))
            .values_list("annee", flat=True)
            .first()
        )
        return super().update(**kwargs)

    def bulk_update(
        self, objs: Iterable["Risque"], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        objs = list(objs)
        fields = list(fields)
        _refuser_champs(fields, {"version", "version_id"}, _MSG_VERSION, "version")
        from django.db.models import Q

        _refuser_si_gele(
            _versions_validees()
            .filter(
                Q(pk__in={o.version_id for o in objs}) | Q(risques__pk__in=[o.pk for o in objs])
            )
            .values_list("annee", flat=True)
            .first()
        )
        return super().bulk_update(objs, fields, batch_size)

    def bulk_create(self, objs: Iterable["Risque"], *a: Any, **kw: Any) -> list["Risque"]:
        objs = list(objs)
        _refuser_si_gele(
            _versions_validees()
            .filter(pk__in={o.version_id for o in objs})
            .values_list("annee", flat=True)
            .first()
        )
        return super().bulk_create(objs, *a, **kw)


class CartographieQuerySet(SoftDeleteQuerySet["CartographieVersion"]):
    def update(self, **kwargs: Any) -> int:
        from .models import StatutCartographie

        _refuser_champs(kwargs, {"statut"}, _MSG_STATUT, "statut")
        _refuser_si_gele(
            self.order_by()
            .filter(statut=StatutCartographie.VALIDEE)
            .values_list("annee", flat=True)
            .first()
        )
        return super().update(**kwargs)

    def bulk_update(
        self,
        objs: Iterable["CartographieVersion"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        objs = list(objs)
        fields = list(fields)
        _refuser_champs(fields, {"statut"}, _MSG_STATUT, "statut")
        _refuser_si_gele(
            _versions_validees()
            .filter(pk__in=[o.pk for o in objs])
            .values_list("annee", flat=True)
            .first()
        )
        return super().bulk_update(objs, fields, batch_size)


class RisqueManager(SoftDeleteManager["Risque"]):
    def get_queryset(self) -> RisqueQuerySet:
        return RisqueQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class RisqueAllManager(AllObjectsManager["Risque"]):
    def get_queryset(self) -> RisqueQuerySet:
        return RisqueQuerySet(self.model, using=self._db)


class CartographieManager(SoftDeleteManager["CartographieVersion"]):
    def get_queryset(self) -> CartographieQuerySet:
        return CartographieQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class CartographieAllManager(AllObjectsManager["CartographieVersion"]):
    def get_queryset(self) -> CartographieQuerySet:
        return CartographieQuerySet(self.model, using=self._db)

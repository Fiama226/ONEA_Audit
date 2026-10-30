"""Managers du suivi : champs figés, ajout seul.

Les gardes de `save()` ne suffisent pas : `update`, `bulk_update` et
`bulk_create(update_conflicts=True)` les contourneraient (défaut récurrent, HANDOFF §5).
Limite connue : SQL brut, `_base_manager` et `hard_delete()` contournent ces gardes.

Un modèle gardé expose `champs_figes() -> set[str]` (noms de colonnes) et
`erreur_champs_figes(champs) -> Exception`.
"""

from collections.abc import Iterable
from typing import Any

from django.db.models import Model
from django.db.models.expressions import Combinable

from apps.core.exceptions import RegleMetierError
from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet
from apps.missions.managers import (
    MissionEnfantAllManager,
    MissionEnfantManager,
    MissionEnfantQuerySet,
)

from .exceptions import MSG_UPSERT_INTERDIT, AjoutSeulSuiviError


def attname_de(modele: type[Model], champ: str) -> str:
    champ_modele: Any = modele._meta.get_field(champ)
    return str(champ_modele.attname)


def _valeur(valeur: Any) -> Any:
    return valeur.pk if isinstance(valeur, Model) else valeur


def champs_modifies(
    modele: Any, en_base: dict[str, Any], apres: dict[str, Any], *, restreint: set[str] | None
) -> list[str]:
    """Champs figés de `modele` dont la valeur `apres` diffère de la ligne `en_base`."""
    figes = modele.champs_figes()
    if restreint is not None:
        figes = figes & restreint
    return [
        c
        for c in figes
        if c in apres and (isinstance(apres[c], Combinable) or _valeur(apres[c]) != en_base.get(c))
    ]


class _GardeChampsFiges:
    """Mélange coopératif : à placer avant le QuerySet de base dans les bases."""

    def update(self, **kwargs: Any) -> int:
        qs: Any = self
        modele = qs.model
        apres = {attname_de(modele, c): _valeur(v) for c, v in kwargs.items()}
        colonnes = [c for c in modele.champs_figes() if c in apres]
        if colonnes:
            for ligne in list(qs.order_by().values("pk", *colonnes)):
                refus = champs_modifies(modele, ligne, apres, restreint=None)
                if refus:
                    raise modele.erreur_champs_figes(refus)
        return super().update(**kwargs)  # type: ignore[misc, no-any-return]

    def bulk_update(
        self, objs: Iterable[Any], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        objs = list(objs)
        fields = list(fields)
        modele = self.model  # type: ignore[attr-defined]
        colonnes = {attname_de(modele, f) for f in fields}
        tous: Any = modele.all_objects
        lignes = {ligne["id"]: ligne for ligne in tous.filter(pk__in=[o.pk for o in objs]).values()}
        for obj in objs:
            ligne = lignes.get(obj.pk)
            if ligne is None:
                continue
            apres = {c: _valeur(getattr(obj, c)) for c in colonnes}
            refus = champs_modifies(modele, ligne, apres, restreint=None)
            if refus:
                raise modele.erreur_champs_figes(refus)
        return super().bulk_update(objs, fields, batch_size)  # type: ignore[misc, no-any-return]

    def bulk_create(self, objs: Iterable[Any], *args: Any, **kwargs: Any) -> list[Any]:
        if kwargs.get("update_conflicts"):
            raise RegleMetierError(MSG_UPSERT_INTERDIT)
        return super().bulk_create(objs, *args, **kwargs)  # type: ignore[misc, no-any-return]


class ChampsFigesQuerySet[T: Model](_GardeChampsFiges, MissionEnfantQuerySet[T]):
    pass


class ChampsFigesManager[T: Model](MissionEnfantManager[T]):
    def get_queryset(self) -> ChampsFigesQuerySet[T]:
        return ChampsFigesQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class ChampsFigesAllManager[T: Model](MissionEnfantAllManager[T]):
    def get_queryset(self) -> ChampsFigesQuerySet[T]:
        return ChampsFigesQuerySet(self.model, using=self._db)


# --- Relance : objet hors mission, mêmes gardes sur les champs figés ---------------------


class RelanceQuerySet[T: Model](_GardeChampsFiges, SoftDeleteQuerySet[T]):
    pass


class RelanceManager[T: Model](SoftDeleteManager[T]):
    def get_queryset(self) -> RelanceQuerySet[T]:
        return RelanceQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class RelanceAllManager[T: Model](AllObjectsManager[T]):
    def get_queryset(self) -> RelanceQuerySet[T]:
        return RelanceQuerySet(self.model, using=self._db)


# --- Journal : ajout seul ----------------------------------------------------------------


class JournalQuerySet[T: Model](SoftDeleteQuerySet[T]):
    def update(self, **kwargs: Any) -> int:
        raise AjoutSeulSuiviError

    def bulk_update(
        self, objs: Iterable[T], fields: Iterable[str], batch_size: int | None = None
    ) -> int:
        raise AjoutSeulSuiviError

    def bulk_create(self, objs: Iterable[T], *args: Any, **kwargs: Any) -> list[T]:
        if kwargs.get("update_conflicts"):
            raise AjoutSeulSuiviError
        return super().bulk_create(objs, *args, **kwargs)


class JournalManager[T: Model](SoftDeleteManager[T]):
    def get_queryset(self) -> JournalQuerySet[T]:
        return JournalQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class JournalAllManager[T: Model](AllObjectsManager[T]):
    def get_queryset(self) -> JournalQuerySet[T]:
        return JournalQuerySet(self.model, using=self._db)


def controler_champs_figes(obj: Model, update_fields: Iterable[str] | None) -> None:
    """Garde de `save()` : refuse la modification d'un champ figé d'un objet déjà créé."""
    modele: Any = type(obj)
    figes: set[str] = set(modele.champs_figes())
    if update_fields is not None:
        figes &= {attname_de(modele, f) for f in update_fields}
    if not figes or obj._state.adding:
        return
    en_base = modele.all_objects.filter(pk=obj.pk).values(*figes).first()
    if en_base is None:
        return
    refus = [c for c in figes if _valeur(getattr(obj, c)) != en_base[c]]
    if refus:
        raise modele.erreur_champs_figes(refus)

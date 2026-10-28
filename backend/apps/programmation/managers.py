"""Managers et QuerySets qui font respecter le gel d'un programme annuel validé.

Le gel est garanti à trois niveaux : les services, `save()` des modèles et ces QuerySets
(`update`, `bulk_update`, `bulk_create`, y compris la suppression logique par `update`).

Une ligne ne change jamais de programme (`programme`) et le statut d'un programme ne change
que par sa validation : `update` / `bulk_update` refusent ces champs.

Limite connue : ces protections s'appliquent aux managers `objects` et `all_objects`. Elles
sont contournées par du SQL brut (`cursor.execute`, `RawSQL`), par les mises à jour passant
par `_base_manager`, par `hard_delete()` (maintenance) et par un accès direct à la base ;
aucun déclencheur en base n'est posé (décision de conception).

Les entités d'une ligne (`entites`, many-to-many) sont gardées par un récepteur `m2m_changed`
(`pre_add`, `pre_remove`, `pre_clear`, y compris côté inverse) ; il est contourné par des
écritures directes sur la table de liaison (`through.objects.bulk_create`, SQL brut).
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from django.db.models import Q

from apps.core.exceptions import RegleMetierError
from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet

from .exceptions import ProgrammeFigeError

if TYPE_CHECKING:
    from .models import LigneProgramme, ProgrammeAnnuel

_MSG_PROGRAMME = "Une ligne ne peut pas changer de programme."
_MSG_STATUT = "Le statut d'un programme ne change que par sa validation."
_META = {"updated_by", "updated_by_id", "updated_at"}


def _programmes_valides() -> Any:
    from .models import ProgrammeAnnuel, StatutProgramme

    return ProgrammeAnnuel.all_objects.filter(statut=StatutProgramme.VALIDE)


def _refuser_si_fige(annee: int | None) -> None:
    if annee is not None:
        raise ProgrammeFigeError(annee)


def _refuser_champs(champs: Iterable[str], interdits: set[str], message: str, cle: str) -> None:
    if interdits & set(champs):
        raise RegleMetierError(message, {cle: [message]})


def champs_execution_seuls(champs: Iterable[str]) -> bool:
    """Vrai si `champs` ne touche que des champs d'exécution (et la traçabilité)."""
    from .models import CHAMPS_EXECUTION

    champs = set(champs)
    return bool(champs & CHAMPS_EXECUTION) and champs <= (CHAMPS_EXECUTION | _META)


class ProgrammeQuerySet(SoftDeleteQuerySet["ProgrammeAnnuel"]):
    def update(self, **kwargs: Any) -> int:
        from .models import StatutProgramme

        _refuser_champs(kwargs, {"statut"}, _MSG_STATUT, "statut")
        _refuser_si_fige(
            self.order_by()
            .filter(statut=StatutProgramme.VALIDE)
            .values_list("annee", flat=True)
            .first()
        )
        return super().update(**kwargs)

    def bulk_update(
        self,
        objs: Iterable["ProgrammeAnnuel"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        objs = list(objs)
        fields = list(fields)
        _refuser_champs(fields, {"statut"}, _MSG_STATUT, "statut")
        _refuser_si_fige(
            _programmes_valides()
            .filter(pk__in=[o.pk for o in objs])
            .values_list("annee", flat=True)
            .first()
        )
        return super().bulk_update(objs, fields, batch_size)


class LigneProgrammeQuerySet(SoftDeleteQuerySet["LigneProgramme"]):
    def update(self, **kwargs: Any) -> int:
        _refuser_champs(kwargs, {"programme", "programme_id"}, _MSG_PROGRAMME, "programme")
        if not champs_execution_seuls(kwargs):
            _refuser_si_fige(
                _programmes_valides()
                .filter(pk__in=self.order_by().values("programme_id"))
                .values_list("annee", flat=True)
                .first()
            )
        return super().update(**kwargs)

    def bulk_update(
        self,
        objs: Iterable["LigneProgramme"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        objs = list(objs)
        fields = list(fields)
        _refuser_champs(fields, {"programme", "programme_id"}, _MSG_PROGRAMME, "programme")
        if not champs_execution_seuls(fields):
            _refuser_si_fige(
                _programmes_valides()
                .filter(
                    Q(pk__in={o.programme_id for o in objs})
                    | Q(lignes__pk__in=[o.pk for o in objs])
                )
                .values_list("annee", flat=True)
                .first()
            )
        return super().bulk_update(objs, fields, batch_size)

    def bulk_create(
        self, objs: Iterable["LigneProgramme"], *a: Any, **kw: Any
    ) -> list["LigneProgramme"]:
        objs = list(objs)
        _refuser_si_fige(
            _programmes_valides()
            .filter(pk__in={o.programme_id for o in objs})
            .values_list("annee", flat=True)
            .first()
        )
        return super().bulk_create(objs, *a, **kw)


class ProgrammeManager(SoftDeleteManager["ProgrammeAnnuel"]):
    def get_queryset(self) -> ProgrammeQuerySet:
        return ProgrammeQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class ProgrammeAllManager(AllObjectsManager["ProgrammeAnnuel"]):
    def get_queryset(self) -> ProgrammeQuerySet:
        return ProgrammeQuerySet(self.model, using=self._db)


class LigneProgrammeManager(SoftDeleteManager["LigneProgramme"]):
    def get_queryset(self) -> LigneProgrammeQuerySet:
        return LigneProgrammeQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class LigneProgrammeAllManager(AllObjectsManager["LigneProgramme"]):
    def get_queryset(self) -> LigneProgrammeQuerySet:
        return LigneProgrammeQuerySet(self.model, using=self._db)

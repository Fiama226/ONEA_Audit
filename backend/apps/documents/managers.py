"""QuerySets that apply the immutability guards of documents to bulk writes.

Same principle as `signatures/managers.py`: `save()` guards are not enough, `update` and
`bulk_update` are controlled too. Known limit: raw SQL and `hard_delete()` bypass them.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from apps.core.managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet

from .exceptions import (
    ConsultationImmuableError,
    DocumentFigeError,
    GabaritFigeError,
    VersionFigeeError,
)

# Fields of a finished version that may still change (PDF conversion and bookkeeping).
CHAMPS_VERSION_MODIFIABLES = frozenset(
    {
        "statut_pdf",
        "fichier_pdf",
        "empreinte_pdf",
        "taille_pdf",
        "pdf_le",
        "erreur_pdf",
        "debut_traitement",
        "updated_at",
        "updated_by",
    }
)
CHAMPS_VERSION_UNE_FOIS = frozenset({"fichier_pdf", "empreinte_pdf"})
CHAMPS_VERSION_LUS = (
    "statut",
    "contexte",
    "empreinte_contexte",
    "empreinte_docx",
    "taille_docx",
    "fichier_docx",
    "genere_le",
    "fichier_pdf",
    "empreinte_pdf",
    "deleted_at",
)
CHAMPS_DOCUMENT_FIGES = frozenset(
    {"type_document", "mission", "content_type", "object_id", "numero", "annee", "sequence"}
)
CHAMPS_GABARIT_FIGES = frozenset(
    {"fichier", "taille", "empreinte", "version", "type_document", "nom_original"}
)


def _nom(champ: str) -> str:
    return champ[:-3] if champ.endswith("_id") else champ


def controler_version(en_base: Mapping[str, Any], changements: Mapping[str, Any]) -> None:
    """Raise if `changements` alter a finished version (`en_base` = stored values)."""
    if en_base["statut"] != "PRETE":
        return
    for champ, valeur in changements.items():
        if champ not in CHAMPS_VERSION_MODIFIABLES:
            if champ in en_base and en_base[champ] == valeur:
                continue
            raise VersionFigeeError
        if champ in CHAMPS_VERSION_UNE_FOIS and en_base.get(champ) not in ("", None, valeur):
            raise VersionFigeeError


class DocumentQuerySet(SoftDeleteQuerySet[Any]):
    def update(self, **kwargs: Any) -> int:
        if CHAMPS_DOCUMENT_FIGES & {_nom(k) for k in kwargs}:
            raise DocumentFigeError
        return super().update(**kwargs)

    def bulk_update(self, objs: Iterable[Any], fields: Iterable[str], *a: Any, **kw: Any) -> int:
        noms = list(fields)
        if CHAMPS_DOCUMENT_FIGES & {_nom(f) for f in noms}:
            raise DocumentFigeError
        return super().bulk_update(objs, noms, *a, **kw)

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if kwargs.get("update_conflicts"):
            raise DocumentFigeError
        return super().bulk_create(objs, *args, **kwargs)


class DocumentManager(SoftDeleteManager[Any]):
    def get_queryset(self) -> DocumentQuerySet:
        return DocumentQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class DocumentAllManager(AllObjectsManager[Any]):
    def get_queryset(self) -> DocumentQuerySet:
        return DocumentQuerySet(self.model, using=self._db)


class VersionQuerySet(SoftDeleteQuerySet[Any]):
    def update(self, **kwargs: Any) -> int:
        changements = {_nom(k): v for k, v in kwargs.items()}
        for ligne in self.order_by().values("pk", *CHAMPS_VERSION_LUS):
            controler_version(ligne, changements)
        return super().update(**kwargs)

    def bulk_update(self, objs: Iterable[Any], fields: Iterable[str], *a: Any, **kw: Any) -> int:
        objs = list(objs)
        noms = list(fields)
        en_base = {
            ligne["pk"]: ligne
            for ligne in self.model.all_objects.filter(pk__in=[o.pk for o in objs])
            .order_by()
            .values("pk", *CHAMPS_VERSION_LUS)
        }
        for obj in objs:
            ligne = en_base.get(obj.pk)
            if ligne is None:
                continue
            changements = {}
            for f in noms:
                valeur = getattr(obj, f)
                changements[_nom(f)] = valeur.name if hasattr(valeur, "name") else valeur
            controler_version(ligne, changements)
        return super().bulk_update(objs, noms, *a, **kw)

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if kwargs.get("update_conflicts"):
            raise VersionFigeeError
        return super().bulk_create(objs, *args, **kwargs)


class VersionManager(SoftDeleteManager[Any]):
    def get_queryset(self) -> VersionQuerySet:
        return VersionQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class VersionAllManager(AllObjectsManager[Any]):
    def get_queryset(self) -> VersionQuerySet:
        return VersionQuerySet(self.model, using=self._db)


class GabaritQuerySet(SoftDeleteQuerySet[Any]):
    def update(self, **kwargs: Any) -> int:
        if CHAMPS_GABARIT_FIGES & {_nom(k) for k in kwargs}:
            raise GabaritFigeError
        return super().update(**kwargs)

    def bulk_update(self, objs: Iterable[Any], fields: Iterable[str], *a: Any, **kw: Any) -> int:
        noms = list(fields)
        if CHAMPS_GABARIT_FIGES & {_nom(f) for f in noms}:
            raise GabaritFigeError
        return super().bulk_update(objs, noms, *a, **kw)

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if kwargs.get("update_conflicts"):
            raise GabaritFigeError
        return super().bulk_create(objs, *args, **kwargs)


class GabaritManager(SoftDeleteManager[Any]):
    def get_queryset(self) -> GabaritQuerySet:
        return GabaritQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class GabaritAllManager(AllObjectsManager[Any]):
    def get_queryset(self) -> GabaritQuerySet:
        return GabaritQuerySet(self.model, using=self._db)


class ConsultationQuerySet(SoftDeleteQuerySet[Any]):
    def update(self, **kwargs: Any) -> int:
        raise ConsultationImmuableError

    def bulk_update(self, objs: Any, fields: Any, batch_size: int | None = None) -> int:
        raise ConsultationImmuableError

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if kwargs.get("update_conflicts"):
            raise ConsultationImmuableError
        return super().bulk_create(objs, *args, **kwargs)


class ConsultationManager(SoftDeleteManager[Any]):
    def get_queryset(self) -> ConsultationQuerySet:
        return ConsultationQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class ConsultationAllManager(AllObjectsManager[Any]):
    def get_queryset(self) -> ConsultationQuerySet:
        return ConsultationQuerySet(self.model, using=self._db)

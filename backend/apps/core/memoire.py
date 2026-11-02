"""Mémo à portée d'un bloc de lecture seule (évite de refaire les mêmes requêtes de droits).

Hors bloc `memo_lecture()`, `memoise` recalcule toujours : aucun état partagé entre requêtes ni
entre threads (variable de contexte), et jamais de lecture périmée après une écriture, puisque
le bloc ne doit envelopper aucune écriture.
"""

from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_MEMO: ContextVar[dict[Hashable, Any] | None] = ContextVar("memo_lecture", default=None)


@contextmanager
def memo_lecture() -> Iterator[None]:
    jeton = _MEMO.set({})
    try:
        yield
    finally:
        _MEMO.reset(jeton)


def memoise[T](cle: Hashable, calcul: Callable[[], T]) -> T:
    memo = _MEMO.get()
    if memo is None:
        return calcul()
    if cle not in memo:
        memo[cle] = calcul()
    return memo[cle]  # type: ignore[no-any-return]

from collections.abc import Iterator

import pytest

from apps.signatures.electronique import enregistrer_signataire_electronique

from .fakes import SignataireFactice


@pytest.fixture
def signataire_factice() -> Iterator[SignataireFactice]:
    s = SignataireFactice()
    enregistrer_signataire_electronique(s)
    yield s
    enregistrer_signataire_electronique(None)

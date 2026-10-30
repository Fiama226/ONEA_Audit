from datetime import UTC, datetime

from apps.signatures.electronique import (
    ResultatVerification,
    enregistrer_signataire_electronique,
    signataire_electronique,
)

from .fakes import SignataireFactice


class _Version:
    pk = 1


def test_aucun_signataire_par_defaut() -> None:
    assert signataire_electronique() is None


def test_enregistrement_et_retrait() -> None:
    s = SignataireFactice()
    enregistrer_signataire_electronique(s)
    assert signataire_electronique() is s
    enregistrer_signataire_electronique(None)
    assert signataire_electronique() is None


def test_signataire_factice(signataire_factice: SignataireFactice) -> None:
    v = _Version()
    s = signataire_electronique()
    assert s is not None
    assert not s.est_signee(v)  # type: ignore[arg-type]
    assert not s.verifier(v).valide  # type: ignore[arg-type]
    signataire_factice.signer(v)
    assert s.est_signee(v)  # type: ignore[arg-type]
    assert s.verifier(v).valide  # type: ignore[arg-type]


def test_resultat_immuable() -> None:
    r = ResultatVerification(True, "CN=x", datetime(2026, 1, 1, tzinfo=UTC), "")
    try:
        r.valide = False  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("ResultatVerification doit être figé")

"""Signataire électronique factice : les versions « signées » sont gardées en mémoire."""

from typing import Any

from apps.signatures.electronique import ResultatVerification


class SignataireFactice:
    def __init__(self) -> None:
        self.signees: set[Any] = set()

    def signer(self, version: Any) -> None:
        self.signees.add(version.pk)

    def est_signee(self, version: Any) -> bool:
        return version.pk in self.signees

    def verifier(self, version: Any) -> ResultatVerification:
        if self.est_signee(version):
            return ResultatVerification(True, "CN=Factice", None, "")
        return ResultatVerification(False, "", None, "Le document n'est pas signé.")

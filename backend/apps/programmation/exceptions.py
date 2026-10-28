from apps.core.exceptions import RegleMetierError


class ProgrammeFigeError(RegleMetierError):
    """Modification d'un programme annuel validé (immuable)."""

    def __init__(self, annee: int) -> None:
        super().__init__(f"Le programme annuel {annee} est validé : il ne peut plus être modifié.")
        self.annee = annee

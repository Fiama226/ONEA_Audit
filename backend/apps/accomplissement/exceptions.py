from apps.core.exceptions import RegleMetierError


class FicheValideeError(RegleMetierError):
    """Écriture sur une fiche de test validée (ou sur l'une de ses pièces)."""

    def __init__(self, code_test: str) -> None:
        super().__init__(f"La fiche du test {code_test} est validée : rouvrez-la pour la modifier.")
        self.code_test = code_test


class FicheVerrouilleeError(RegleMetierError):
    """Écriture sur les pièces d'une fiche soumise (seules BROUILLON et RENVOYE sont ouvertes)."""

    def __init__(self, code_test: str) -> None:
        super().__init__(
            f"La fiche du test {code_test} est soumise : "
            "attendez sa validation ou son renvoi pour la modifier."
        )
        self.code_test = code_test


class PieceImmuableError(RegleMetierError):
    """Modification du fichier d'une pièce justificative déposée."""

    def __init__(self) -> None:
        super().__init__(
            "Une pièce justificative déposée ne peut pas être modifiée : déposez-en une nouvelle."
        )


MSG_AJOUT_SEUL = "Un événement de fiche ne peut pas être modifié : le journal est en ajout seul."


class InstantaneImmuableError(RegleMetierError):
    """Modification ou suppression d'un instantané du programme validé."""

    def __init__(self) -> None:
        super().__init__(
            "Un instantané du programme est définitif : il ne peut être ni modifié ni supprimé."
        )

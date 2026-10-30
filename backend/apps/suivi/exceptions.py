from apps.core.exceptions import RegleMetierError

MSG_UPSERT_INTERDIT = (
    "L'écriture avec résolution de conflit est interdite sur le suivi : "
    "elle contournerait la protection de ses champs figés."
)


class SuiviImmuableError(RegleMetierError):
    """Modification d'un champ copié à l'ouverture du suivi, figé pour toujours."""

    def __init__(self, champs: list[str]) -> None:
        super().__init__(
            "Ces champs du suivi sont figés à son ouverture et ne peuvent pas être modifiés : "
            f"{', '.join(sorted(champs))}."
        )
        self.champs = champs


class PreuveImmuableError(RegleMetierError):
    """Modification du fichier d'une preuve déposée."""

    def __init__(self) -> None:
        super().__init__("Une preuve déposée ne peut pas être modifiée : déposez-en une nouvelle.")


class AjoutSeulSuiviError(RegleMetierError):
    """Modification ou suppression d'un événement du journal de suivi."""

    def __init__(self) -> None:
        super().__init__(
            "Un événement de suivi ne peut être ni modifié ni supprimé : le journal est en "
            "ajout seul."
        )


class RelanceImmuableError(RegleMetierError):
    """Modification d'un champ figé d'une relance (seul son état d'envoi évolue)."""

    def __init__(self, champs: list[str]) -> None:
        super().__init__(
            "Seul l'état d'envoi d'une relance peut changer ; champs refusés : "
            f"{', '.join(sorted(champs))}."
        )
        self.champs = champs

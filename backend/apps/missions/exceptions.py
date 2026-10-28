from apps.core.exceptions import RegleMetierError


class MissionFigeeError(RegleMetierError):
    """Écriture sur une mission suspendue, annulée ou clôturée (ou sur l'un de ses objets)."""

    def __init__(self, reference: str, statut_libelle: str) -> None:
        super().__init__(
            f"La mission {reference} est {statut_libelle.lower()} : "
            "aucune modification n'est possible."
        )
        self.reference = reference
        self.statut_libelle = statut_libelle


class EtapeCloseError(RegleMetierError):
    """Écriture sur des travaux dont l'étape est terminée, validée ou à revalider."""

    def __init__(self, romain: str) -> None:
        super().__init__(f"L'étape {romain} est terminée : rouvrez-la pour modifier ses travaux.")
        self.romain = romain

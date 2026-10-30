from apps.core.exceptions import RegleMetierError


class ConstatValideError(RegleMetierError):
    """Écriture sur un constat validé (ou sur ses causes, recommandations, fiches liées)."""

    def __init__(self, reference: str) -> None:
        super().__init__(f"Le constat {reference} est validé : rouvrez-le pour le modifier.")
        self.reference = reference


MSG_REPONSE_AJOUT_SEUL = (
    "Une réponse de l'audité ne peut être ni modifiée ni supprimée : "
    "l'historique des réponses est en ajout seul."
)
MSG_EVENEMENT_AJOUT_SEUL = (
    "Un événement de constat ne peut pas être modifié : le journal est en ajout seul."
)


class ReponseAjoutSeulError(RegleMetierError):
    """Modification ou suppression d'une réponse de l'audité."""

    def __init__(self) -> None:
        super().__init__(MSG_REPONSE_AJOUT_SEUL)


MSG_UPSERT_INTERDIT = (
    "L'écriture avec résolution de conflit est interdite sur les constats : "
    "elle contournerait leur gel."
)
MSG_AUTRE_MISSION = "Cet objet n'appartient pas à la mission du constat."

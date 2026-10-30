from apps.core.exceptions import RegleMetierError

MSG_STATUT_SUIVI = "Le statut d'une action se met à jour pendant le suivi des recommandations."
MSG_ACCEPTATION_IMMUABLE = (
    "Une acceptation du risque ne peut pas être modifiée : retirez-la, "
    "puis saisissez-en une nouvelle."
)
MSG_ENGAGEMENT_AJOUT_SEUL = (
    "Un engagement sur le plan d'actions ne peut être ni modifié ni supprimé : "
    "l'historique des engagements est en ajout seul."
)
MSG_UPSERT_INTERDIT = (
    "L'écriture avec résolution de conflit est interdite sur le plan d'actions : "
    "elle contournerait son gel."
)
MSG_AUTRE_MISSION = "Cette recommandation n'appartient pas à la mission."


class EngagementAjoutSeulError(RegleMetierError):
    """Modification ou suppression d'un engagement sur le plan d'actions."""

    def __init__(self) -> None:
        super().__init__(MSG_ENGAGEMENT_AJOUT_SEUL)

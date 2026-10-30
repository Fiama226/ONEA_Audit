from apps.core.exceptions import RegleMetierError


class RapportFigeError(RegleMetierError):
    """Écriture sur un rapport qui n'est plus modifiable (soumis, validé, diffusé, remplacé)."""

    def __init__(self, statut: str) -> None:
        super().__init__(f"Le rapport est {statut} : il ne peut plus être modifié.")
        self.statut = statut


MSG_RAPPORT_HORS_COMMUNICATION = (
    "La mission n'est pas en phase de communication : le rapport ne peut pas être modifié."
)
MSG_TRANSITION_INTERDITE = "Cette transition du rapport n'est pas permise : {avant} vers {apres}."
MSG_TRANSITION_CHAMPS = (
    "Cette transition du rapport ne peut pas modifier les champs suivants : {champs}."
)
MSG_AUTRE_MISSION = "Cet objet n'appartient pas à la mission du rapport."
MSG_UPSERT_INTERDIT = (
    "L'écriture avec résolution de conflit est interdite sur les objets de la communication : "
    "elle contournerait leur gel."
)
MSG_DESTINATAIRES_FIGES = (
    "Le rapport est diffusé : la liste de diffusion ne peut plus être modifiée "
    "(seul le suivi des destinataires reste permis)."
)
MSG_SUIVI_HORS_DIFFUSION = (
    "Le suivi d'un destinataire n'est possible que lorsque le rapport est diffusé."
)

_AJOUT_SEUL = "{objet} ne peut être ni modifié ni supprimé : il est en ajout seul."


class AjoutSeulError(RegleMetierError):
    """Modification ou suppression d'un objet de la communication en ajout seul."""

    def __init__(self, objet: str) -> None:
        super().__init__(_AJOUT_SEUL.format(objet=objet))

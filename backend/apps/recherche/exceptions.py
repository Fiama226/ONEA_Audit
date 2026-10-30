from apps.core.exceptions import RegleMetierError


class RechercheIndisponibleError(RegleMetierError):
    """Le moteur de recherche ne répond pas (réseau, délai, 5xx) : HTTP 503."""

    status_http = 503

    def __init__(self) -> None:
        super().__init__("La recherche est momentanément indisponible. Réessayez plus tard.")

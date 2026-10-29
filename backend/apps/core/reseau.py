"""Adresse IP réelle du client derrière le proxy (nginx).

``X-Real-IP`` n'est cru que si le pair TCP (``REMOTE_ADDR``) appartient à
``TRUSTED_PROXY_CIDRS`` (vide par défaut : on ne fait confiance à personne).
``X-Forwarded-For`` n'est jamais lu : un client peut y écrire ce qu'il veut.
"""

import ipaddress
import logging

from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger(__name__)

PROXY_META = "ONEA_PROXY_ADDR"


def _adresse_valide(valeur: str | None) -> str | None:
    """Renvoie la forme canonique d'une adresse IP unique, sinon None."""
    if not valeur:
        return None
    try:
        return str(ipaddress.ip_address(valeur.strip()))
    except ValueError:
        return None


def pair_de_confiance(pair: str | None) -> bool:
    adresse = _adresse_valide(pair)
    if adresse is None:
        return False
    ip = ipaddress.ip_address(adresse)
    for cidr in getattr(settings, "TRUSTED_PROXY_CIDRS", []):
        try:
            if ip in ipaddress.ip_network(str(cidr).strip(), strict=False):
                return True
        except ValueError:
            logger.warning("TRUSTED_PROXY_CIDRS contient une entrée invalide, ignorée.")
    return False


def adresse_reelle(meta: dict[str, object]) -> str | None:
    """Adresse du client d'après les métadonnées WSGI (sans modifier la requête)."""
    pair = meta.get("REMOTE_ADDR")
    pair_str = pair if isinstance(pair, str) else None
    if pair_de_confiance(pair_str):
        brut = meta.get("HTTP_X_REAL_IP")
        if isinstance(brut, str) and brut:
            valide = _adresse_valide(brut)
            if valide is not None:
                return valide
            logger.warning("En-tête X-Real-IP invalide reçu d'un proxy de confiance, ignoré.")
    return pair_str


def adresse_client(request: HttpRequest) -> str | None:
    """Adresse du client (le middleware a déjà substitué ``REMOTE_ADDR`` si besoin)."""
    valeur = request.META.get("REMOTE_ADDR")
    return valeur if isinstance(valeur, str) and valeur else None

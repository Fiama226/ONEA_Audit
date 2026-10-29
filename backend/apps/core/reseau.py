"""Adresse IP réelle du client derrière le proxy (nginx).

``X-Real-IP`` n'est cru que si le pair TCP (``REMOTE_ADDR``) appartient à
``TRUSTED_PROXY_CIDRS`` (vide par défaut : on ne fait confiance à personne).
``X-Forwarded-For`` n'est jamais lu : un client peut y écrire ce qu'il veut.
"""

import ipaddress
import logging
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest

logger = logging.getLogger(__name__)

PROXY_META = "ONEA_PROXY_ADDR"

Reseau = ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache(maxsize=8)
def _analyser(cidrs: tuple[str, ...]) -> tuple[Reseau, ...]:
    reseaux: list[Reseau] = []
    for brut in cidrs:
        try:
            reseaux.append(ipaddress.ip_network(str(brut).strip(), strict=False))
        except ValueError as exc:
            raise ImproperlyConfigured(
                "TRUSTED_PROXY_CIDRS contient une entrée qui n'est pas une adresse ou un "
                "réseau CIDR valide."
            ) from exc
    return tuple(reseaux)


def reseaux_de_confiance() -> tuple[Reseau, ...]:
    """Réseaux de confiance, analysés une seule fois (échec franc si une entrée est invalide)."""
    return _analyser(tuple(getattr(settings, "TRUSTED_PROXY_CIDRS", [])))


def _adresse_valide(valeur: str | None) -> str | None:
    """Forme canonique d'une adresse IP unique (IPv4-mappé déplié, sans zone), sinon None."""
    if not valeur:
        return None
    try:
        ip = ipaddress.ip_address(valeur.strip())
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        if getattr(ip, "scope_id", None):
            return None
    return str(ip)


def pair_de_confiance(pair: str | None) -> bool:
    adresse = _adresse_valide(pair)
    if adresse is None:
        return False
    ip = ipaddress.ip_address(adresse)
    return any(ip in reseau for reseau in reseaux_de_confiance() if reseau.version == ip.version)


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

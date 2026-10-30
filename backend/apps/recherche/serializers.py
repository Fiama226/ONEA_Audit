"""Sérialiseurs de la recherche : paramètres validés et résultats nettoyés.

`titre` et `extrait` ne conservent que les deux marqueurs de surlignage du moteur ; tout autre
caractère de contrôle ou de mise en forme (dont les inversions bidirectionnelles) est retiré.
"""

import unicodedata
from typing import Any

from rest_framework import serializers

from .client import MARQUEUR_DEBUT, MARQUEUR_FIN
from .sources import SOURCES

LONGUEUR_BRUTE_MAX = 1000
TYPES_RECHERCHE_CHOICES: list[tuple[str, str]] = [(t, t) for t in sorted(SOURCES)]
_BLANCS = {"\n", "\r", "\t", "\u2028", "\u2029"}


def nettoyer_affichage(texte: str, *, marqueurs: bool) -> str:
    """Retire les caractères de contrôle ; seuls les marqueurs de surlignage peuvent survivre."""
    sortie: list[str] = []
    for c in str(texte):
        if c in (MARQUEUR_DEBUT, MARQUEUR_FIN):
            if marqueurs:
                sortie.append(c)
        elif c in _BLANCS:
            sortie.append(" ")
        elif unicodedata.category(c) not in ("Cc", "Cf"):
            sortie.append(c)
    return "".join(sortie)


class RechercheParametresSerializer(serializers.Serializer[dict[str, Any]]):
    q = serializers.CharField(
        max_length=LONGUEUR_BRUTE_MAX,
        trim_whitespace=False,
        help_text="Texte recherché (2 à 200 caractères après nettoyage).",
    )
    types = serializers.CharField(
        required=False,
        max_length=200,
        help_text="Types séparés par des virgules : " + ", ".join(sorted(SOURCES)) + ".",
    )

    def validate_types(self, valeur: str) -> list[str]:
        types = [t.strip() for t in valeur.split(",")]
        if not all(types):
            raise serializers.ValidationError("Liste de types invalide.")
        return list(dict.fromkeys(types))

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # Un paramètre vide (	ypes=) est ignoré par DRF : on le refuse explicitement.
        if "types" in self.initial_data and "types" not in attrs:
            raise serializers.ValidationError({"types": ["Liste de types invalide."]})
        return attrs


class ResultatRechercheSerializer(serializers.Serializer[dict[str, Any]]):
    type = serializers.ChoiceField(choices=TYPES_RECHERCHE_CHOICES)
    objet_id = serializers.UUIDField()
    mission_id = serializers.UUIDField(allow_null=True)
    mission_reference = serializers.CharField(allow_blank=True)
    titre = serializers.CharField()
    sous_titre = serializers.CharField(allow_blank=True)
    extrait = serializers.CharField(allow_blank=True)
    etape = serializers.IntegerField(allow_null=True)


class ReponseRechercheSerializer(serializers.Serializer[dict[str, Any]]):
    resultats = ResultatRechercheSerializer(many=True)
    plus = serializers.BooleanField()

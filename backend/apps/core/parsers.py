"""Analyseurs de corps de requête : une entrée hostile ne doit jamais produire une erreur 500."""

from typing import Any

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class JSONParserSur(JSONParser):
    """JSON dont une imbrication excessive est refusée (400) au lieu de faire échouer le serveur."""

    def parse(self, stream: Any, media_type: Any = None, parser_context: Any = None) -> Any:
        try:
            return super().parse(stream, media_type, parser_context)
        except RecursionError:
            raise ParseError("Imbrication excessive.") from None

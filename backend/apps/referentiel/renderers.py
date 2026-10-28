from typing import Any

from rest_framework.renderers import BaseRenderer, JSONRenderer


class PassthroughRenderer(BaseRenderer):
    """Accepte n'importe quel en-tête `Accept` pour les téléchargements de fichiers.

    Le contenu est produit par la vue (`HttpResponse`) ; ce moteur ne sert qu'à éviter le 406
    de la négociation, et rend en JSON les éventuelles erreurs (400, 403, 404).
    """

    media_type = "*/*"
    format = ""
    charset = None
    render_style = "binary"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: Any = None,
    ) -> bytes:
        if isinstance(data, bytes):
            return data
        if data is None:
            return b""
        return bytes(JSONRenderer().render(data, accepted_media_type, renderer_context))

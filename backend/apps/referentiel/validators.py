import re

from django.core.validators import RegexValidator

# Caractères de contrôle interdits dans les textes libres ; \t, \n et \r restent permis.
CARACTERES_CONTROLE_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MSG_CARACTERES_CONTROLE = "Les caractères de contrôle ne sont pas autorisés."

valider_code_processus = RegexValidator(
    r"^[A-Z]{2,5}\Z",
    message="Le code d'un processus comporte de 2 à 5 lettres majuscules sans accent.",
    code="code_processus_invalide",
)

valider_code_direction = RegexValidator(
    r"^[A-Z][A-Z0-9-]{1,15}\Z",
    message=(
        "Le code d'une direction comporte de 2 à 16 caractères : majuscules sans accent, "
        "chiffres ou tirets, en commençant par une lettre."
    ),
    code="code_direction_invalide",
)

valider_code_risque = RegexValidator(
    r"^[1-9][0-9]*-[A-Z]{2,5}-R[1-9][0-9]*\Z",
    message="Le code d'un risque doit suivre le format <numéro>-<CODE_PROCESSUS>-R<rang>.",
    code="code_risque_invalide",
)

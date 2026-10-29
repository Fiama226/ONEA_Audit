"""Bounded rendering of Word templates.

Untrusted templates are rendered in a child Python process (`bac_a_sable`) so that a template
which loops or allocates for too long can be killed instead of freezing a web worker or a
Celery task:

- wall-clock limit (`delai_s`, the child is killed on expiry), portable;
- on POSIX, address-space and CPU limits set in the child (`resource.setrlimit`); on Windows
  (development only) only the wall-clock limit applies;
- operators able to allocate huge values are refused inside the sandbox (fail fast, French
  error), and the produced .docx is capped at 50 Mo.

A subprocess (not `multiprocessing`) is used because Celery prefork workers are daemonic and
may not start multiprocessing children.
"""

import base64
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

from .bac_a_sable import CODE_ERREUR, MAX_DOCX_OCTETS
from .contrats import CHAMPS_COMMUNS, Contrat, champ_vers_dict, ecarts_contexte
from .exceptions import RenduError

logger = logging.getLogger(__name__)

DELAI_PAR_DEFAUT_S: Final = 60.0
LIMITE_MEMOIRE_OCTETS: Final = 2 * 1024 * 1024 * 1024
_BACKEND: Final = Path(__file__).resolve().parents[3]
_VARIABLES_UTILES: Final = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")


def _limiter_ressources(delai_s: float) -> None:  # pragma: no cover - runs in the child
    if sys.platform == "win32":
        return
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (LIMITE_MEMOIRE_OCTETS, LIMITE_MEMOIRE_OCTETS))
    cpu = int(delai_s) + 5
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))


def rendre_docx(
    gabarit: bytes,
    contexte: dict[str, Any],
    contrat: Contrat,
    *,
    delai_s: float = DELAI_PAR_DEFAUT_S,
) -> bytes:
    """Render `gabarit` with `contexte`, which must conform to `contrat`."""
    ecarts = ecarts_contexte(contrat, contexte)
    if ecarts:
        raise RenduError(
            "Les données du document ne respectent pas le contrat : " + " ".join(ecarts)
        )
    entree = json.dumps(
        {
            "gabarit": base64.b64encode(gabarit).decode("ascii"),
            "contexte": contexte,
            "champs": [champ_vers_dict(c) for c in CHAMPS_COMMUNS + contrat.champs],
        }
    ).encode("utf-8")
    env = {nom: os.environ[nom] for nom in _VARIABLES_UTILES if nom in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"  # French messages on stderr must be UTF-8 on every platform
    options: dict[str, Any] = {}
    if os.name == "posix":
        options["preexec_fn"] = lambda: _limiter_ressources(delai_s)
    try:
        fini = subprocess.run(  # noqa: S603 - fixed argv, no shell, trusted module
            [sys.executable, "-m", "apps.documents.moteur.bac_a_sable"],
            input=entree,
            capture_output=True,
            timeout=delai_s,
            cwd=_BACKEND,
            env=env,
            check=False,
            **options,
        )
    except subprocess.TimeoutExpired:
        raise RenduError(
            f"Le rendu du document a dépassé le délai autorisé ({delai_s:g} s) : "
            "le gabarit est trop complexe."
        ) from None
    if fini.returncode == 0:
        if len(fini.stdout) > MAX_DOCX_OCTETS:
            raise RenduError(
                "Le rendu du document a échoué : le document produit est trop volumineux."
            )
        resultat: bytes = fini.stdout
        return resultat
    sortie = fini.stderr.decode("utf-8", errors="replace").splitlines()
    if fini.returncode == CODE_ERREUR and sortie:
        logger.warning("Rendu de gabarit refusé : %s", " | ".join(sortie[1:]))
        raise RenduError(sortie[0])
    logger.error("Sous-processus de rendu interrompu (code %s)", fini.returncode)
    raise RenduError("Le rendu du document a échoué : ressources autorisées dépassées.")

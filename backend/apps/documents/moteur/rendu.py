"""Bounded rendering of Word templates.

Untrusted templates are rendered in a child Python process (`bac_a_sable`) so that a template
which loops or allocates for too long can be killed instead of freezing a web worker or a
Celery task:

- wall-clock limit (`delai_s`, the child is killed on expiry), portable;
- on POSIX, address-space (`memoire_mo`, default 1 GiB per render) and CPU limits applied by the
  child itself at start-up (no `preexec_fn`, which is unsafe in a threaded parent); on Windows
  (development only) only the wall-clock limit applies;
- operators able to allocate huge values are refused inside the sandbox (defence in depth, not
  a complete bound: the process limits are the real bound);
- the rendered .docx is scanned for forbidden fields and external links before it is returned.

A subprocess (not `multiprocessing`) is used because Celery prefork workers are daemonic and
may not start multiprocessing children. Size the number of concurrent renders (Celery
concurrency) with the per-render memory limit in mind.
"""

import base64
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

from .bac_a_sable import MARQUEUR_ERREUR, MAX_DOCX_OCTETS, MESSAGES
from .contrats import CHAMPS_COMMUNS, Contrat, champ_vers_dict, ecarts_contexte
from .exceptions import RenduError

logger = logging.getLogger(__name__)

DELAI_PAR_DEFAUT_S: Final = 60.0
MEMOIRE_PAR_DEFAUT_MO: Final = 1024
_BACKEND: Final = Path(__file__).resolve().parents[3]
_VARIABLES_UTILES: Final = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")
_STDERR_LOG_MAX: Final = 4096


def _code_depuis_stderr(erreur: bytes) -> tuple[str, str]:
    """(error code, truncated detail) from the child's last marker line; never the raw text."""
    texte = erreur[-_STDERR_LOG_MAX:].decode("utf-8", errors="replace")
    for ligne in reversed(texte.splitlines()):
        if ligne.startswith(MARQUEUR_ERREUR):
            code, _, detail = ligne[len(MARQUEUR_ERREUR) :].partition(":")
            return (code if code in MESSAGES else "generique"), detail
    return "generique", texte


def rendre_docx(
    gabarit: bytes,
    contexte: dict[str, Any],
    contrat: Contrat,
    *,
    delai_s: float = DELAI_PAR_DEFAUT_S,
    memoire_mo: int = MEMOIRE_PAR_DEFAUT_MO,
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
    env["PYTHONUTF8"] = "1"
    try:
        fini = subprocess.run(  # noqa: S603 - fixed argv, no shell, trusted module
            [
                sys.executable,
                "-W",
                "ignore",
                "-m",
                "apps.documents.moteur.bac_a_sable",
                "--memoire-mo",
                str(memoire_mo),
                "--cpu-s",
                str(int(delai_s) + 5),
            ],
            input=entree,
            capture_output=True,
            timeout=delai_s,
            cwd=_BACKEND,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RenduError(
            f"Le rendu du document a dépassé le délai autorisé ({delai_s:g} s) : "
            "le gabarit est trop complexe."
        ) from None
    if fini.returncode == 0:
        resultat: bytes = fini.stdout
        if len(resultat) > MAX_DOCX_OCTETS:
            raise RenduError(MESSAGES["sortie_volumineuse"])
        return resultat
    code, detail = _code_depuis_stderr(fini.stderr)
    logger.warning(
        "Rendu de gabarit refusé (code %s, retour %s) : %s", code, fini.returncode, detail
    )
    raise RenduError(MESSAGES[code])

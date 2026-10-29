"""Structured JSON logging without personal data, request/task correlation.

The formatter and the masking filter use the standard library only, so that they can be
loaded by gunicorn's log configuration before Django is set up.
"""

import json
import logging
import re
import time
import traceback
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from django.http import HttpRequest
from django.http.response import HttpResponseBase

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
tache_var: ContextVar[str] = ContextVar("tache", default="")

EN_TETE = "X-Correlation-ID"
_ID_VALIDE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_MASQUE = "[masqué]"

# Order matters: JWT and Bearer first, then key=value secrets, e-mails, query strings.
_MOTIFS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]*"), _MASQUE),
    (re.compile(r"(?i)\bbearer\s+\S+"), f"Bearer {_MASQUE}"),
    (
        re.compile(
            r"(?i)\b(password|passwd|mot_de_passe|secret|token|jeton|api[_-]?key|authorization)"
            r"(\s*[=:]\s*)[^\s&,;]+"
        ),
        rf"\1\2{_MASQUE}",
    ),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[courriel]"),
    (re.compile(r"\?\S+"), ""),  # query strings may carry search terms (personal data)
)


def masquer(texte: str) -> str:
    for motif, remplacement in _MOTIFS:
        texte = motif.sub(remplacement, texte)
    return texte


class MasquageFiltre(logging.Filter):
    """Mask e-mails, tokens, secrets and query strings in the final message."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = masquer(record.getMessage())
        except Exception:  # noqa: BLE001 - a logging filter must never raise
            record.msg = "[message illisible]"
        record.args = None
        return True


_CHAMPS = ("methode", "chemin", "statut", "duree_ms", "user_id", "tache")


class FormateurJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        donnees: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "niveau": record.levelname,
            "logger": record.name,
            "message": masquer(record.getMessage()),
            "correlation_id": correlation_id_var.get() or None,
        }
        for champ in _CHAMPS:
            valeur = getattr(record, champ, None)
            if valeur is not None:
                donnees[champ] = valeur
        if "tache" not in donnees and tache_var.get():
            donnees["tache"] = tache_var.get()
        if record.exc_info:
            donnees["exception"] = masquer("".join(traceback.format_exception(*record.exc_info)))
        return json.dumps(donnees, ensure_ascii=False, default=str)


# --- HTTP --------------------------------------------------------------------------------

logger_requete = logging.getLogger("onea.requete")


class CorrelationMiddleware:
    """Set the correlation id, echo it in the response and log one line per request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        recu = request.headers.get(EN_TETE, "")
        identifiant = recu if _ID_VALIDE.match(recu) else uuid.uuid4().hex
        jeton = correlation_id_var.set(identifiant)
        debut = time.monotonic()
        statut = 500
        try:
            response = self.get_response(request)
            statut = response.status_code
            response[EN_TETE] = identifiant
            return response
        finally:
            utilisateur = getattr(request, "user", None)
            user_id = (
                getattr(utilisateur, "pk", None)
                if getattr(utilisateur, "is_authenticated", False)
                else None
            )
            sonde = request.path.startswith("/api/v1/health/")
            logger_requete.log(
                logging.DEBUG if sonde else logging.INFO,
                "requête traitée",
                extra={
                    "methode": request.method,
                    "chemin": request.path,
                    "statut": statut,
                    "duree_ms": round((time.monotonic() - debut) * 1000),
                    "user_id": str(user_id) if user_id is not None else None,
                },
            )
            correlation_id_var.reset(jeton)


# --- Celery ------------------------------------------------------------------------------

logger_celery = logging.getLogger("onea.celery")


def avant_publication(headers: dict[str, Any] | None = None, **_: Any) -> None:
    identifiant = correlation_id_var.get()
    if headers is not None and identifiant:
        headers["correlation_id"] = identifiant


def avant_execution(task: Any = None, task_id: Any = None, **_: Any) -> None:
    identifiant = getattr(getattr(task, "request", None), "correlation_id", None)
    correlation_id_var.set(identifiant or uuid.uuid4().hex)
    tache_var.set(getattr(task, "name", "") or "")


def apres_execution(**_: Any) -> None:
    correlation_id_var.set("")
    tache_var.set("")


def echec_tache(
    sender: Any = None, task_id: Any = None, exception: BaseException | None = None, **_: Any
) -> None:
    """Log a failure with the task name and exception class only: never the arguments."""
    logger_celery.error(
        "échec de la tâche %s (%s)",
        getattr(sender, "name", "?"),
        type(exception).__name__,
        extra={"tache": getattr(sender, "name", None)},
    )


def connecter_signaux_celery() -> None:
    from celery.signals import (
        before_task_publish,
        task_failure,
        task_postrun,
        task_prerun,
    )

    before_task_publish.connect(avant_publication, weak=False, dispatch_uid="onea-pub")
    task_prerun.connect(avant_execution, weak=False, dispatch_uid="onea-pre")
    task_postrun.connect(apres_execution, weak=False, dispatch_uid="onea-post")
    task_failure.connect(echec_tache, weak=False, dispatch_uid="onea-fail")

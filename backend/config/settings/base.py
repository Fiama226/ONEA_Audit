import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import environ
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

from config import __version__
from config.documents_settings import configuration_stockage

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# .env lives at the repository root (shared with docker compose)
ENV_FILE = BASE_DIR.parent / ".env"
if ENV_FILE.exists() and not env.bool("ONEA_IGNORE_DOTENV", default=False):
    environ.Env.read_env(str(ENV_FILE))


# --- Bloc T17 : secrets lus dans des fichiers (D16). `<NOM>_FILE` est prioritaire sur `<NOM>`.
def env_secret(nom: str, default: Any = environ.Env.NOTSET) -> str:
    """Valeur du secret `nom` : contenu du fichier `<nom>_FILE` s'il est défini, sinon `<nom>`.

    Seuls les sauts de ligne finaux sont retirés. Un fichier illisible lève ImproperlyConfigured
    en nommant la variable ; la valeur du secret n'apparaît jamais dans un message d'erreur.
    """
    chemin = os.environ.get(f"{nom}_FILE", "")
    if not chemin:
        return str(env(nom, default=default))
    try:
        contenu = Path(chemin).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ImproperlyConfigured(
            f"{nom}_FILE : le fichier « {chemin} » est absent ou illisible."
        ) from exc
    return contenu.rstrip("\r\n")


def base_de_donnees(nom: str = "DATABASE_URL", default: Any = environ.Env.NOTSET) -> dict[str, Any]:
    """Configuration de base : `DATABASE_PASSWORD_FILE` remplace le mot de passe de l'URL."""
    config: dict[str, Any] = env.db(nom, default=default)
    if os.environ.get("DATABASE_PASSWORD_FILE"):
        config["PASSWORD"] = env_secret("DATABASE_PASSWORD")
    return config


def url_redis(nom: str = "REDIS_URL", default: Any = environ.Env.NOTSET) -> str:
    """URL Redis : avec `REDIS_PASSWORD_FILE`, l'URL est reconstruite avec le mot de passe lu."""
    url: str = env(nom, default=default)
    if not os.environ.get("REDIS_PASSWORD_FILE"):
        return url
    parties = urlsplit(url)
    machine = parties.netloc.rpartition("@")[2]
    mot_de_passe = quote(env_secret("REDIS_PASSWORD"), safe="")
    return urlunsplit(parties._replace(netloc=f":{mot_de_passe}@{machine}"))


def _lignes(valeur: str) -> list[str]:
    return [v.strip() for v in re.split(r"[\n,]", valeur) if v.strip()]


SECRET_KEY = env_secret("SECRET_KEY", default="insecure-dev-key-change-me")  # noqa: S105
# Anciennes clés encore acceptées pendant une rotation (une par ligne ou séparées par des virgules).
SECRET_KEY_FALLBACKS: list[str] = _lignes(env_secret("SECRET_KEY_FALLBACKS", default=""))
DEBUG = False
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "django_filters",
    "auditlog",
    "apps.core",
    "apps.users",
    "apps.referentiel",
    "apps.signatures",
    "apps.missions",
    "apps.programmation",
    "apps.analyse",
    "apps.accomplissement",
    "apps.constats",
    "apps.recommandations",
    "apps.communication",
    "apps.documents",
    "apps.suivi",
    "apps.notifications",
    "apps.recherche",
    "apps.tableaux_de_bord",
]

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.journalisation.CorrelationMiddleware",
    "apps.core.middleware.PasDeCacheApiMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.SessionLimiteeMiddleware",
    "apps.core.middleware.MotDePasseAChangerMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.AdresseClientMiddleware",
    "apps.core.middleware.LazyActorAuditlogMiddleware",
]

# T6 : pairs (CIDR) dont X-Real-IP est cru ; vide = personne.
TRUSTED_PROXY_CIDRS: list[str] = env.list("TRUSTED_PROXY_CIDRS", default=[])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": base_de_donnees("DATABASE_URL", default="postgres://onea:onea@localhost:5432/onea"),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL: str = url_redis("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))

# --- Documents: files live on the server disk (or S3), never in Git, never at a public URL.
# No MEDIA_URL on purpose: downloads go through the authenticated API only.
DOCUMENTS_STORAGE: str = env("DOCUMENTS_STORAGE", default="filesystem")
if DOCUMENTS_STORAGE not in {"filesystem", "s3"}:
    raise ImproperlyConfigured("DOCUMENTS_STORAGE must be 'filesystem' or 's3'")
DOCUMENTS_ROOT: str = env("DOCUMENTS_ROOT", default=str(BASE_DIR.parent / ".dev" / "documents"))
DOCUMENTS_MAX_GABARIT_MO: int = env.int("DOCUMENTS_MAX_GABARIT_MO", default=10)
DOCUMENTS_ESPACE_MIN_LIBRE_MO: int = env.int("DOCUMENTS_ESPACE_MIN_LIBRE_MO", default=1024)
DOCUMENTS_QUOTA_MO: int = env.int("DOCUMENTS_QUOTA_MO", default=0)  # 0 = no quota
DOCUMENTS_PDFA: bool = env.bool("DOCUMENTS_PDFA", default=True)
RECHERCHE = {
    "BACKEND": env("RECHERCHE_BACKEND", default="apps.recherche.client.MeilisearchHttp"),
    "URL": env("MEILI_URL", default="http://localhost:7700"),
    "CLE": env_secret("MEILI_MASTER_KEY", default=""),
    "INDEX": env("MEILI_INDEX", default="onea"),
    "TIMEOUT": 3,
}
# Types de documents que l'audité peut trouver dans la recherche (R14, spec §5) ; le rapport
# n'est indexé pour l'audité et le DG qu'une fois diffusé.
RECHERCHE_TYPES_DOCUMENTS_AUDITE: list[str] = [
    "ORDRE_MISSION",
    "PV_OUVERTURE",
    "PV_CLOTURE",
    "RAPPORT_FINAL",
]
GOTENBERG_URL: str = env("GOTENBERG_URL", default="http://localhost:3000").rstrip("/")
# --- Pièces justificatives (lot 6) : disque du serveur, jamais dans Git, jamais sous une URL.
STOCKAGE_PREUVES: dict[str, Any] = {
    "BACKEND": env(
        "STOCKAGE_PREUVES_BACKEND", default="apps.accomplissement.stockage.StockageDisque"
    ),
    "OPTIONS": {
        "RACINE": env("FICHIERS_RACINE", default=str(BASE_DIR.parent / "var" / "fichiers"))
    },
}
PIECE_TAILLE_MAX_OCTETS: int = 50 * 1024 * 1024  # aligné sur `client_max_body_size 50m` de Nginx

# --- Bloc T15 : téléversements. Les fichiers dépassant 5 Mo passent par un fichier temporaire ;
# la limite de 50 Mo des pièces est contrôlée par `core.fichiers` (et `nginx`, 55 Mo sur /api/).
DATA_UPLOAD_MAX_MEMORY_SIZE: int = 5 * 1024 * 1024  # corps hors fichiers
FILE_UPLOAD_MAX_MEMORY_SIZE: int = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES: int = 5
ANTIVIRUS_MOTEUR: str = env("ANTIVIRUS_MOTEUR", default="aucun")
if ANTIVIRUS_MOTEUR not in {"aucun", "clamav", "clamd"}:  # clamd : synonyme historique de clamav
    raise ImproperlyConfigured("ANTIVIRUS_MOTEUR must be 'aucun' or 'clamav'")
# Échec fermé : clamd injoignable => fichier refusé (503). `false` = choix explicite d'accepter.
ANTIVIRUS_ECHEC_FERME: bool = env.bool("ANTIVIRUS_ECHEC_FERME", default=True)
ANTIVIRUS_TAILLE_MAX_OCTETS: int = PIECE_TAILLE_MAX_OCTETS  # nginx : 55m
ANTIVIRUS_CLAMD_HOTE: str = env("ANTIVIRUS_CLAMD_HOTE", default="clamav")
ANTIVIRUS_CLAMD_PORT: int = env.int("ANTIVIRUS_CLAMD_PORT", default=3310)

DOCUMENTS_CREER_DOSSIER = False  # dev.py enables it; production must not create it
GOTENBERG_TIMEOUT = 90  # seconds (read timeout of the docx -> PDF conversion)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "documents": configuration_stockage(
        {**os.environ, "DOCUMENTS_STORAGE": DOCUMENTS_STORAGE, "DOCUMENTS_ROOT": DOCUMENTS_ROOT}
    ),
}

# Django admin (/admin/) is mounted only when enabled; prod.py defaults it to False.
DJANGO_ADMIN_ENABLED: bool = env.bool("DJANGO_ADMIN_ENABLED", default=True)


# Scopes of `apps.users.auth_throttles`: their period may carry a multiplier ("30/15min").
_PORTEES_AUTHENTIFICATION = frozenset(
    {
        "connexion",
        "connexion_code",
        "mot_de_passe_oublie",
        "mot_de_passe_oublie_ip",
        "reinitialisation",
        "changement_mot_de_passe",
        "echecs_connexion",
        "echecs_reinitialisation",
    }
)


def _taux_debit(portee: str, defaut: str) -> str:
    """Taux « N/min|hour|day » d'une portée, surchargeable par THROTTLE_RATE_<PORTEE>.

    Les portées de l'authentification acceptent aussi un multiple de la période (« 30/15min »).
    """
    valeur: str = env(f"THROTTLE_RATE_{portee.upper()}", default=defaut).strip()
    multiple = r"([1-9]\d*)?" if portee in _PORTEES_AUTHENTIFICATION else ""
    if not re.fullmatch(rf"[1-9]\d*/{multiple}(sec|min|hour|day)", valeur):
        raise ImproperlyConfigured(
            f"THROTTLE_RATE_{portee.upper()} doit avoir la forme « 20/min » (sec, min, hour, day)."
        )
    return valeur


REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "apps.core.handlers.api_exception_handler",
    "DEFAULT_PARSER_CLASSES": [
        "apps.core.parsers.JSONParserSur",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    # In-app session login only (CSRF enforced on writes); same origin, no bearer tokens.
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.users.authentication.SessionAuthentication401"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    # T12 : limitation de débit par utilisateur (D3), sans effet hors vues à portée.
    "DEFAULT_THROTTLE_CLASSES": ["apps.core.throttling.UtilisateurScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        portee: _taux_debit(portee, defaut)
        for portee, defaut in {
            "generation": "20/min",
            "apercu": "30/min",
            "televersement": "30/hour",
            "import": "10/hour",
            "export": "30/min",
            "anonyme": "30/min",
            "recherche": "60/min",
            # Authentication (apps.users.auth_throttles, AUTH-04/05): one bucket per endpoint,
            # per client IP (IPv6: per /64). Sized for a head office behind one NAT address;
            # the per-account lockout (5 failures, 15 min) is the brute-force defence. Each
            # one is overridable by THROTTLE_RATE_<SCOPE>, e.g. THROTTLE_RATE_CONNEXION=120/min.
            "connexion": "60/min",
            "connexion_code": "30/min",
            "mot_de_passe_oublie_ip": "20/min",
            "reinitialisation": "20/min",
            # failures only, across accounts: one address cannot keep many accounts locked
            "echecs_connexion": "30/15min",
            "echecs_reinitialisation": "30/hour",
            # per user: change of password, removal of the login code (password re-checked)
            "changement_mot_de_passe": "10/min",
            # per typed identifier on "forgotten password" (+ a per-account quota in the DB)
            "mot_de_passe_oublie": "5/hour",
            # per user: account creation, password reset, login-code removal (emails sent)
            "gestion_comptes": "30/hour",
        }.items()
    },
}


def _entier_positif(nom: str, defaut: int) -> int:
    """A positive integer from the environment; anything else stops the start-up (N5)."""
    try:
        valeur = int(env(nom, default=str(defaut)))
    except ValueError:
        valeur = 0
    if valeur < 1:
        raise ImproperlyConfigured(f"{nom} doit être un entier strictement positif.")
    return valeur


# AUTH-02: wrong forgotten-password codes accepted per account over 24 h, whatever the code
# (then no code is issued nor accepted until the window ends; the admin reset remains).
AUTH_REINITIALISATION_ECHECS_MAX: int = _entier_positif("AUTH_REINITIALISATION_ECHECS_MAX", 15)
# N6: login codes mailed per account over 15 min (whoever knows the password cannot flood
# the owner's mailbox; past it, no code is issued until the window ends).
AUTH_CODES_CONNEXION_MAX: int = _entier_positif("AUTH_CODES_CONNEXION_MAX", 10)

SPECTACULAR_SETTINGS = {
    "TITLE": "API Audit Interne ONEA",
    "DESCRIPTION": (
        "API de la plateforme de digitalisation de l'audit interne de l'ONEA. "
        "Les erreurs suivent le format {detail, errors} (composant ApiError)."
    ),
    "VERSION": __version__,
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    # On-site deployment without Internet: serve Swagger UI/Redoc assets locally.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # Stable component names for enums shared by several serializers and filters.
    "ENUM_NAME_OVERRIDES": {
        # Journal d'audit (liste inline dans apps.core.serializers) : nom historique conservé.
        "ActionEnum": ["create", "update", "delete", "access", "unknown"],
        "ActionTutorielEnum": "apps.users.models.ActionTutoriel.choices",
        "TypeEntiteEnum": "apps.referentiel.models.TypeEntite.choices",
        "FamilleProcessusEnum": "apps.referentiel.models.FamilleProcessus.choices",
        "NatureObjetEnum": "apps.referentiel.models.NatureObjet.choices",
        "StatutCartographieEnum": "apps.referentiel.models.StatutCartographie.choices",
        "NiveauRisqueEnum": "apps.referentiel.models.NiveauRisque.choices",
        "ReponseRisqueEnum": "apps.referentiel.models.ReponseRisque.choices",
        "PrioriteRisqueEnum": "apps.referentiel.models.PrioriteRisque.choices",
        "TypeMissionEnum": "apps.missions.models.TypeMission.choices",
        "StatutMissionEnum": "apps.missions.models.StatutMission.choices",
        "EvenementDeclencheurEnum": "apps.missions.models.EvenementDeclencheur.choices",
        "RoleMissionEnum": "apps.missions.models.RoleMission.choices",
        "PhaseEnum": "apps.missions.models.Phase.choices",
        "StatutEtapeEnum": "apps.missions.models.StatutEtape.choices",
        "TypeEvenementEtapeEnum": "apps.missions.models.TypeEvenementEtape.choices",
        "StatutDeclarationEnum": "apps.missions.models.StatutDeclaration.choices",
        "TypeReunionEnum": "apps.missions.models.TypeReunion.choices",
        "StatutEntretienEnum": "apps.missions.models.StatutEntretien.choices",
        "ActionEtapeEnum": "apps.missions.services.etapes.ActionEtape.choices",
        "TypeDocumentSignableEnum": "apps.signatures.models.TypeDocumentSignable.choices",
        "ModeSignatureParametreEnum": "apps.signatures.models.ModeSignatureParametre.choices",
        "OrigineCompteEnum": "apps.users.models.OrigineCompte.choices",
        "StatutProgrammeEnum": "apps.programmation.models.StatutProgramme.choices",
        # programmation.TypeIntervention a les mêmes choix que missions.TypeMission
        # (ASSURANCE / CONSEIL) : drf-spectacular les fusionne sous TypeMissionEnum.
        "StatutGabaritEnum": "apps.documents.models.StatutGabarit.choices",
        "StatutGenerationEnum": "apps.documents.models.StatutGeneration.choices",
        "StatutPdfEnum": "apps.documents.models.StatutPdf.choices",
        "PorteeNumerotationEnum": "apps.documents.models.PorteeNumerotation.choices",
        "FormatFichierEnum": "apps.documents.models.FormatFichier.choices",
        "TypeChampEnum": "apps.documents.serializers.TYPE_CHAMP_CHOICES",
        "TypeQuestionnaireEnum": "apps.analyse.models.TypeQuestionnaire.choices",
        "AppreciationEnum": "apps.analyse.models.Appreciation.choices",
        "TypologieProcessusEnum": "apps.analyse.models.TypologieProcessus.choices",
        "CategorieObjectifEnum": "apps.analyse.models.CategorieObjectif.choices",
        "RoleTacheEnum": "apps.analyse.models.RoleTache.choices",
        "ComposanteEnum": "apps.analyse.models.Composante.choices",
        "NatureControleEnum": "apps.analyse.models.NatureControle.choices",
        "EvaluationConceptionEnum": "apps.analyse.models.EvaluationConception.choices",
        "TypeForceFaiblesseEnum": "apps.analyse.models.TypeForceFaiblesse.choices",
        "TypeAvisEnum": "apps.analyse.models.TypeAvis.choices",
        "MotifNonTestEnum": "apps.analyse.models.MotifNonTest.choices",
        "CouvertureOrdreEnum": "apps.analyse.models.CouvertureOrdre.choices",
        "VarianteOrientationEnum": "apps.analyse.models.VarianteOrientation.choices",
        "StatutReferentielEnum": "apps.analyse.models.StatutReferentiel.choices",
        "NatureTestEnum": "apps.accomplissement.models.NatureTest.choices",
        "MethodeSelectionEnum": "apps.accomplissement.models.MethodeSelection.choices",
        "StatutTestEnum": "apps.accomplissement.models.StatutTest.choices",
        "StatutFicheEnum": "apps.accomplissement.models.StatutFiche.choices",
        "ConclusionTestEnum": "apps.accomplissement.models.ConclusionTest.choices",
        "TypeEvenementFicheEnum": "apps.accomplissement.models.TypeEvenementFiche.choices",
        "StatutConstatEnum": "apps.constats.models.StatutConstat.choices",
        "CategorieCauseEnum": "apps.constats.models.CategorieCause.choices",
        "PrioriteRecommandationEnum": "apps.constats.models.PrioriteRecommandation.choices",
        "PositionAuditeEnum": "apps.constats.models.PositionAudite.choices",
        "TypeEvenementConstatEnum": "apps.constats.models.TypeEvenementConstat.choices",
        "StatutActionEnum": "apps.recommandations.models.StatutAction.choices",
        "StatutRecommandationDeriveEnum": "apps.recommandations.serializers.STATUT_DERIVE_CHOICES",
        "EtatEngagementEnum": "apps.recommandations.serializers.ETAT_ENGAGEMENT_CHOICES",
        "StatutRapportEnum": "apps.communication.models.StatutRapport.choices",
        "AppreciationGlobaleEnum": "apps.communication.models.AppreciationGlobale.choices",
        "CategorieDestinataireEnum": "apps.communication.models.CategorieDestinataire.choices",
        "TypeEvenementRapportEnum": "apps.communication.models.TypeEvenementRapport.choices",
        "StatutSuiviEnum": "apps.suivi.models.StatutSuivi.choices",
        "StatutRecommandationSuiviEnum": "apps.suivi.models.StatutRecommandationSuivi.choices",
        "TypeEvenementSuiviEnum": "apps.suivi.models.TypeEvenementSuivi.choices",
        "StatutDemandeReportEnum": "apps.suivi.models.StatutDemandeReport.choices",
        "PalierRelanceEnum": "apps.suivi.models.PalierRelance.choices",
        "StatutRelanceEnum": "apps.suivi.models.StatutRelance.choices",
        "TypeNotificationEnum": "apps.notifications.models.TypeNotification.choices",
        "TypeResultatRechercheEnum": "apps.recherche.serializers.TYPES_RECHERCHE_CHOICES",
    },
}

# --- Templates: project-level templates (email/*) ---
TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]

# --- Celery (namespace CELERY; broker/backend are set from REDIS_URL above) ---
CELERY_TIMEZONE = "Africa/Ouagadougou"
# N2: the authentication emails have their own queue, served by a dedicated worker in
# production (`worker-auth`, docker/compose.prod.yml) and by the main worker as a fallback:
# a login code (10 min) must not wait behind a document conversion (up to 8 min).
CELERY_FILE_AUTHENTIFICATION = "auth"
CELERY_TASK_ROUTES = {
    nom: {"queue": CELERY_FILE_AUTHENTIFICATION}
    for nom in (
        "users.envoyer_code_connexion",
        "users.envoyer_code_reinitialisation",
        "users.envoyer_mot_de_passe_temporaire",
    )
}
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULE = {
    "heartbeat": {
        "task": "core.tasks.heartbeat",
        "schedule": crontab(hour=6, minute=0),
    },
    "pouls-beat": {
        "task": "core.tasks.pouls_beat",
        "schedule": crontab(minute="*"),
    },
    "documents-balayage": {
        "task": "documents.balayer_generations_bloquees",
        "schedule": crontab(minute="*/10"),
    },
    "suivi-reconciliation": {
        "task": "suivi.reconcilier_suivis",
        "schedule": crontab(minute=5),
    },
    "recherche-reconciliation": {
        "task": "recherche.reconcilier",
        "schedule": crontab(hour=2, minute=0),
    },
    "users-purge-codes": {
        "task": "users.purger_codes",
        "schedule": crontab(hour=3, minute=30),
    },
    "users-purge-sessions": {
        "task": "users.purger_sessions",
        "schedule": crontab(hour=3, minute=45),
    },
}

# --- Relances automatiques du suivi des recommandations (lot 8) ---
RELANCES_ACTIVES: bool = env.bool("RELANCES_ACTIVES", default=True)
RELANCES_MAX_EMAILS_PAR_EXECUTION: int = env.int("RELANCES_MAX_EMAILS_PAR_EXECUTION", default=200)
RELANCES_TENTATIVES_MAX = 5
# Base des liens des e-mails (sans barre finale) ; https:// exigé en production.
PLATEFORME_URL: str = env("PLATEFORME_URL", default="http://localhost:5173").rstrip("/")
CELERY_BEAT_SCHEDULE["suivi-relances"] = {
    "task": "suivi.relances_quotidiennes",
    "schedule": crontab(hour=7, minute=0),
}

# --- Email: EMAIL_URL = smtp://mailpit:1025 in compose, smtp://localhost:1025 on host ---
_email = env.email_url("EMAIL_URL", default="smtp://mailpit:1025")
EMAIL_BACKEND = _email["EMAIL_BACKEND"]
EMAIL_HOST = _email.get("EMAIL_HOST", "")
EMAIL_PORT = _email.get("EMAIL_PORT", 25)
EMAIL_HOST_USER = _email.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_secret("EMAIL_PASSWORD", default="") or _email.get(
    "EMAIL_HOST_PASSWORD", ""
)
EMAIL_USE_TLS = _email.get("EMAIL_USE_TLS", False)
# Seconds before an SMTP connection or send gives up (no timeout by default: a server that
# stops answering would block a request, e.g. the welcome emails of a CSV import, forever).
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = "audit-interne@onea.bf"

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# --- T5: cookies, cache. Sessions in the database (no Redis needed to log in). ---
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
# Absolute maximum (not sliding, see SessionLimiteeMiddleware) and idle timeout.
SESSION_COOKIE_AGE = 8 * 3600
SESSION_INACTIVITE_SECONDES = 30 * 60
CSRF_COOKIE_SAMESITE = "Lax"


def _cache_url() -> str:
    explicit: str = env("CACHE_URL", default="")
    url = explicit or REDIS_URL
    parts = urlsplit(url)
    if parts.scheme not in {"redis", "rediss", "unix"}:
        raise ImproperlyConfigured(
            "CACHE_URL / REDIS_URL must be a redis://, rediss:// or unix:// URL"
        )
    if explicit:
        return explicit
    return urlunsplit(parts._replace(path="/1"))  # same Redis, database 1 (0 is Celery's)


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _cache_url(),
        "KEY_PREFIX": "onea",
        "OPTIONS": {"socket_connect_timeout": 1, "socket_timeout": 1},
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"masquage": {"()": "apps.core.journalisation.MasquageFiltre"}},
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "plain",
            "filters": ["masquage"],
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": [], "level": "ERROR", "propagate": True},
    },
}

# --- T13: protected metrics endpoint (empty token = endpoint disabled, always 404) ---
METRICS_TOKEN: str = env_secret("METRICS_TOKEN", default="")

# --- Lot 7 bis : signature électronique PAdES (pyHanko). Désactivée tant que le certificat n'est
# pas fourni : le mode « Confirmation horodatée » reste alors le seul disponible.
# Certificat de l'ONEA : fichier PKCS#12 (hors dépôt, volume ou secret Docker) + phrase secrète.
SIGNATURE_PKCS12_FILE: str = env("SIGNATURE_PKCS12_FILE", default="")
SIGNATURE_PKCS12_PASSPHRASE: str = env_secret("SIGNATURE_PKCS12_PASSPHRASE", default="")
# Ancres de confiance (PEM : autorité de certification de l'ONEA). Vide = le certificat de
# signature lui-même (certificat autosigné de dev ou cachet serveur sans PKI).
SIGNATURE_ANCRES_CONFIANCE: str = env("SIGNATURE_ANCRES_CONFIANCE", default="")
# Serveur d'horodatage RFC 3161 interne (optionnel) : niveau PAdES B-T ; vide = B-B.
SIGNATURE_TSA_URL: str = env("SIGNATURE_TSA_URL", default="")
SIGNATURE_ELECTRONIQUE_ACTIVE: bool = bool(SIGNATURE_PKCS12_FILE)

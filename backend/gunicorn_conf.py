"""Gunicorn: JSON error log (same format as the application), access log off (nginx has it)."""

accesslog = None
errorlog = "-"
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "apps.core.journalisation.FormateurJson"}},
    "filters": {"masquage": {"()": "apps.core.journalisation.MasquageFiltre"}},
    "handlers": {
        "error_console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "json",
            "filters": ["masquage"],
        },
    },
    "root": {"handlers": [], "level": "INFO"},
    "loggers": {
        "gunicorn.error": {"handlers": ["error_console"], "level": "INFO", "propagate": False},
        "gunicorn.access": {"handlers": [], "level": "INFO", "propagate": False},
    },
}

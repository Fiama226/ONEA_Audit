# Single source of the API version (health endpoint, OpenAPI schema); mirrors pyproject.toml.
# Defined before the Celery import so settings can import it without a circular import.
__version__ = "0.1.0"

from .celery import app as celery_app  # noqa: E402

__all__ = ("__version__", "celery_app")

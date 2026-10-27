from .celery import app as celery_app

__all__ = ("__version__", "celery_app")

# Single source of the API version (health endpoint, OpenAPI schema); mirrors pyproject.toml.
__version__ = "0.1.0"

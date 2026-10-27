from typing import Any, cast

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context
from django.template.backends.django import Template as DjangoTemplate
from django.template.loader import get_template, render_to_string

SUBJECT_PREFIX = "[ONEA Audit] "


def _render_text(name: str, context: dict[str, Any]) -> str:
    """Render a plain-text template without HTML autoescaping."""
    backend_template = get_template(name)
    django_template = cast(DjangoTemplate, backend_template)
    return django_template.template.render(Context(context, autoescape=False))


def send_mail_template(to: list[str], subject: str, template: str, context: dict[str, Any]) -> None:
    """Render email/<template>.txt and .html and send them as one multipart message."""
    text = _render_text(f"email/{template}.txt", context)
    html = render_to_string(f"email/{template}.html", context)
    message = EmailMultiAlternatives(
        subject=f"{SUBJECT_PREFIX}{subject}",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    message.attach_alternative(html, "text/html")
    message.send()

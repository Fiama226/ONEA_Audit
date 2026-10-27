from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

SUBJECT_PREFIX = "[ONEA Audit] "


def send_mail_template(to: list[str], subject: str, template: str, context: dict[str, Any]) -> None:
    """Render email/<template>.txt and .html and send them as one multipart message."""
    text = render_to_string(f"email/{template}.txt", context)
    html = render_to_string(f"email/{template}.html", context)
    message = EmailMultiAlternatives(
        subject=f"{SUBJECT_PREFIX}{subject}",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    message.attach_alternative(html, "text/html")
    message.send()

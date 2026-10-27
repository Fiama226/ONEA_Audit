from typing import Any

import pytest
from django.core import mail
from django.core.mail import BadHeaderError, EmailMultiAlternatives

from apps.core.mail import send_mail_template
from apps.core.tasks import heartbeat, send_mail_task

CONTEXT = {"name": "Awa", "message": "Bonjour depuis les tests."}


def test_send_mail_template_builds_text_and_html() -> None:
    send_mail_template(["a@onea.bf"], "Test", "test", CONTEXT)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert isinstance(msg, EmailMultiAlternatives)
    assert msg.subject == "[ONEA Audit] Test"
    assert msg.to == ["a@onea.bf"]
    assert msg.from_email == "audit-interne@onea.bf"
    assert "Awa" in msg.body
    assert "Message automatique, ne pas répondre." in msg.body
    html, mimetype = msg.alternatives[0][:2]
    assert mimetype == "text/html"
    assert isinstance(html, str)
    assert "Awa" in html
    assert "Message automatique, ne pas répondre." in html


def test_send_mail_task_eager_sends() -> None:
    send_mail_task.delay(["b@onea.bf"], "Tâche", "test", CONTEXT)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "[ONEA Audit] Tâche"


def test_beat_schedule_has_daily_heartbeat(settings: Any) -> None:
    entry = settings.CELERY_BEAT_SCHEDULE["heartbeat"]
    assert entry["task"] == "core.tasks.heartbeat"
    assert entry["schedule"].hour == {6}
    assert entry["schedule"].minute == {0}


def test_heartbeat_logs_one_line(caplog: Any) -> None:
    with caplog.at_level("INFO"):
        heartbeat()
    assert [r.getMessage() for r in caplog.records if r.name == "apps.core.tasks"] == [
        "celery beat heartbeat"
    ]


def test_text_body_is_not_escaped_but_html_is() -> None:
    send_mail_template(["a@onea.bf"], "Test", "test", {"name": "O'Brien & fils", "message": "x"})

    msg = mail.outbox[0]
    assert isinstance(msg, EmailMultiAlternatives)
    assert "O'Brien & fils" in msg.body
    assert "&amp;" not in msg.body
    html = msg.alternatives[0][0]
    assert isinstance(html, str)
    assert "O&#x27;Brien &amp; fils" in html


def test_subject_with_newline_is_rejected() -> None:
    with pytest.raises(BadHeaderError):
        send_mail_template(["a@onea.bf"], "Test\nBcc: x@evil.com", "test", CONTEXT)
    assert mail.outbox == []

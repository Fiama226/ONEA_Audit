from django.core import mail

from apps.core.mail import send_mail_template


def test_send_mail_template_cc(db: None) -> None:
    send_mail_template(["a@onea.bf"], "Sujet", "test", {"name": "A"}, cc=["chef@onea.bf"])
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["a@onea.bf"]
    assert mail.outbox[0].cc == ["chef@onea.bf"]


def test_send_mail_template_sans_cc_retrocompatible(db: None) -> None:
    send_mail_template(["a@onea.bf"], "Sujet", "test", {"name": "A"})
    assert mail.outbox[0].cc == []

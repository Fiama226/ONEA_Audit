from auditlog.models import LogEntry

from apps.users.models import User


def test_user_changes_are_audited_without_password(user: User) -> None:
    user.fonction = "Chef de mission"
    user.save()
    entries = LogEntry.objects.get_for_object(user)
    assert entries.count() >= 2
    for e in entries:
        assert "password" not in e.changes_dict

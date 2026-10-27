from typing import Any

from auditlog.models import LogEntry
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

ACTION_NAMES: dict[int, str] = {
    LogEntry.Action.CREATE: "create",
    LogEntry.Action.UPDATE: "update",
    LogEntry.Action.DELETE: "delete",
    LogEntry.Action.ACCESS: "access",
}


class AuditActorSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    username = serializers.CharField()


class AuditLogSerializer(serializers.Serializer[LogEntry]):
    """Read-only representation of an auditlog entry."""

    id = serializers.IntegerField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    actor = AuditActorSerializer(read_only=True, allow_null=True)
    action = serializers.SerializerMethodField()
    model = serializers.SerializerMethodField()
    object_id = serializers.CharField(source="object_pk", read_only=True)
    object_repr = serializers.CharField(read_only=True)
    changes = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ChoiceField(choices=["create", "update", "delete", "access"]))
    def get_action(self, obj: LogEntry) -> str:
        return ACTION_NAMES[obj.action]

    @extend_schema_field(serializers.CharField(help_text="app_label.model, e.g. users.user"))
    def get_model(self, obj: LogEntry) -> str:
        return f"{obj.content_type.app_label}.{obj.content_type.model}"

    @extend_schema_field(
        serializers.DictField(
            child=serializers.ListField(),
            help_text="{field: [before, after]}; empty for deletions.",
        )
    )
    def get_changes(self, obj: LogEntry) -> dict[str, Any]:
        return obj.changes if isinstance(obj.changes, dict) else {}

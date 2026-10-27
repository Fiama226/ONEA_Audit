import logging
from typing import Any

from auditlog.models import LogEntry
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

logger = logging.getLogger(__name__)

CHANGES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Per field: [before, after] (values are strings as stored by django-auditlog; on "
        "creation before is the string 'None', on deletion after is the string 'None'), or an "
        "m2m object, or {'raw': value} for an unexpected stored shape."
    ),
    "additionalProperties": {
        "oneOf": [
            {"type": "array", "items": {}, "minItems": 2, "maxItems": 2},
            {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["m2m"]},
                    "operation": {"type": "string"},
                    "objects": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["type", "operation", "objects"],
            },
            {"type": "object", "properties": {"raw": {}}, "required": ["raw"]},
        ]
    },
}

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

    @extend_schema_field(
        serializers.ChoiceField(choices=["create", "update", "delete", "access", "unknown"])
    )
    def get_action(self, obj: LogEntry) -> str:
        return ACTION_NAMES.get(obj.action, "unknown")

    @extend_schema_field(serializers.CharField(help_text="app_label.model, e.g. users.user"))
    def get_model(self, obj: LogEntry) -> str:
        return f"{obj.content_type.app_label}.{obj.content_type.model}"

    @extend_schema_field(CHANGES_SCHEMA)
    def get_changes(self, obj: LogEntry) -> dict[str, Any]:
        raw = obj.changes_dict
        if not isinstance(raw, dict):
            logger.warning("Unexpected audit changes payload on entry %s", obj.pk)
            return {"raw": raw}
        out: dict[str, Any] = {}
        for field, value in raw.items():
            if isinstance(value, list | tuple) or (
                isinstance(value, dict) and value.get("type") == "m2m"
            ):
                out[field] = value
            else:
                logger.warning("Unexpected audit change shape on entry %s (%s)", obj.pk, field)
                out[field] = {"raw": value}
        return out

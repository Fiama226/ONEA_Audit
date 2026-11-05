import logging
from typing import Any

from auditlog.models import LogEntry
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.users.models import Role, User

from .parametres import ContenuJournal, contenu_journal

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


MASQUE = "[masqué]"
# Entités hors mission, toujours lisibles par l'ADMIN (comptes, référentiel, réglages).
APPS_HORS_MISSION = {"users", "referentiel", "auth"}
MODELES_HORS_MISSION = {
    "signatures.parametresignature",
    "core.parametreplateforme",
    "gouvernance.reglegouvernance",
}


def masquer_pour(request: Any, entree: LogEntry, mode: str | None = None) -> bool:
    """Vrai si l'ADMIN (et non le RAI) consulte une entité de mission en mode « masqué »."""
    user = getattr(request, "user", None)
    if not isinstance(user, User) or user.has_role(Role.RAI) or not user.has_role(Role.ADMIN):
        return False
    ct = entree.content_type
    if ct.app_label in APPS_HORS_MISSION or f"{ct.app_label}.{ct.model}" in MODELES_HORS_MISSION:
        return False
    return (mode or contenu_journal()) == ContenuJournal.MASQUE


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
    action_metier = serializers.SerializerMethodField()
    motif = serializers.SerializerMethodField()
    affaiblissement = serializers.SerializerMethodField()

    @extend_schema_field(
        serializers.ChoiceField(choices=["create", "update", "delete", "access", "unknown"])
    )
    def get_action(self, obj: LogEntry) -> str:
        return ACTION_NAMES.get(obj.action, "unknown")

    @extend_schema_field(serializers.CharField(help_text="app_label.model, e.g. users.user"))
    def get_model(self, obj: LogEntry) -> str:
        return f"{obj.content_type.app_label}.{obj.content_type.model}"

    def _masque(self, obj: LogEntry) -> bool:
        """Mode « masqué » (SEC-02) : l'ADMIN ne lit pas le contenu des entités de mission."""
        if not hasattr(self, "_mode"):  # une lecture par requête, pas par entrée
            self._mode = contenu_journal()
        return masquer_pour(self.context.get("request"), obj, self._mode)

    def to_representation(self, instance: LogEntry) -> dict[str, Any]:
        data = super().to_representation(instance)
        if self._masque(instance):
            data["object_repr"] = MASQUE
        return data

    @extend_schema_field(
        serializers.CharField(
            allow_null=True,
            help_text=(
                "Business action named by the service that wrote the entry "
                "(additional_data.action), e.g. creation_compte, reinitialisation_mot_de_passe, "
                "changement_mot_de_passe, reinitialisation_par_code, activation_otp; "
                "null when none."
            ),
        )
    )
    def get_action_metier(self, obj: LogEntry) -> str | None:
        if self._masque(obj):
            return None
        donnees = obj.additional_data
        action = donnees.get("action") if isinstance(donnees, dict) else None
        return action if isinstance(action, str) else None

    def _donnee(self, obj: LogEntry, cle: str) -> object:
        if self._masque(obj):
            return None
        donnees = obj.additional_data
        return donnees.get(cle) if isinstance(donnees, dict) else None

    @extend_schema_field(
        serializers.CharField(
            allow_null=True,
            help_text="Motif saisi avec le changement (règles de gouvernance) ; null sinon.",
        )
    )
    def get_motif(self, obj: LogEntry) -> str | None:
        motif = self._donnee(obj, "motif")
        return motif if isinstance(motif, str) and motif else None

    @extend_schema_field(
        serializers.BooleanField(
            allow_null=True,
            help_text="Vrai si le changement a assoupli un contrôle (règles de gouvernance).",
        )
    )
    def get_affaiblissement(self, obj: LogEntry) -> bool | None:
        valeur = self._donnee(obj, "affaiblissement")
        return valeur if isinstance(valeur, bool) else None

    @extend_schema_field(CHANGES_SCHEMA)
    def get_changes(self, obj: LogEntry) -> dict[str, Any]:
        raw = obj.changes_dict
        if self._masque(obj):
            return {champ: [MASQUE, MASQUE] for champ in raw} if isinstance(raw, dict) else {}
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


class ParametreJournalModifieParSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    nom_complet = serializers.SerializerMethodField()

    def get_nom_complet(self, obj: User) -> str:
        return obj.get_full_name() or obj.username


class ParametreJournalSerializer(serializers.Serializer[dict[str, Any]]):
    """Réglage `journal_audit_contenu_missions`."""

    valeur = serializers.ChoiceField(choices=list(ContenuJournal.VALEURS))
    valeur_libelle = serializers.CharField()
    modifie_le = serializers.DateTimeField(allow_null=True)
    modifie_par = ParametreJournalModifieParSerializer(allow_null=True)


class ParametreJournalEcritureSerializer(serializers.Serializer[dict[str, str]]):
    valeur = serializers.ChoiceField(choices=list(ContenuJournal.VALEURS))

"""Sérialiseurs de l'API des notifications (lecture seule : l'état de lecture change par action)."""

from rest_framework import serializers

from .models import Notification, TypeNotification


class NotificationSerializer(serializers.ModelSerializer[Notification]):
    type = serializers.ChoiceField(choices=TypeNotification.choices, read_only=True)
    lue = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "type", "titre", "message", "lien", "lue", "lue_le", "created_at")
        read_only_fields = fields

    def get_lue(self, obj: Notification) -> bool:
        return obj.lue_le is not None


class CompteSerializer(serializers.Serializer[dict[str, int]]):
    count = serializers.IntegerField(min_value=0)

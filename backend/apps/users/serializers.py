from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "direction_code",
            "fonction",
        )
        read_only_fields = fields

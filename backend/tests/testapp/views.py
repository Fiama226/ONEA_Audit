from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.exceptions import RegleMetierError

from .models import Exemple


class AdresseSerializer(serializers.Serializer[dict[str, str]]):
    ville = serializers.CharField()


class ItemSerializer(serializers.Serializer[dict[str, str]]):
    nom = serializers.CharField()


class PayloadSerializer(serializers.Serializer[dict[str, object]]):
    adresse = AdresseSerializer()
    items = ItemSerializer(many=True, required=False)


@api_view(["GET"])
@permission_classes([AllowAny])
def regle_metier(request: Request) -> Response:
    raise RegleMetierError("Montant négatif interdit.", {"montant": ["Doit être positif."]})


@api_view(["GET"])
@permission_classes([AllowAny])
def regle_metier_simple(request: Request) -> Response:
    raise RegleMetierError("Transition interdite.")


@api_view(["POST"])
@permission_classes([AllowAny])
def validation(request: Request) -> Response:
    serializer = PayloadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([AllowAny])
def validation_plate(request: Request) -> Response:
    raise serializers.ValidationError("Incohérent.")


@api_view(["GET"])
@permission_classes([AllowAny])
def exemple_detail(request: Request, pk: str) -> Response:
    obj = get_object_or_404(Exemple.objects, pk=pk)
    return Response({"nom": obj.nom})


@api_view(["GET"])
@permission_classes([AllowAny])
def interdit(request: Request) -> Response:
    raise PermissionDenied


@api_view(["GET"])
@permission_classes([AllowAny])
def interdit_drf(request: Request) -> Response:
    raise DRFPermissionDenied

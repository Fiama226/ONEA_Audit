"""Sérialiseurs de l'API du suivi.

Les noms des classes (sans le suffixe `Serializer`) sont les noms des composants OpenAPI. Les
droits affichés (`actions_possibles`) viennent de `droits.py`, dont le contexte est calculé UNE
FOIS par page (clé `contexte_suivi` du contexte du sérialiseur, posée par la vue).
"""

from datetime import date
from typing import Any, cast

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.constats.models import Constat, PrioriteRecommandation, Recommandation
from apps.missions.models import Mission, StatutMission
from apps.referentiel.models import Direction
from apps.users.models import User
from apps.users.serializers import UtilisateurResumeSerializer

from . import droits
from .models import (
    DemandeReport,
    EvenementSuivi,
    PreuveMiseEnOeuvre,
    StatutDemandeReport,
    StatutRecommandationSuivi,
    StatutSuivi,
    SuiviAction,
    TypeEvenementSuivi,
)
from .services import commun


def _acteur(serializer: serializers.BaseSerializer[Any]) -> User:
    return cast(User, serializer.context["request"].user)


def _contexte(serializer: serializers.BaseSerializer[Any], mission_id: Any) -> droits.ContexteSuivi:
    """Contexte de la page (posé par la vue) ; à défaut, celui de la seule mission demandée."""
    contexte: droits.ContexteSuivi | None = serializer.context.get("contexte_suivi")
    if contexte is not None and mission_id in contexte.statuts_mission:
        return contexte
    return droits.contexte_suivi(_acteur(serializer), [mission_id])


def _aujourd_hui(serializer: serializers.BaseSerializer[Any]) -> date:
    contexte = cast(dict[str, Any], serializer.context)
    if "aujourd_hui" not in contexte:
        contexte["aujourd_hui"] = timezone.localdate()
    return cast(date, contexte["aujourd_hui"])


class MissionSuiviSerializer(serializers.ModelSerializer[Mission]):
    statut = serializers.ChoiceField(choices=StatutMission.choices, read_only=True)

    class Meta:
        model = Mission
        fields = ("id", "reference", "titre", "statut")
        read_only_fields = fields


class ConstatSuiviSerializer(serializers.ModelSerializer[Constat]):
    class Meta:
        model = Constat
        fields = ("id", "reference", "titre")
        read_only_fields = fields


class RecommandationResumeSerializer(serializers.ModelSerializer[Recommandation]):
    priorite = serializers.ChoiceField(choices=PrioriteRecommandation.choices, read_only=True)

    class Meta:
        model = Recommandation
        fields = ("id", "libelle", "priorite")
        read_only_fields = fields


class EntiteSuiviSerializer(serializers.ModelSerializer[Direction]):
    class Meta:
        model = Direction
        fields = ("id", "code", "libelle")
        read_only_fields = fields


# --------------------------------------------------------------------------- demandes de report


class DemandeReportSerializer(serializers.ModelSerializer[DemandeReport]):
    action = serializers.PrimaryKeyRelatedField[SuiviAction](source="suivi", read_only=True)
    statut = serializers.ChoiceField(choices=StatutDemandeReport.choices, read_only=True)
    demandee_par = UtilisateurResumeSerializer(read_only=True)
    decidee_par = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = DemandeReport
        fields = (
            "id",
            "action",
            "echeance_actuelle",
            "nouvelle_echeance",
            "motif",
            "statut",
            "demandee_par",
            "decidee_par",
            "decidee_le",
            "commentaire_decision",
            "actions_possibles",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: DemandeReport) -> list[str]:
        return droits.actions_demande(obj, _acteur(self), contexte=_contexte(self, obj.mission_id))


class DemandeReportListeSerializer(DemandeReportSerializer):
    """Ligne du journal des reports : ajoute la mission et l'action pour l'écran dédié du RAI."""

    mission_id = serializers.UUIDField(read_only=True)
    mission_reference = serializers.CharField(source="mission.reference", read_only=True)
    action_libelle = serializers.CharField(source="suivi.action.libelle", read_only=True)

    class Meta(DemandeReportSerializer.Meta):
        fields = (  # type: ignore[assignment]
            *DemandeReportSerializer.Meta.fields,
            "mission_id",
            "mission_reference",
            "action_libelle",
        )
        read_only_fields = fields  # type: ignore[assignment]


class DemandeReportRequestSerializer(serializers.Serializer[Any]):
    action = serializers.PrimaryKeyRelatedField(queryset=SuiviAction.objects.all())
    nouvelle_echeance = serializers.DateField()
    motif = serializers.CharField(max_length=4000)


class DecisionReportSerializer(serializers.Serializer[Any]):
    commentaire = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=4000
    )


# --------------------------------------------------------------------------- actions


class SuiviActionSerializer(serializers.ModelSerializer[SuiviAction]):
    mission = MissionSuiviSerializer(read_only=True)
    constat = ConstatSuiviSerializer(source="recommandation.constat", read_only=True)
    recommandation = RecommandationResumeSerializer(read_only=True)
    entite = EntiteSuiviSerializer(read_only=True)
    action_libelle = serializers.CharField(source="action.libelle", read_only=True)
    indicateur = serializers.CharField(source="action.indicateur", read_only=True)
    responsable = UtilisateurResumeSerializer(read_only=True)
    statut = serializers.ChoiceField(choices=StatutSuivi.choices, read_only=True)
    en_retard = serializers.SerializerMethodField()
    jours_retard = serializers.SerializerMethodField()
    declaree_par = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    verifiee_par = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    cloturee_par = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    nombre_preuves = serializers.IntegerField(read_only=True)
    demande_report_en_attente = serializers.SerializerMethodField()
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = SuiviAction
        fields = (
            "id",
            "mission",
            "constat",
            "recommandation",
            "entite",
            "action_libelle",
            "indicateur",
            "responsable",
            "echeance_initiale",
            "echeance",
            "nombre_reports",
            "statut",
            "en_retard",
            "jours_retard",
            "declaree_par",
            "declaree_le",
            "verifiee_par",
            "verifiee_le",
            "cloturee_par",
            "cloturee_le",
            "justification_abandon",
            "motif_dernier_rejet",
            "nombre_preuves",
            "demande_report_en_attente",
            "derniere_activite_le",
            "actions_possibles",
        )
        read_only_fields = fields

    def get_en_retard(self, obj: SuiviAction) -> bool:
        return commun.en_retard(obj, _aujourd_hui(self))

    def get_jours_retard(self, obj: SuiviAction) -> int | None:
        return commun.jours_retard(obj, _aujourd_hui(self))

    @extend_schema_field(DemandeReportSerializer(allow_null=True))
    def get_demande_report_en_attente(self, obj: SuiviAction) -> Any:
        en_attente = getattr(obj, "report_en_attente", [])
        if not en_attente:
            return None
        return DemandeReportSerializer(en_attente[0], context=self.context).data

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: SuiviAction) -> list[str]:
        return droits.actions_possibles(
            obj, _acteur(self), contexte=_contexte(self, obj.mission_id)
        )


class EvenementActionSuiviSerializer(serializers.ModelSerializer[EvenementSuivi]):
    type = serializers.ChoiceField(choices=TypeEvenementSuivi.choices, read_only=True)
    par = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    pour_compte_de = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    statut_avant = serializers.CharField(read_only=True)
    statut_apres = serializers.CharField(read_only=True)

    class Meta:
        model = EvenementSuivi
        fields = (
            "id",
            "type",
            "par",
            "pour_compte_de",
            "le",
            "statut_avant",
            "statut_apres",
            "texte",
        )
        read_only_fields = fields


class ResponsableRequestSerializer(serializers.Serializer[Any]):
    responsable = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class CommentaireRequestSerializer(serializers.Serializer[Any]):
    """Commentaire facultatif (obligatoire pour le RAI qui agit pour le compte du responsable)."""

    commentaire = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=4000
    )


class CommentaireObligatoireRequestSerializer(serializers.Serializer[Any]):
    commentaire = serializers.CharField(max_length=4000)


class MotifSuiviRequestSerializer(serializers.Serializer[Any]):
    motif = serializers.CharField(max_length=4000)


class JustificationRequestSerializer(serializers.Serializer[Any]):
    justification = serializers.CharField(max_length=4000)


class TexteRequestSerializer(serializers.Serializer[Any]):
    texte = serializers.CharField(max_length=4000)


# --------------------------------------------------------------------------- registre


class RecommandationSuiviSerializer(serializers.ModelSerializer[Recommandation]):
    mission = MissionSuiviSerializer(read_only=True)
    constat = ConstatSuiviSerializer(read_only=True)
    entite = EntiteSuiviSerializer(source="constat.entite", read_only=True)
    priorite = serializers.ChoiceField(choices=PrioriteRecommandation.choices, read_only=True)
    statut_suivi = serializers.ChoiceField(
        choices=StatutRecommandationSuivi.choices, read_only=True
    )
    risque_accepte = serializers.SerializerMethodField()
    actions_total = serializers.IntegerField(read_only=True)
    actions_closes = serializers.IntegerField(read_only=True)
    actions_en_retard = serializers.IntegerField(read_only=True)
    prochaine_echeance = serializers.DateField(read_only=True, allow_null=True)

    class Meta:
        model = Recommandation
        fields = (
            "id",
            "mission",
            "constat",
            "entite",
            "libelle",
            "priorite",
            "statut_suivi",
            "risque_accepte",
            "actions_total",
            "actions_closes",
            "actions_en_retard",
            "prochaine_echeance",
        )
        read_only_fields = fields

    def get_risque_accepte(self, obj: Recommandation) -> bool:
        return bool(getattr(obj, "nb_acceptations", 0))


# --------------------------------------------------------------------------- preuves


class PreuveSerializer(serializers.ModelSerializer[PreuveMiseEnOeuvre]):
    deposee_par = UtilisateurResumeSerializer(read_only=True)
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = PreuveMiseEnOeuvre
        fields = (
            "id",
            "numero",
            "libelle",
            "description",
            "nom_fichier_original",
            "taille_octets",
            "type_mime",
            "empreinte_sha256",
            "deposee_par",
            "deposee_le",
            "actions_possibles",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: PreuveMiseEnOeuvre) -> list[str]:
        return droits.actions_preuve(obj, _acteur(self), contexte=_contexte(self, obj.mission_id))


class DepotPreuveSerializer(serializers.Serializer[Any]):
    """Dépôt d'une preuve (multipart/form-data) ; le fichier n'est lu que par le service."""

    action = serializers.PrimaryKeyRelatedField(
        queryset=SuiviAction.objects.all(),
        required=False,
        help_text="Facultatif si `?action=` est fourni dans l'URL (recommandé).",
    )
    libelle = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    fichier = serializers.FileField()
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")


class ModifierPreuveSerializer(serializers.Serializer[Any]):
    libelle = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)


# --------------------------------------------------------------------------- missions


class MissionACloturerSerializer(serializers.ModelSerializer[Mission]):
    statut = serializers.ChoiceField(choices=StatutMission.choices, read_only=True)
    actions_total = serializers.IntegerField(read_only=True)
    actions_closes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Mission
        fields = ("id", "reference", "titre", "statut", "annee", "actions_total", "actions_closes")
        read_only_fields = fields

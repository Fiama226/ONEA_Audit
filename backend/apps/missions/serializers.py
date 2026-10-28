"""Sérialiseurs de l'API des missions.

Les noms des classes (sans le suffixe `Serializer`) sont les noms des composants OpenAPI
consommés par le frontend. Les droits affichés (`mes_droits`, `actions_possibles`) viennent des
services ; rien n'est recalculé ici. La liste des étapes reçoit un `contexte_actions` construit
une seule fois par la vue (clé `contexte_actions` du contexte du sérialiseur).
"""

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any, cast

from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.relations import ManyRelatedField

from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    NiveauRisque,
    Processus,
    Risque,
)
from apps.referentiel.serializers import (
    CelluleMatriceSerializer,
    DirectionResumeSerializer,
    ParNiveauSerializer,
)
from apps.signatures.models import Confirmation, TypeDocumentSignable
from apps.signatures.serializers import ConfirmationResumeSerializer
from apps.users.models import Role, User
from apps.users.serializers import UtilisateurResumeSerializer

from .gardes import STATUTS_ETAPE_CLOSE
from .models import (
    AffectationMission,
    DeclarationIndependance,
    Entretien,
    EtapeMission,
    EvenementDeclencheur,
    EvenementEtape,
    Mission,
    Phase,
    Reunion,
    RisqueMission,
    RoleMission,
    StatutDeclaration,
    StatutEntretien,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
    TypeMission,
    TypeReunion,
)
from .services import declarations as svc_declarations
from .services import droits as svc_droits
from .services import etapes as svc_etapes
from .services.etapes import ActionEtape, ContexteActions
from .services.livrables import livrables_manquants

# --------------------------------------------------------------------------- champs communs


class _ManyIndexe(ManyRelatedField):
    """Liste de clés : l'erreur d'un élément est posée sur son rang (`processus.0`)."""

    def to_internal_value(self, data: Any) -> list[Any]:
        if isinstance(data, str) or not hasattr(data, "__iter__"):
            self.fail("not_a_list", input_type=type(data).__name__)
        if not self.allow_empty and len(data) == 0:
            self.fail("empty")
        valeurs: list[Any] = []
        erreurs: dict[int, Any] = {}
        for rang, element in enumerate(data):
            try:
                valeurs.append(self.child_relation.to_internal_value(element))
            except ValidationError as e:
                erreurs[rang] = e.detail
        if erreurs:
            raise ValidationError(cast(Any, erreurs))
        return valeurs


class CleRelation(serializers.PrimaryKeyRelatedField):  # type: ignore[type-arg]
    """Clé primaire dont l'identifiant UUID est validé avant la requête (jamais de 500)."""

    def __init__(self, **kwargs: Any) -> None:
        queryset = kwargs.get("queryset")
        if (
            queryset is not None
            and "pk_field" not in kwargs
            and queryset.model._meta.pk.get_internal_type() == "UUIDField"
        ):
            kwargs["pk_field"] = serializers.UUIDField()
        super().__init__(**kwargs)

    @classmethod
    def many_init(cls, *args: Any, **kwargs: Any) -> ManyRelatedField:
        enfant = cls(*args, **kwargs)
        options = {
            cle: kwargs[cle]
            for cle in ("read_only", "write_only", "required", "allow_empty", "help_text")
            if cle in kwargs
        }
        return _ManyIndexe(child_relation=enfant, **options)


def _nom_complet(user: User) -> str:
    return user.get_full_name() or user.username


def _role_de(serializer: serializers.BaseSerializer[Any]) -> str | None:
    request = serializer.context.get("request")
    return cast("str | None", getattr(getattr(request, "user", None), "role", None))


def _est_audite(serializer: serializers.BaseSerializer[Any]) -> bool:
    return _role_de(serializer) == Role.AUDITE


class ResumeSerializer(serializers.Serializer[Any]):
    """{id, code, libelle} d'un processus ou d'une entité."""

    id = serializers.UUIDField()
    code = serializers.CharField()
    libelle = serializers.CharField()


class MissionResumeSerializer(serializers.ModelSerializer[Mission]):
    class Meta:
        model = Mission
        fields = ("id", "reference", "titre")
        read_only_fields = fields


class CartographieResumeSerializer(serializers.ModelSerializer[CartographieVersion]):
    class Meta:
        model = CartographieVersion
        fields = ("id", "annee")
        read_only_fields = fields


class EtapeCouranteSerializer(serializers.Serializer[Any]):
    numero = serializers.IntegerField()
    romain = serializers.CharField()


class DroitsMissionSerializer(serializers.Serializer[svc_droits.DroitsMission]):
    modifier = serializers.BooleanField()
    planifier = serializers.BooleanField()
    lancer = serializers.BooleanField()
    emettre_ordre = serializers.BooleanField()
    suspendre = serializers.BooleanField()
    reprendre = serializers.BooleanField()
    annuler = serializers.BooleanField()
    supprimer = serializers.BooleanField()
    affecter = serializers.BooleanField()
    contribuer = serializers.BooleanField()
    voir_travaux = serializers.BooleanField()
    confirmer_ma_declaration = serializers.BooleanField()


def _dernier_ordre(mission: Mission) -> Confirmation | None:
    return (
        Confirmation.objects.filter(
            content_type=ContentType.objects.get_for_model(Mission),
            object_id=mission.pk,
            type_document=TypeDocumentSignable.ORDRE_MISSION,
        )
        .select_related("signataire")
        .order_by("-confirme_le", "-pk")
        .first()
    )


# --------------------------------------------------------------------------- équipe


class DeclarationResumeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    statut = serializers.ChoiceField(choices=StatutDeclaration.choices)
    levee = serializers.BooleanField()
    confirmee_le = serializers.DateTimeField(allow_null=True)


class AffectationSerializer(serializers.ModelSerializer[AffectationMission]):
    mission = CleRelation(queryset=Mission.objects.all())
    utilisateur = CleRelation(queryset=User.objects.filter(is_active=True))
    utilisateur_detail = UtilisateurResumeSerializer(source="utilisateur", read_only=True)
    role_mission = serializers.ChoiceField(choices=RoleMission.choices)
    declaration = serializers.SerializerMethodField()

    class Meta:
        model = AffectationMission
        fields = (
            "id",
            "mission",
            "utilisateur",
            "utilisateur_detail",
            "role_mission",
            "declaration",
        )
        read_only_fields = ("id",)

    @extend_schema_field(DeclarationResumeSerializer(allow_null=True))
    def get_declaration(self, obj: AffectationMission) -> dict[str, Any] | None:
        if _est_audite(self):
            return None
        declaration = getattr(obj, "declaration", None)
        if declaration is None or declaration.deleted_at is not None:
            return None
        confirmee_le = getattr(obj, "declaration_confirmee_le", None)
        return {
            "id": declaration.pk,
            "statut": declaration.statut,
            "levee": declaration.levee,
            "confirmee_le": confirmee_le,
        }


# --------------------------------------------------------------------------- missions


class MissionListeSerializer(serializers.ModelSerializer[Mission]):
    type = serializers.ChoiceField(choices=TypeMission.choices, read_only=True)
    statut = serializers.ChoiceField(choices=StatutMission.choices, read_only=True)
    phase = serializers.ChoiceField(choices=Phase.choices, read_only=True, allow_null=True)
    chef_mission = serializers.SerializerMethodField()
    etape_courante = serializers.SerializerMethodField()
    ma_declaration_en_attente = serializers.SerializerMethodField()

    class Meta:
        model = Mission
        fields = (
            "id",
            "reference",
            "titre",
            "type",
            "statut",
            "phase",
            "chef_mission",
            "date_debut_prevue",
            "date_fin_prevue",
            "etape_courante",
            "ma_declaration_en_attente",
        )
        read_only_fields = fields

    @extend_schema_field(UtilisateurResumeSerializer(allow_null=True))
    def get_chef_mission(self, obj: Mission) -> dict[str, Any] | None:
        for affectation in obj.affectations.all():
            if affectation.role_mission == RoleMission.CHEF_MISSION:
                return dict(UtilisateurResumeSerializer(affectation.utilisateur).data)
        return None

    @extend_schema_field(EtapeCouranteSerializer(allow_null=True))
    def get_etape_courante(self, obj: Mission) -> dict[str, Any] | None:
        if _est_audite(self):
            return None
        en_cours: Sequence[EtapeMission] = getattr(obj, "etapes_en_cours", None) or []
        if not en_cours:
            return None
        premiere = min(en_cours, key=lambda e: e.numero)
        return {"numero": premiere.numero, "romain": premiere.definition.romain}

    def get_ma_declaration_en_attente(self, obj: Mission) -> bool:
        user = self.context["request"].user
        return any(
            a.utilisateur_id == user.pk
            and getattr(a, "declaration", None) is not None
            and a.declaration.statut == StatutDeclaration.EN_ATTENTE
            for a in obj.affectations.all()
        )


class MissionSerializer(MissionListeSerializer):
    evenement_declencheur = serializers.ChoiceField(
        choices=EvenementDeclencheur.choices, required=False, allow_blank=True
    )
    type = serializers.ChoiceField(choices=TypeMission.choices)
    processus = CleRelation(
        many=True, queryset=Processus.objects.all(), required=False, write_only=True
    )
    processus_detail = serializers.SerializerMethodField()
    entites = CleRelation(
        many=True, queryset=Direction.objects.all(), required=False, write_only=True
    )
    entites_detail = serializers.SerializerMethodField()
    budget_jours = serializers.DecimalField(
        max_digits=6, decimal_places=1, min_value=0, required=False, allow_null=True
    )
    cartographie = CartographieResumeSerializer(read_only=True, allow_null=True)
    statut_avant_suspension = serializers.ChoiceField(
        choices=StatutMission.choices, read_only=True, allow_blank=True
    )
    motif_suspension = serializers.CharField(read_only=True)
    motif_annulation = serializers.CharField(read_only=True, allow_null=True)
    ordre_mission = serializers.SerializerMethodField()
    equipe = AffectationSerializer(source="affectations", many=True, read_only=True)
    mes_droits = serializers.SerializerMethodField()

    class Meta:
        model = Mission
        fields = (
            "id",
            "reference",
            "titre",
            "type",
            "statut",
            "phase",
            "chef_mission",
            "date_debut_prevue",
            "date_fin_prevue",
            "etape_courante",
            "ma_declaration_en_attente",
            "processus",
            "processus_detail",
            "entites",
            "entites_detail",
            "evenement_declencheur",
            "evenement_precision",
            "periode_debut",
            "periode_fin",
            "budget_jours",
            "objectifs",
            "perimetre",
            "exclusions",
            "clients",
            "livrables_attendus",
            "cartographie",
            "statut_avant_suspension",
            "motif_suspension",
            "motif_annulation",
            "ordre_mission",
            "ordre_mission_emis_le",
            "equipe",
            "mes_droits",
            "created_at",
        )
        read_only_fields = (
            "id",
            "reference",
            "statut",
            "phase",
            "chef_mission",
            "etape_courante",
            "ma_declaration_en_attente",
            "ordre_mission_emis_le",
            "created_at",
        )

    def validate_budget_jours(self, value: Any) -> Any:
        if value is None:
            return Decimal("0.0")  # nul = aucun budget, comme à la création
        return value

    @extend_schema_field(ResumeSerializer(many=True))
    def get_processus_detail(self, obj: Mission) -> list[dict[str, Any]]:
        return [
            {"id": p.pk, "code": p.code, "libelle": p.libelle}
            for p in sorted(obj.processus.all(), key=lambda p: (p.ordre, p.code))
        ]

    @extend_schema_field(ResumeSerializer(many=True))
    def get_entites_detail(self, obj: Mission) -> list[dict[str, Any]]:
        return [
            dict(DirectionResumeSerializer(d).data)
            for d in sorted(obj.entites.all(), key=lambda d: d.code)
        ]

    @extend_schema_field(ConfirmationResumeSerializer(allow_null=True))
    def get_ordre_mission(self, obj: Mission) -> dict[str, Any] | None:
        confirmation = _dernier_ordre(obj)
        return dict(ConfirmationResumeSerializer(confirmation).data) if confirmation else None

    @extend_schema_field(DroitsMissionSerializer)
    def get_mes_droits(self, obj: Mission) -> dict[str, Any]:
        droits = svc_droits.droits_mission(self.context["request"].user, obj)
        return dict(DroitsMissionSerializer(droits).data)

    def to_representation(self, instance: Mission) -> dict[str, Any]:
        data: dict[str, Any] = dict(super().to_representation(instance))
        if _est_audite(self):
            # Champs internes : jamais communiqués à l'audité.
            data["budget_jours"] = None
            data["cartographie"] = None
            data["motif_annulation"] = None
        return data


class RemplacerChefSerializer(serializers.Serializer[Any]):
    utilisateur = CleRelation(queryset=User.objects.filter(is_active=True))


class MotifSerializer(serializers.Serializer[Any]):
    motif = serializers.CharField(min_length=1, max_length=2000)


class ConfirmationSerializer(serializers.Serializer[Any]):
    confirme = serializers.BooleanField(
        help_text="Doit être vrai : la confirmation explicite de l'utilisateur."
    )
    conflit = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Déclaration d'indépendance seulement : une situation est à signaler.",
    )
    description_conflit = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=4000,
        help_text="Déclaration d'indépendance seulement : description de la situation.",
    )

    def validate_confirme(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("Vous devez confirmer explicitement.")
        return value


class ArbitrageSerializer(serializers.Serializer[Any]):
    justification = serializers.CharField(min_length=1, max_length=4000)


# --------------------------------------------------------------------------- déclarations


class _ListeDeclarations(serializers.ListSerializer[Any]):
    """Charge en lot les confirmations et les entités de la page (pas de N+1)."""

    def to_representation(self, data: Any) -> list[Any]:
        declarations: list[DeclarationIndependance] = list(data)
        precharger_declarations(declarations)
        enfant = cast(serializers.BaseSerializer[Any], self.child)
        return [enfant.to_representation(d) for d in declarations]


def precharger_declarations(declarations: Iterable[DeclarationIndependance]) -> None:
    liste = list(declarations)
    if not liste:
        return
    confirmations: dict[Any, Confirmation] = {}
    for confirmation in (
        Confirmation.objects.filter(
            content_type=ContentType.objects.get_for_model(DeclarationIndependance),
            object_id__in=[d.pk for d in liste],
            type_document=TypeDocumentSignable.DECLARATION_INDEPENDANCE,
        )
        .select_related("signataire")
        .order_by("-confirme_le", "-pk")
    ):
        confirmations.setdefault(confirmation.object_id, confirmation)
    missions = {d.affectation.mission_id for d in liste}
    entites: dict[Any, list[str]] = {pk: [] for pk in missions}
    for mission_id, libelle in (
        Direction.objects.filter(missions__in=missions)
        .values_list("missions", "libelle")
        .order_by("code")
    ):
        entites[mission_id].append(libelle)
    for declaration in liste:
        declaration._confirmation = confirmations.get(declaration.pk)  # type: ignore[attr-defined]
        declaration._entites = ", ".join(  # type: ignore[attr-defined]
            entites[declaration.affectation.mission_id]
        )


class DeclarationSerializer(serializers.ModelSerializer[DeclarationIndependance]):
    mission = serializers.UUIDField(source="affectation.mission_id", read_only=True)
    mission_reference = serializers.CharField(
        source="affectation.mission.reference", read_only=True
    )
    mission_titre = serializers.CharField(source="affectation.mission.titre", read_only=True)
    utilisateur_detail = UtilisateurResumeSerializer(
        source="affectation.utilisateur", read_only=True
    )
    role_mission = serializers.ChoiceField(
        choices=RoleMission.choices, source="affectation.role_mission", read_only=True
    )
    statut = serializers.ChoiceField(choices=StatutDeclaration.choices, read_only=True)
    levee = serializers.BooleanField(read_only=True)
    texte = serializers.SerializerMethodField()
    confirmation = serializers.SerializerMethodField()
    arbitre_par = UtilisateurResumeSerializer(read_only=True, allow_null=True)

    class Meta:
        model = DeclarationIndependance
        fields = (
            "id",
            "affectation",
            "mission",
            "mission_reference",
            "mission_titre",
            "utilisateur_detail",
            "role_mission",
            "statut",
            "levee",
            "texte",
            "description_conflit",
            "confirmation",
            "arbitrage_justification",
            "arbitre_par",
            "arbitre_le",
        )
        read_only_fields = fields
        list_serializer_class = _ListeDeclarations

    def get_texte(self, obj: DeclarationIndependance) -> str:
        entites = getattr(obj, "_entites", None)
        return svc_declarations.texte_declaration(obj, libelles_entites=entites)

    @extend_schema_field(ConfirmationResumeSerializer(allow_null=True))
    def get_confirmation(self, obj: DeclarationIndependance) -> dict[str, Any] | None:
        if hasattr(obj, "_confirmation"):
            confirmation = obj._confirmation
        else:
            confirmation = svc_declarations.confirmation_de(obj)
        return dict(ConfirmationResumeSerializer(confirmation).data) if confirmation else None


# --------------------------------------------------------------------------- étapes


class EvenementSerializer(serializers.ModelSerializer[EvenementEtape]):
    type = serializers.ChoiceField(choices=TypeEvenementEtape.choices, read_only=True)
    par = UtilisateurResumeSerializer(read_only=True)
    statut_avant = serializers.ChoiceField(choices=StatutEtape.choices, read_only=True)
    statut_apres = serializers.ChoiceField(choices=StatutEtape.choices, read_only=True)

    class Meta:
        model = EvenementEtape
        fields: tuple[str, ...] = (
            "type",
            "par",
            "le",
            "motif",
            "statut_avant",
            "statut_apres",
        )
        read_only_fields: tuple[str, ...] = fields


class EvenementSuiviSerializer(EvenementSerializer):
    etape_romain = serializers.CharField(source="etape.definition.romain", read_only=True)

    class Meta(EvenementSerializer.Meta):
        fields = (*EvenementSerializer.Meta.fields, "etape_romain")
        read_only_fields = fields


class EtapeSerializer(serializers.ModelSerializer[EtapeMission]):
    romain = serializers.CharField(source="definition.romain", read_only=True)
    titre = serializers.CharField(source="definition.titre", read_only=True)
    phase = serializers.ChoiceField(
        choices=Phase.choices, source="definition.phase", read_only=True
    )
    jalon = serializers.BooleanField(source="definition.jalon", read_only=True)
    objectif = serializers.CharField(source="definition.objectif", read_only=True)
    livrables = serializers.ListField(
        child=serializers.CharField(), source="definition.livrables", read_only=True
    )
    acteurs = serializers.CharField(source="definition.acteurs", read_only=True)
    statut = serializers.ChoiceField(choices=StatutEtape.choices, read_only=True)
    terminee_par = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    validee_par = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    actions_possibles = serializers.SerializerMethodField()
    livrables_manquants = serializers.SerializerMethodField()
    evenements = serializers.SerializerMethodField()

    class Meta:
        model = EtapeMission
        fields = (
            "id",
            "mission",
            "numero",
            "romain",
            "titre",
            "phase",
            "jalon",
            "objectif",
            "livrables",
            "acteurs",
            "statut",
            "date_debut_prevue",
            "date_fin_prevue",
            "date_debut_reelle",
            "date_fin_reelle",
            "charge_prevue_jours",
            "charge_reelle_jours",
            "terminee_par",
            "validee_par",
            "validee_le",
            "motif_non_applicable",
            "actions_possibles",
            "livrables_manquants",
            "evenements",
        )
        read_only_fields = (
            "id",
            "mission",
            "numero",
            "validee_le",
            "motif_non_applicable",
            "date_debut_reelle",
            "date_fin_reelle",
        )

    def _detail(self) -> bool:
        return bool(self.context.get("detail"))

    @extend_schema_field(
        serializers.ListField(child=serializers.ChoiceField(choices=ActionEtape.choices))
    )
    def get_actions_possibles(self, obj: EtapeMission) -> list[str]:
        user = self.context["request"].user
        contexte: ContexteActions | None = self.context.get("contexte_actions")
        return svc_etapes.actions_possibles(obj, user, contexte=contexte)

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_livrables_manquants(self, obj: EtapeMission) -> list[str]:
        return livrables_manquants(obj) if self._detail() else []

    @extend_schema_field(EvenementSerializer(many=True))
    def get_evenements(self, obj: EtapeMission) -> list[dict[str, Any]]:
        if not self._detail():
            return []
        return [dict(EvenementSerializer(e).data) for e in obj.evenements.all()]


# --------------------------------------------------------------------------- fiche de suivi


class LigneSuiviSerializer(serializers.Serializer[Any]):
    numero = serializers.IntegerField()
    romain = serializers.CharField()
    titre = serializers.CharField()
    phase = serializers.ChoiceField(choices=Phase.choices)
    jalon = serializers.BooleanField()
    statut = serializers.ChoiceField(choices=StatutEtape.choices)
    debut_prevu = serializers.DateField(allow_null=True)
    fin_prevue = serializers.DateField(allow_null=True)
    debut_reel = serializers.DateField(allow_null=True)
    fin_reelle = serializers.DateField(allow_null=True)
    ecart_jours = serializers.IntegerField(
        allow_null=True, help_text="Positif = retard, négatif = avance."
    )
    charge_prevue = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)
    charge_reelle = serializers.DecimalField(max_digits=5, decimal_places=1, allow_null=True)


class FicheSuiviSerializer(serializers.Serializer[Any]):
    mission = MissionResumeSerializer()
    budget_jours = serializers.DecimalField(max_digits=6, decimal_places=1)
    total_prevu = serializers.DecimalField(max_digits=7, decimal_places=1)
    total_reel = serializers.DecimalField(max_digits=7, decimal_places=1)
    lignes = LigneSuiviSerializer(many=True)
    evenements = EvenementSuiviSerializer(many=True)


# --------------------------------------------------------------------------- réunions


class ReunionSerializer(serializers.ModelSerializer[Reunion]):
    mission = CleRelation(queryset=Mission.objects.all())
    type = serializers.ChoiceField(choices=TypeReunion.choices)
    participants = CleRelation(
        many=True, queryset=User.objects.filter(is_active=True), required=False
    )
    participants_detail = UtilisateurResumeSerializer(
        source="participants", many=True, read_only=True
    )
    etape_close = serializers.SerializerMethodField()

    class Meta:
        model = Reunion
        fields = (
            "id",
            "mission",
            "type",
            "date",
            "lieu",
            "ordre_du_jour",
            "participants",
            "participants_detail",
            "participants_externes",
            "decisions",
            "compte_rendu",
            "tenue_le",
            "etape_close",
        )
        read_only_fields = ("id", "tenue_le")

    def get_etape_close(self, obj: Reunion) -> bool:
        return getattr(obj, "etape_statut", None) in STATUTS_ETAPE_CLOSE


# --------------------------------------------------------------------------- entretiens


class EntretienSerializer(serializers.ModelSerializer[Entretien]):
    mission = CleRelation(queryset=Mission.objects.all())
    etape = CleRelation(queryset=EtapeMission.objects.all(), required=False, allow_null=True)
    etape_romain = serializers.SerializerMethodField()
    auditeurs = CleRelation(many=True, queryset=User.objects.filter(is_active=True), required=False)
    auditeurs_detail = UtilisateurResumeSerializer(source="auditeurs", many=True, read_only=True)
    interlocuteurs = CleRelation(
        many=True, queryset=User.objects.filter(is_active=True), required=False
    )
    interlocuteurs_detail = UtilisateurResumeSerializer(
        source="interlocuteurs", many=True, read_only=True
    )
    statut = serializers.ChoiceField(choices=StatutEntretien.choices, read_only=True)
    etape_close = serializers.SerializerMethodField()

    class Meta:
        model = Entretien
        fields = (
            "id",
            "mission",
            "etape",
            "etape_romain",
            "objet",
            "date_prevue",
            "duree_minutes",
            "lieu",
            "auditeurs",
            "auditeurs_detail",
            "interlocuteurs",
            "interlocuteurs_detail",
            "autres_interlocuteurs",
            "themes",
            "compte_rendu",
            "note_synthese",
            "statut",
            "realise_le",
            "motif_annulation",
            "etape_close",
        )
        read_only_fields = ("id", "realise_le", "motif_annulation")

    def get_etape_romain(self, obj: Entretien) -> str | None:
        return obj.etape.definition.romain if obj.etape is not None else None

    def get_etape_close(self, obj: Entretien) -> bool:
        return obj.etape is not None and obj.etape.statut in STATUTS_ETAPE_CLOSE

    def to_representation(self, instance: Entretien) -> dict[str, Any]:
        data: dict[str, Any] = dict(super().to_representation(instance))
        if _est_audite(self):
            # Notes internes de l'équipe d'audit : jamais communiquées à l'audité.
            data["compte_rendu"] = ""
            data["note_synthese"] = ""
        return data


# --------------------------------------------------------------------------- risques


class RisqueMissionSerializer(serializers.ModelSerializer[RisqueMission]):
    mission = CleRelation(queryset=Mission.objects.all())
    mission_reference = serializers.CharField(source="mission.reference", read_only=True)
    risque_source = CleRelation(queryset=Risque.objects.all(), required=False, allow_null=True)
    code_source = serializers.CharField(read_only=True)
    nouveau = serializers.BooleanField(read_only=True)
    processus = CleRelation(queryset=Processus.objects.all(), required=False)
    processus_code = serializers.CharField(source="processus.code", read_only=True)
    libelle = serializers.CharField(required=False, allow_blank=True, max_length=500)
    probabilite = serializers.IntegerField(min_value=1, max_value=5, required=False)
    impact = serializers.IntegerField(min_value=1, max_value=5, required=False)
    score = serializers.IntegerField(read_only=True)
    niveau = serializers.ChoiceField(choices=NiveauRisque.choices, read_only=True)
    probabilite_reference = serializers.SerializerMethodField()
    impact_reference = serializers.SerializerMethodField()

    class Meta:
        model = RisqueMission
        fields = (
            "id",
            "mission",
            "mission_reference",
            "risque_source",
            "code_source",
            "nouveau",
            "processus",
            "processus_code",
            "libelle",
            "description",
            "probabilite",
            "impact",
            "score",
            "niveau",
            "commentaire",
            "probabilite_reference",
            "impact_reference",
        )
        read_only_fields = ("id",)

    def get_probabilite_reference(self, obj: RisqueMission) -> int | None:
        return obj.risque_source.probabilite if obj.risque_source is not None else None

    def get_impact_reference(self, obj: RisqueMission) -> int | None:
        return obj.risque_source.impact if obj.risque_source is not None else None


class MatriceMissionSerializer(serializers.Serializer[Any]):
    mission = serializers.UUIDField()
    total = serializers.IntegerField()
    par_niveau = ParNiveauSerializer()
    cellules = CelluleMatriceSerializer(many=True)

from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from django.conf import settings
from django.db import models
from django.db.models import Case, CharField, F, Q, Value, When
from django.db.models.lookups import GreaterThanOrEqual
from django.utils import timezone
from django_fsm import FSMField, transition

from apps.core.exceptions import RegleMetierError
from apps.core.models import BaseModel
from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    NiveauRisque,
    Processus,
    Risque,
)
from apps.referentiel.scoring import SEUIL_ELEVE, SEUIL_MOYEN

from .managers import (
    EvenementAllManager,
    EvenementManager,
    MissionAllManager,
    MissionEnfantAllManager,
    MissionEnfantManager,
    MissionManager,
)
from .signals import etape_changee

if TYPE_CHECKING:
    from apps.users.models import User

    from .etapes import DefinitionEtape


class TypeMission(models.TextChoices):
    ASSURANCE = "ASSURANCE", "Assurance"
    CONSEIL = "CONSEIL", "Conseil"


class StatutMission(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    PLANIFIEE = "PLANIFIEE", "Planifiée"
    EN_PLANIFICATION = "EN_PLANIFICATION", "En planification"
    EN_ACCOMPLISSEMENT = "EN_ACCOMPLISSEMENT", "En accomplissement"
    EN_COMMUNICATION = "EN_COMMUNICATION", "En communication"
    RAPPORT_DIFFUSE = "RAPPORT_DIFFUSE", "Rapport diffusé"
    EN_SUIVI = "EN_SUIVI", "En suivi"
    CLOTUREE = "CLOTUREE", "Clôturée"
    SUSPENDUE = "SUSPENDUE", "Suspendue"
    ANNULEE = "ANNULEE", "Annulée"


class EvenementDeclencheur(models.TextChoices):
    PROGRAMME_ANNUEL = "PROGRAMME_ANNUEL", "Mission inscrite au programme annuel"
    DEMANDE_MANAGEMENT = "DEMANDE_MANAGEMENT", "Demande du management"
    CHANGEMENT_MAJEUR = "CHANGEMENT_MAJEUR", "Changement majeur interne ou externe"
    EXIGENCE_REGLEMENTAIRE = "EXIGENCE_REGLEMENTAIRE", "Exigence réglementaire"
    AUTRE = "AUTRE", "Autre"


class RoleMission(models.TextChoices):
    CHEF_MISSION = "CHEF_MISSION", "Chef de mission"
    AUDITEUR = "AUDITEUR", "Auditeur"
    SUPERVISEUR = "SUPERVISEUR", "Superviseur"
    AUDITE = "AUDITE", "Audité"


class Phase(models.TextChoices):
    PLANIFICATION = "PLANIFICATION", "Planification"
    ACCOMPLISSEMENT = "ACCOMPLISSEMENT", "Accomplissement"
    COMMUNICATION = "COMMUNICATION", "Communication"


class StatutEtape(models.TextChoices):
    A_FAIRE = "A_FAIRE", "À faire"
    EN_COURS = "EN_COURS", "En cours"
    TERMINEE = "TERMINEE", "Terminée"
    VALIDEE = "VALIDEE", "Validée"
    RENVOYEE = "RENVOYEE", "Renvoyée"
    A_REVALIDER = "A_REVALIDER", "À revalider"
    NON_APPLICABLE = "NON_APPLICABLE", "Non applicable"


class TypeEvenementEtape(models.TextChoices):
    DEMARREE = "DEMARREE", "Démarrée"
    TERMINEE = "TERMINEE", "Terminée"
    VALIDEE = "VALIDEE", "Validée"
    RENVOYEE = "RENVOYEE", "Renvoyée"
    ROUVERTE = "ROUVERTE", "Rouverte"
    A_REVALIDER = "A_REVALIDER", "Marquée à revalider"
    NON_APPLICABLE = "NON_APPLICABLE", "Marquée non applicable"
    RETABLIE = "RETABLIE", "Rétablie"
    DEROGATION = "DEROGATION", "Dérogation (réponse de l'audité)"


class StatutDeclaration(models.TextChoices):
    EN_ATTENTE = "EN_ATTENTE", "En attente"
    CONFIRMEE = "CONFIRMEE", "Confirmée"
    CONFLIT_DECLARE = "CONFLIT_DECLARE", "Situation déclarée"


class TypeReunion(models.TextChoices):
    OUVERTURE = "OUVERTURE", "Réunion d'ouverture"
    LANCEMENT = "LANCEMENT", "Réunion de lancement"
    CLOTURE = "CLOTURE", "Réunion de clôture"


class StatutEntretien(models.TextChoices):
    PLANIFIE = "PLANIFIE", "Planifié"
    REALISE = "REALISE", "Réalisé"
    ANNULE = "ANNULE", "Annulé"


ROLES_INTERVENANTS = (RoleMission.CHEF_MISSION, RoleMission.AUDITEUR, RoleMission.SUPERVISEUR)


class Mission(BaseModel):
    reference = models.CharField("référence", max_length=20, blank=True)
    annee = models.PositiveSmallIntegerField("année", null=True, blank=True)
    numero = models.PositiveSmallIntegerField("numéro", null=True, blank=True)
    titre = models.CharField("titre", max_length=300)
    type = models.CharField("type", max_length=16, choices=TypeMission.choices)
    statut = FSMField(  # type: ignore[no-untyped-call]  # django-fsm is untyped
        "statut",
        default=StatutMission.BROUILLON,
        choices=StatutMission.choices,
        protected=False,
    )
    statut_avant_suspension = models.CharField(
        "statut avant suspension", max_length=24, choices=StatutMission.choices, blank=True
    )
    motif_suspension = models.TextField("motif de suspension", blank=True)
    motif_annulation = models.TextField("motif d'annulation", blank=True)
    processus = models.ManyToManyField(
        Processus, verbose_name="processus", blank=True, related_name="missions"
    )
    entites = models.ManyToManyField(
        Direction, verbose_name="entités auditées", blank=True, related_name="missions"
    )
    risques_couverts = models.ManyToManyField(
        "referentiel.Risque",
        verbose_name="risques couverts",
        blank=True,
        related_name="missions_couvrantes",
        help_text=(
            "Risques de la cartographie de référence que la mission couvre (règle de "
            "gouvernance « lien programme ↔ risque »)."
        ),
    )
    evenement_declencheur = models.CharField(
        "événement déclencheur",
        max_length=24,
        choices=EvenementDeclencheur.choices,
        blank=True,
    )
    evenement_precision = models.TextField("précision sur l'événement", blank=True)
    periode_debut = models.DateField("début de la période auditée", null=True, blank=True)
    periode_fin = models.DateField("fin de la période auditée", null=True, blank=True)
    date_debut_prevue = models.DateField("début prévu", null=True, blank=True)
    date_fin_prevue = models.DateField("fin prévue", null=True, blank=True)
    budget_jours = models.DecimalField("budget (jours)", max_digits=6, decimal_places=1, default=0)
    objectifs = models.TextField("objectifs", blank=True)
    perimetre = models.TextField("périmètre", blank=True)
    exclusions = models.TextField("exclusions", blank=True)
    clients = models.TextField("clients de la mission", blank=True)
    livrables_attendus = models.TextField("livrables attendus", blank=True)
    cartographie = models.ForeignKey(
        CartographieVersion,
        verbose_name="cartographie de référence",
        on_delete=models.PROTECT,
        related_name="missions",
    )
    ordre_mission_emis_le = models.DateTimeField("ordre de mission émis le", null=True, blank=True)

    objects: ClassVar[MissionManager] = MissionManager()
    all_objects: ClassVar[MissionAllManager] = MissionAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "mission"
        verbose_name_plural = "missions"
        ordering = ("-created_at",)
        constraints = [
            # La référence n'est jamais réutilisée : unicité y compris pour les supprimées.
            models.UniqueConstraint(
                fields=["reference"],
                condition=~Q(reference=""),
                name="mission_reference_unique",
            ),
            models.UniqueConstraint(
                fields=["annee", "numero"],
                condition=Q(numero__isnull=False),
                name="mission_annee_numero_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(date_debut_prevue__isnull=True)
                    | Q(date_fin_prevue__isnull=True)
                    | Q(date_fin_prevue__gte=F("date_debut_prevue"))
                ),
                name="mission_dates_prevues_ordonnees",
            ),
            models.CheckConstraint(
                condition=(
                    Q(periode_debut__isnull=True)
                    | Q(periode_fin__isnull=True)
                    | Q(periode_fin__gte=F("periode_debut"))
                ),
                name="mission_periode_ordonnee",
            ),
            models.CheckConstraint(condition=Q(budget_jours__gte=0), name="mission_budget_positif"),
            models.CheckConstraint(
                condition=Q(numero__isnull=True) | Q(annee__isnull=False),
                name="mission_numero_avec_annee",
            ),
            models.CheckConstraint(
                condition=Q(statut=StatutMission.BROUILLON) | ~Q(reference=""),
                name="mission_reference_hors_brouillon",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reference or 'Brouillon'} - {self.titre}"

    @property
    def phase(self) -> Phase | None:
        from .etapes import PHASE_DU_STATUT

        return PHASE_DU_STATUT.get(self.statut)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            from . import gardes

            gardes.controler_sauvegarde_mission(self, kwargs.get("update_fields"))
        super().save(*args, **kwargs)


class MissionEnfantModel(BaseModel):
    """Objet rattaché à une mission : refuse l'écriture si la mission est figée.

    Les sous-classes surchargent `exiger_travaux_ouverts` quand une étape gèle leurs travaux.
    """

    objects: ClassVar[MissionEnfantManager[Any]] = MissionEnfantManager()
    all_objects: ClassVar[MissionEnfantAllManager[Any]] = MissionEnfantAllManager()  # noqa: DJ012

    class Meta:
        abstract = True

    mission_id: UUID

    def exiger_travaux_ouverts(self) -> None:
        """Refuse (EtapeCloseError) si l'étape qui gèle cet objet est close."""

    def save(self, *args: Any, **kwargs: Any) -> None:
        from . import gardes

        gardes.controler_sauvegarde(self)
        super().save(*args, **kwargs)


class AffectationMission(MissionEnfantModel):
    mission = models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name="affectations", verbose_name="mission"
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="affectations_mission",
        verbose_name="utilisateur",
    )
    role_mission = models.CharField(
        "rôle dans la mission", max_length=16, choices=RoleMission.choices
    )
    responsable_entite = models.BooleanField(
        "responsable de l'entité",
        default=False,
        help_text=(
            "Audité habilité à engager sa direction (acceptation de risque, réponse au "
            "rapport provisoire). Au plus un par direction et par mission (contrôlé par le "
            "service d'équipe : la direction vient du compte, pas de l'affectation)."
        ),
    )
    alerte_objectivite = models.TextField(
        "alerte d'objectivité",
        blank=True,
        help_text=(
            "Situation détectée par le contrôle d'objectivité (Normes IIA 2.2) quand la règle "
            "de gouvernance est en mode avertissement ; vide sinon."
        ),
    )

    class Meta:
        verbose_name = "affectation"
        verbose_name_plural = "affectations"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "utilisateur"],
                condition=Q(deleted_at__isnull=True),
                name="affectation_utilisateur_unique_actif",
            ),
            models.UniqueConstraint(
                fields=["mission"],
                condition=Q(deleted_at__isnull=True, role_mission=RoleMission.CHEF_MISSION),
                name="affectation_chef_unique_actif",
            ),
            models.UniqueConstraint(
                fields=["mission"],
                condition=Q(deleted_at__isnull=True, role_mission=RoleMission.SUPERVISEUR),
                name="affectation_superviseur_unique_actif",
            ),
            models.CheckConstraint(
                condition=Q(responsable_entite=False) | Q(role_mission=RoleMission.AUDITE),
                name="affectation_responsable_entite_audite",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.utilisateur} ({self.get_role_mission_display()})"


class DeclarationIndependance(MissionEnfantModel):
    affectation = models.OneToOneField(
        AffectationMission,
        on_delete=models.PROTECT,
        related_name="declaration",
        verbose_name="affectation",
    )
    statut = models.CharField(
        "statut",
        max_length=16,
        choices=StatutDeclaration.choices,
        default=StatutDeclaration.EN_ATTENTE,
    )
    description_conflit = models.TextField("situation déclarée", blank=True)
    arbitrage_justification = models.TextField("justification de l'arbitrage", blank=True)
    arbitre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="arbitré par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    arbitre_le = models.DateTimeField("arbitré le", null=True, blank=True)

    class Meta:
        verbose_name = "déclaration d'indépendance"
        verbose_name_plural = "déclarations d'indépendance"
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(statut=StatutDeclaration.CONFLIT_DECLARE) | ~Q(description_conflit=""),
                name="declaration_conflit_decrit",
            ),
            models.CheckConstraint(
                condition=(
                    Q(statut=StatutDeclaration.CONFLIT_DECLARE)
                    | (
                        Q(arbitrage_justification="")
                        & Q(arbitre_le__isnull=True)
                        & Q(arbitre_par__isnull=True)
                    )
                ),
                name="declaration_arbitrage_sur_conflit",
            ),
        ]

    def __str__(self) -> str:
        return f"Déclaration de {self.affectation.utilisateur}"

    @property
    def mission_id(self) -> UUID:  # type: ignore[override]
        return self.affectation.mission_id

    @property
    def levee(self) -> bool:
        """Déclaration confirmée, ou situation déclarée puis arbitrée par le RAI."""
        return self.statut == StatutDeclaration.CONFIRMEE or (
            self.statut == StatutDeclaration.CONFLIT_DECLARE and self.arbitre_le is not None
        )


class EtapeMission(MissionEnfantModel):
    mission = models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name="etapes", verbose_name="mission"
    )
    numero = models.PositiveSmallIntegerField("numéro")
    statut = FSMField(  # type: ignore[no-untyped-call]  # django-fsm is untyped
        "statut",
        default=StatutEtape.A_FAIRE,
        choices=StatutEtape.choices,
        protected=False,
    )
    date_debut_prevue = models.DateField("début prévu", null=True, blank=True)
    date_fin_prevue = models.DateField("fin prévue", null=True, blank=True)
    date_debut_reelle = models.DateField("début réel", null=True, blank=True)
    date_fin_reelle = models.DateField("fin réelle", null=True, blank=True)
    charge_prevue_jours = models.DecimalField(
        "charge prévue (jours)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    charge_reelle_jours = models.DecimalField(
        "charge réelle (jours)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    terminee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="terminée par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validée par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    validee_le = models.DateTimeField("validée le", null=True, blank=True)
    motif_non_applicable = models.TextField("motif « non applicable »", blank=True)

    class Meta:
        verbose_name = "étape de mission"
        verbose_name_plural = "étapes de mission"
        ordering = ("numero",)
        constraints = [
            models.CheckConstraint(
                condition=Q(numero__gte=1, numero__lte=18), name="etape_numero_1_18"
            ),
            models.UniqueConstraint(
                fields=["mission", "numero"],
                condition=Q(deleted_at__isnull=True),
                name="etape_numero_unique_actif",
            ),
            models.CheckConstraint(
                condition=Q(charge_prevue_jours__isnull=True) | Q(charge_prevue_jours__gte=0),
                name="etape_charge_prevue_positive",
            ),
            models.CheckConstraint(
                condition=Q(charge_reelle_jours__isnull=True) | Q(charge_reelle_jours__gte=0),
                name="etape_charge_reelle_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Étape {self.definition.romain}"

    @property
    def definition(self) -> "DefinitionEtape":
        from .etapes import etape

        return etape(self.numero)

    # Transitions de D8 : appelées uniquement par les services (qui posent aussi les dates,
    # les auteurs et l'événement). `protected=False` : le champ reste modifiable par `update`.

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutEtape.A_FAIRE, target=StatutEtape.EN_COURS
    )
    def demarrer(self) -> None:
        """A_FAIRE -> EN_COURS."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=[StatutEtape.EN_COURS, StatutEtape.RENVOYEE],
        target=StatutEtape.TERMINEE,
    )
    def terminer(self) -> None:
        """EN_COURS ou RENVOYEE -> TERMINEE."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=[StatutEtape.TERMINEE, StatutEtape.A_REVALIDER],
        target=StatutEtape.VALIDEE,
    )
    def valider(self) -> None:
        """TERMINEE ou A_REVALIDER -> VALIDEE."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutEtape.TERMINEE, target=StatutEtape.RENVOYEE
    )
    def renvoyer(self) -> None:
        """TERMINEE -> RENVOYEE."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=[StatutEtape.TERMINEE, StatutEtape.VALIDEE, StatutEtape.A_REVALIDER],
        target=StatutEtape.EN_COURS,
    )
    def rouvrir(self) -> None:
        """TERMINEE, VALIDEE ou A_REVALIDER -> EN_COURS."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutEtape.VALIDEE, target=StatutEtape.A_REVALIDER
    )
    def a_revalider(self) -> None:
        """VALIDEE -> A_REVALIDER (réouverture d'une étape antérieure)."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=[StatutEtape.A_FAIRE, StatutEtape.EN_COURS],
        target=StatutEtape.NON_APPLICABLE,
    )
    def non_applicable(self) -> None:
        """A_FAIRE ou EN_COURS -> NON_APPLICABLE."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutEtape.NON_APPLICABLE, target=StatutEtape.A_FAIRE
    )
    def retablir(self) -> None:
        """NON_APPLICABLE -> A_FAIRE."""


class EvenementEtape(BaseModel):
    """Journal des transitions d'une étape : ajout seul."""

    etape = models.ForeignKey(
        EtapeMission, on_delete=models.PROTECT, related_name="evenements", verbose_name="étape"
    )
    type = models.CharField("type", max_length=16, choices=TypeEvenementEtape.choices)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="par"
    )
    le = models.DateTimeField("le", default=timezone.now)
    motif = models.TextField("motif", blank=True)
    statut_avant = models.CharField("statut avant", max_length=16, choices=StatutEtape.choices)
    statut_apres = models.CharField("statut après", max_length=16, choices=StatutEtape.choices)

    objects: ClassVar[EvenementManager[Any]] = EvenementManager()
    all_objects: ClassVar[EvenementAllManager[Any]] = EvenementAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "événement d'étape"
        verbose_name_plural = "événements d'étape"
        ordering = ("le", "created_at")

    def __str__(self) -> str:
        return f"{self.get_type_display()} ({self.le:%d/%m/%Y})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise RegleMetierError(
                "Un événement d'étape ne peut pas être modifié : le journal est en ajout seul."
            )
        super().save(*args, **kwargs)

    @classmethod
    def journaliser(
        cls,
        etape: EtapeMission,
        type: str,  # noqa: A002
        *,
        par: "User",
        motif: str = "",
        statut_avant: str,
    ) -> "EvenementEtape":
        """Écrit l'événement ; `statut_apres` est le statut courant de l'étape.

        Émet ensuite `signals.etape_changee` dans la transaction de l'appelant : une exception
        d'un récepteur annule la transition.
        """
        evenement: EvenementEtape = cls.objects.create(
            etape=etape,
            type=type,
            par=par,
            created_by=par,
            le=timezone.now(),
            motif=motif,
            statut_avant=statut_avant,
            statut_apres=etape.statut,
        )
        etape_changee.send(
            sender=EtapeMission,
            etape=etape,
            evenement=evenement,
            par=par,
            type_evenement=type,
            motif=motif,
            statut_avant=statut_avant,
        )
        return evenement


class Reunion(MissionEnfantModel):
    mission = models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name="reunions", verbose_name="mission"
    )
    type = models.CharField("type", max_length=16, choices=TypeReunion.choices)
    date = models.DateTimeField("date")
    lieu = models.CharField("lieu", max_length=200, blank=True)
    ordre_du_jour = models.TextField("ordre du jour", blank=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="participants", blank=True, related_name="+"
    )
    participants_externes = models.TextField("participants externes", blank=True)
    decisions = models.TextField("décisions", blank=True)
    compte_rendu = models.TextField("compte rendu", blank=True)
    tenue_le = models.DateTimeField("tenue le", null=True, blank=True)

    class Meta:
        verbose_name = "réunion"
        verbose_name_plural = "réunions"
        ordering = ("date",)
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "type"],
                condition=Q(deleted_at__isnull=True),
                name="reunion_type_unique_actif",
            ),
        ]

    def __str__(self) -> str:
        return self.get_type_display()

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes
        from .etapes import ETAPE_DE_REUNION

        numero = ETAPE_DE_REUNION.get(self.type)
        if numero is None:
            raise RegleMetierError(
                "Type de réunion inconnu.", {"type": ["Type de réunion inconnu."]}
            )
        gardes.exiger_etape_ouverte(self.mission_id, numero)


class Entretien(MissionEnfantModel):
    mission = models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name="entretiens", verbose_name="mission"
    )
    etape = models.ForeignKey(
        EtapeMission,
        verbose_name="étape rattachée",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="entretiens",
    )
    objet = models.CharField("objet", max_length=300)
    date_prevue = models.DateTimeField("date prévue")
    duree_minutes = models.PositiveSmallIntegerField("durée (minutes)", null=True, blank=True)
    lieu = models.CharField("lieu", max_length=200, blank=True)
    auditeurs = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="auditeurs", blank=True, related_name="+"
    )
    interlocuteurs = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="interlocuteurs", blank=True, related_name="+"
    )
    autres_interlocuteurs = models.TextField("autres interlocuteurs", blank=True)
    themes = models.TextField("thèmes", blank=True)
    compte_rendu = models.TextField("compte rendu", blank=True)
    note_synthese = models.TextField("note de synthèse", blank=True)
    statut = models.CharField(
        "statut", max_length=16, choices=StatutEntretien.choices, default=StatutEntretien.PLANIFIE
    )
    realise_le = models.DateTimeField("réalisé le", null=True, blank=True)
    motif_annulation = models.TextField("motif d'annulation", blank=True)

    class Meta:
        verbose_name = "entretien"
        verbose_name_plural = "entretiens"
        ordering = ("date_prevue",)
        constraints = [
            models.CheckConstraint(
                condition=Q(duree_minutes__isnull=True)
                | Q(duree_minutes__gte=1, duree_minutes__lte=600),
                name="entretien_duree_1_600",
            ),
        ]

    def __str__(self) -> str:
        return self.objet

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        etape_id: UUID | None = self.etape_id
        if etape_id is not None:
            gardes.exiger_etape_ouverte_par_id(etape_id)


_PRODUIT = F("probabilite") * F("impact")


class RisqueMission(MissionEnfantModel):
    mission = models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name="risques", verbose_name="mission"
    )
    risque_source = models.ForeignKey(
        Risque,
        verbose_name="risque de la cartographie",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    processus = models.ForeignKey(
        Processus, verbose_name="processus", on_delete=models.PROTECT, related_name="+"
    )
    code_source = models.CharField("code d'origine", max_length=32, blank=True)
    libelle = models.CharField("libellé", max_length=500)
    description = models.TextField("description", blank=True)
    probabilite = models.PositiveSmallIntegerField("probabilité")
    impact = models.PositiveSmallIntegerField("impact")
    score = models.GeneratedField(
        expression=_PRODUIT,
        output_field=models.PositiveSmallIntegerField(),
        db_persist=True,
        verbose_name="score",
    )
    # Mêmes expressions que `referentiel.Risque` (seuils de `referentiel.scoring`).
    niveau = models.GeneratedField(
        expression=Case(
            When(GreaterThanOrEqual(_PRODUIT, Value(SEUIL_ELEVE)), then=Value(NiveauRisque.ELEVE)),
            When(GreaterThanOrEqual(_PRODUIT, Value(SEUIL_MOYEN)), then=Value(NiveauRisque.MOYEN)),
            default=Value(NiveauRisque.FAIBLE),
            output_field=CharField(max_length=8),
        ),
        output_field=CharField(max_length=8),
        db_persist=True,
        verbose_name="niveau",
    )
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        verbose_name = "risque de mission"
        verbose_name_plural = "risques de mission"
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(probabilite__gte=1, probabilite__lte=5),
                name="risque_mission_probabilite_1_5",
            ),
            models.CheckConstraint(
                condition=Q(impact__gte=1, impact__lte=5), name="risque_mission_impact_1_5"
            ),
            models.UniqueConstraint(
                fields=["mission", "risque_source"],
                condition=Q(deleted_at__isnull=True, risque_source__isnull=False),
                name="risque_mission_source_unique_actif",
            ),
            models.CheckConstraint(
                condition=(
                    Q(risque_source__isnull=True, code_source="")
                    | (Q(risque_source__isnull=False) & ~Q(code_source=""))
                ),
                name="risque_mission_code_source_coherent",
            ),
        ]

    def __str__(self) -> str:
        return self.libelle

    @property
    def nouveau(self) -> bool:
        """Risque créé dans la mission (absent de la cartographie)."""
        return self.risque_source_id is None

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.exiger_etape_ouverte(self.mission_id, 4)

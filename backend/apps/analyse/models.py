from typing import Any

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, MissionEnfantModel, RisqueMission, StatutEtape
from apps.referentiel.models import ObjetAuditable, Processus


class TypeQuestionnaire(models.TextChoices):
    PRISE_CONNAISSANCE = "PRISE_CONNAISSANCE", "Questionnaire de prise de connaissance"
    QCI = "QCI", "Questionnaire de contrôle interne"


class Appreciation(models.TextChoices):
    OUI = "OUI", "Oui"
    NON = "NON", "Non"
    SANS_OBJET = "SANS_OBJET", "Sans objet"


class TypologieProcessus(models.TextChoices):
    PILOTAGE = "PILOTAGE", "Pilotage"
    SUPPORT = "SUPPORT", "Support"
    REALISATION = "REALISATION", "Réalisation"
    MESURE = "MESURE", "Mesure"


class CategorieObjectif(models.TextChoices):
    OPERATIONNELS = "OPERATIONNELS", "Opérationnels"
    FIABILITE_INFORMATION = "FIABILITE_INFORMATION", "Fiabilité des informations"
    STRATEGIQUES = "STRATEGIQUES", "Stratégiques"
    CONFORMITE = "CONFORMITE", "Conformité"


class RoleTache(models.TextChoices):
    EXECUTE = "EXECUTE", "Exécute"
    AUTORISE = "AUTORISE", "Autorise"
    ENREGISTRE = "ENREGISTRE", "Enregistre"
    CONTROLE = "CONTROLE", "Contrôle"


class Composante(models.TextChoices):
    ENVIRONNEMENT = "ENVIRONNEMENT", "Environnement de contrôle"
    ACTIVITE = "ACTIVITE", "Activité de contrôle"


class NatureControle(models.TextChoices):
    PREVENTIF = "PREVENTIF", "Préventif"
    DETECTIF = "DETECTIF", "Détectif"
    CORRECTIF = "CORRECTIF", "Correctif"


class EvaluationConception(models.TextChoices):
    ADEQUATE = "ADEQUATE", "Conception adéquate — risque maîtrisé"
    INSUFFISANTE = "INSUFFISANTE", "Conception insuffisante"
    ABSENTE = "ABSENTE", "Contrôle absent"


class TypeForceFaiblesse(models.TextChoices):
    FORCE = "FORCE", "Force"
    FAIBLESSE = "FAIBLESSE", "Faiblesse"


class TypeAvis(models.TextChoices):
    ACCORD = "ACCORD", "Accord"
    REMARQUES = "REMARQUES", "Remarques"


class MotifNonTest(models.TextChoices):
    CONTROLE_NIVEAU_SUPERIEUR = "CONTROLE_NIVEAU_SUPERIEUR", "Contrôle de niveau supérieur"
    AUTRES_CONTROLES = "AUTRES_CONTROLES", "Autres contrôles couvrant totalement le risque"
    CONCEPTION_ADAPTEE = "CONCEPTION_ADAPTEE", "Conception adaptée"
    PERIODE_INCOMPATIBLE = (
        "PERIODE_INCOMPATIBLE",
        "Période de mise en œuvre incompatible avec le calendrier",
    )
    CHANGEMENT_ORGANISATION = (
        "CHANGEMENT_ORGANISATION",
        "Changements d'organisation impactant le dispositif",
    )


class CouvertureOrdre(models.TextChoices):
    EXACTE = "EXACTE", "Couverture exacte"
    ELARGIE = "ELARGIE", "Objectifs d'audit plus larges (avenant à l'ordre de mission)"
    PARTIELLE = (
        "PARTIELLE",
        "Objectifs d'audit ne couvrant pas tout l'ordre de mission (exclusion justifiée)",
    )


class VarianteOrientation(models.TextChoices):
    COMPLET = "COMPLET", "Rapport d'orientation complet"
    SIMPLIFIE = "SIMPLIFIE", "Rapport d'orientation simplifié"


class StatutReferentiel(models.TextChoices):
    BROUILLON = "BROUILLON", "En préparation"
    SOUMIS = "SOUMIS", "Soumis au RAI"
    RENVOYE = "RENVOYE", "Renvoyé"
    VALIDE = "VALIDE", "Validé"
    A_REVALIDER = "A_REVALIDER", "À revalider"


_STATUT_REFERENTIEL = {
    StatutEtape.TERMINEE: StatutReferentiel.SOUMIS,
    StatutEtape.RENVOYEE: StatutReferentiel.RENVOYE,
    StatutEtape.VALIDEE: StatutReferentiel.VALIDE,
    StatutEtape.A_REVALIDER: StatutReferentiel.A_REVALIDER,
}


def statut_referentiel(statut_vi: str) -> StatutReferentiel:
    """Statut du référentiel d'audit, dérivé du statut de l'étape VI (D2)."""
    return _STATUT_REFERENTIEL.get(StatutEtape(statut_vi), StatutReferentiel.BROUILLON)


def _mission_fk(related_name: str) -> models.ForeignKey[Mission]:
    return models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name=related_name, verbose_name="mission"
    )


class Questionnaire(MissionEnfantModel):
    mission = _mission_fk("questionnaires")
    type = models.CharField("type", max_length=24, choices=TypeQuestionnaire.choices)
    processus = models.ForeignKey(
        Processus,
        verbose_name="processus",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    titre = models.CharField("titre", max_length=200)

    class Meta:
        verbose_name = "questionnaire"
        verbose_name_plural = "questionnaires"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "type", "processus"],
                condition=Q(deleted_at__isnull=True),
                nulls_distinct=False,
                name="questionnaire_unique_actif",
            ),
        ]

    def __str__(self) -> str:
        return self.titre

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.exiger_gel_questionnaire(self.mission_id, self.type)


class QuestionQuestionnaire(MissionEnfantModel):
    mission = _mission_fk("questions_questionnaire")
    questionnaire = models.ForeignKey(
        Questionnaire,
        verbose_name="questionnaire",
        on_delete=models.PROTECT,
        related_name="questions",
    )
    theme = models.CharField("thème", max_length=200)
    libelle = models.TextField("question")
    reponse = models.TextField("réponse", blank=True)
    appreciation = models.CharField(
        "appréciation", max_length=16, choices=Appreciation.choices, blank=True
    )
    ordre = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "question de questionnaire"
        verbose_name_plural = "questions de questionnaire"
        ordering = ("ordre", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(appreciation__in=Appreciation.values) | Q(appreciation=""),
                name="question_appreciation_valide",
            ),
        ]

    def __str__(self) -> str:
        return self.libelle[:60]

    @property
    def repondue(self) -> bool:
        return bool(self.appreciation) or bool(self.reponse.strip())

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        type_ = (
            Questionnaire.all_objects.filter(pk=self.questionnaire_id)
            .values_list("type", flat=True)
            .first()
        )
        if type_ is not None:
            gardes.exiger_gel_questionnaire(self.mission_id, type_)


class DescriptionProcessus(MissionEnfantModel):
    mission = _mission_fk("descriptions_processus")
    processus = models.ForeignKey(
        Processus, verbose_name="processus", on_delete=models.PROTECT, related_name="+"
    )
    typologie = models.CharField(
        "typologie", max_length=16, choices=TypologieProcessus.choices, blank=True
    )
    categories_objectifs = ArrayField(
        models.CharField(max_length=24, choices=CategorieObjectif.choices),
        verbose_name="catégories d'objectifs",
        default=list,
        blank=True,
    )
    description = models.TextField("description", blank=True)
    objectifs = models.TextField("objectifs", blank=True)
    indicateurs = models.TextField("indicateurs", blank=True)
    sources = models.TextField("sources", blank=True)
    references_diagrammes = models.TextField("références des diagrammes", blank=True)

    class Meta:
        verbose_name = "description de processus"
        verbose_name_plural = "descriptions de processus"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "processus"],
                condition=Q(deleted_at__isnull=True),
                name="description_processus_unique_actif",
            ),
        ]

    def __str__(self) -> str:
        return f"Description du processus {self.processus_id}"

    def exiger_travaux_ouverts(self) -> None:
        from apps.missions import gardes

        gardes.exiger_etape_ouverte(self.mission_id, 3)


class GrilleSeparation(MissionEnfantModel):
    mission = _mission_fk("grilles_separation")
    processus = models.ForeignKey(
        Processus, verbose_name="processus", on_delete=models.PROTECT, related_name="+"
    )
    taches = models.JSONField("tâches", default=list, blank=True)
    acteurs = models.JSONField("acteurs", default=list, blank=True)
    cellules = models.JSONField("cellules", default=list, blank=True)
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        verbose_name = "grille de séparation des tâches"
        verbose_name_plural = "grilles de séparation des tâches"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "processus"],
                condition=Q(deleted_at__isnull=True),
                name="grille_separation_unique_actif",
            ),
        ]

    def __str__(self) -> str:
        return f"Grille du processus {self.processus_id}"

    def exiger_travaux_ouverts(self) -> None:
        from apps.missions import gardes

        gardes.exiger_etape_ouverte(self.mission_id, 3)


class LigneMARC(MissionEnfantModel):
    mission = _mission_fk("lignes_marc")
    risque = models.ForeignKey(
        RisqueMission,
        verbose_name="risque de mission",
        on_delete=models.PROTECT,
        related_name="lignes_marc",
    )
    objet_auditable = models.ForeignKey(
        ObjetAuditable,
        verbose_name="objet auditable",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    operation = models.CharField("opération", max_length=300, blank=True)
    objectif_controle = models.TextField("objectif de contrôle", blank=True)
    controle_attendu = models.TextField("contrôle attendu", blank=True)
    controle_existant = models.TextField("contrôle existant", blank=True)
    commentaire = models.TextField("commentaire", blank=True)
    composante = models.CharField(
        "composante", max_length=16, choices=Composante.choices, blank=True
    )
    nature = models.CharField("nature", max_length=16, choices=NatureControle.choices, blank=True)
    evaluation = models.CharField(
        "évaluation de la conception", max_length=16, choices=EvaluationConception.choices,
        blank=True,
    )  # fmt: skip
    cle = models.BooleanField("contrôle clé", default=False)
    ordre = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "ligne de la matrice d'analyse des risques et contrôles"
        verbose_name_plural = "lignes de la matrice d'analyse des risques et contrôles"
        ordering = ("ordre", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~Q(
                        evaluation__in=[
                            EvaluationConception.ADEQUATE,
                            EvaluationConception.INSUFFISANTE,
                        ]
                    )
                    | ~Q(controle_existant="")
                ),
                name="marc_evaluation_exige_controle_existant",
            ),
            models.CheckConstraint(
                condition=Q(cle=False) | ~Q(evaluation=EvaluationConception.ABSENTE),
                name="marc_cle_exige_controle_present",
            ),
        ]

    def __str__(self) -> str:
        return self.operation or self.objectif_controle[:60]

    @property
    def appreciation(self) -> str | None:
        if self.evaluation == EvaluationConception.ADEQUATE:
            return TypeForceFaiblesse.FORCE
        if self.evaluation in (EvaluationConception.INSUFFISANTE, EvaluationConception.ABSENTE):
            return TypeForceFaiblesse.FAIBLESSE
        return None

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.exiger_fenetre_marc(self.mission_id)


class ForceFaiblesse(MissionEnfantModel):
    mission = _mission_fk("forces_faiblesses")
    type = models.CharField("type", max_length=16, choices=TypeForceFaiblesse.choices)
    ligne_marc = models.OneToOneField(
        LigneMARC,
        verbose_name="ligne de la matrice",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="force_faiblesse",
    )
    processus = models.ForeignKey(
        Processus,
        verbose_name="processus",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    libelle = models.CharField("libellé", max_length=500)
    consequence = models.TextField("conséquence", blank=True)
    commentaire = models.TextField("commentaire", blank=True)
    ordre = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "force ou faiblesse apparente"
        verbose_name_plural = "forces et faiblesses apparentes"
        ordering = ("ordre", "created_at")

    def __str__(self) -> str:
        return self.libelle

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.exiger_fenetre_marc(self.mission_id)


class AvisAudite(MissionEnfantModel):
    mission = _mission_fk("avis_audites")
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="auteur",
        on_delete=models.PROTECT,
        related_name="+",
    )
    avis = models.CharField("avis", max_length=16, choices=TypeAvis.choices)
    commentaire = models.TextField("commentaire", blank=True)
    donne_le = models.DateTimeField("donné le", default=timezone.now)

    class Meta:
        verbose_name = "avis d'audité"
        verbose_name_plural = "avis d'audités"
        ordering = ("donne_le",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(avis=TypeAvis.REMARQUES) | ~Q(commentaire=""),
                name="avis_remarques_exige_commentaire",
            ),
        ]

    def __str__(self) -> str:
        return self.get_avis_display()

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.exiger_avis_ouvert(self.mission_id)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            from apps.missions import gardes

            gardes.controler_sauvegarde(self)  # gel de mission / d'étape prioritaire
            raise RegleMetierError("Un avis déposé ne peut pas être modifié.")
        super().save(*args, **kwargs)


class ObjectifAudit(MissionEnfantModel):
    mission = _mission_fk("objectifs_audit")
    ligne_marc = models.ForeignKey(
        LigneMARC,
        verbose_name="ligne de la matrice",
        on_delete=models.PROTECT,
        related_name="objectifs_audit",
    )
    numero = models.PositiveSmallIntegerField("numéro")
    libelle = models.CharField("libellé", max_length=500)
    retenu = models.BooleanField("retenu", default=True)
    motif_non_test = models.CharField(
        "motif de non-test", max_length=32, choices=MotifNonTest.choices, blank=True
    )
    justification = models.TextField("justification", blank=True)

    class Meta:
        verbose_name = "objectif d'audit"
        verbose_name_plural = "objectifs d'audit"
        ordering = ("numero",)
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "numero"],
                condition=Q(deleted_at__isnull=True),
                name="objectif_audit_numero_unique_actif",
            ),
            models.UniqueConstraint(
                fields=["mission", "ligne_marc"],
                condition=Q(deleted_at__isnull=True),
                name="objectif_audit_ligne_unique_actif",
            ),
            models.CheckConstraint(
                condition=(
                    Q(retenu=True, motif_non_test="") | (Q(retenu=False) & ~Q(motif_non_test=""))
                ),
                name="objectif_audit_motif_coherent",
            ),
            models.CheckConstraint(
                condition=Q(retenu=True) | ~Q(justification=""),
                name="objectif_audit_non_retenu_justifie",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.libelle}"

    @property
    def code(self) -> str:
        return f"OA-{self.numero:02d}"

    def exiger_travaux_ouverts(self) -> None:
        from apps.missions import gardes

        gardes.exiger_etape_ouverte(self.mission_id, 7)


class RapportOrientation(MissionEnfantModel):
    mission = _mission_fk("rapports_orientation")
    variante = models.CharField(
        "variante",
        max_length=16,
        choices=VarianteOrientation.choices,
        default=VarianteOrientation.COMPLET,
    )
    contexte = models.TextField("contexte", blank=True)
    approche = models.TextField("approche", blank=True)
    observations = models.TextField("observations", blank=True)
    couverture_ordre = models.CharField(
        "couverture de l'ordre de mission",
        max_length=16,
        choices=CouvertureOrdre.choices,
        blank=True,
    )
    justification_couverture = models.TextField("justification", blank=True)

    class Meta:
        verbose_name = "rapport d'orientation"
        verbose_name_plural = "rapports d'orientation"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["mission"],
                condition=Q(deleted_at__isnull=True),
                name="rapport_orientation_unique_actif",
            ),
            models.CheckConstraint(
                condition=(
                    Q(couverture_ordre__in=["", CouvertureOrdre.EXACTE])
                    | ~Q(justification_couverture="")
                ),
                name="rapport_orientation_couverture_justifiee",
            ),
        ]

    def __str__(self) -> str:
        return self.get_variante_display()

    def exiger_travaux_ouverts(self) -> None:
        from apps.missions import gardes

        gardes.exiger_etape_ouverte(self.mission_id, 7)

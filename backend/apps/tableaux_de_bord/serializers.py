"""Sérialiseurs explicites des tableaux de bord : un par bloc, clés figées par `test_api_contrat`.

Les taux sont des fractions entre 0 et 1 (flottants), `null` quand le dénominateur est nul.
"""

from typing import Any

from rest_framework import serializers

_Base = serializers.Serializer[dict[str, Any]]


class MissionsParStatutSerializer(_Base):
    statut = serializers.CharField()
    libelle = serializers.CharField()
    phase = serializers.CharField(allow_null=True)
    nombre = serializers.IntegerField()


class MissionEnRetardSerializer(_Base):
    mission_id = serializers.UUIDField()
    reference = serializers.CharField()
    titre = serializers.CharField()
    statut = serializers.CharField()
    date_fin_prevue = serializers.DateField()
    jours_retard = serializers.IntegerField()


class JalonAValiderSerializer(_Base):
    mission_id = serializers.UUIDField()
    reference = serializers.CharField()
    numero = serializers.IntegerField()
    romain = serializers.CharField()
    libelle = serializers.CharField()
    terminee_le = serializers.DateTimeField(allow_null=True)


class LigneDirectionSerializer(_Base):
    direction_id = serializers.UUIDField()
    code = serializers.CharField()
    libelle = serializers.CharField()
    cloturees = serializers.IntegerField()
    ouvertes_dans_les_delais = serializers.IntegerField()
    en_retard = serializers.IntegerField()
    abandonnees = serializers.IntegerField()


class FileDecisionsSerializer(_Base):
    a_cloturer = serializers.IntegerField()
    abandons_proposes = serializers.IntegerField()
    reports_en_attente = serializers.IntegerField()
    missions_a_cloturer = serializers.IntegerField()
    relances_en_echec = serializers.IntegerField()
    relances_sans_adresse = serializers.IntegerField()


class CelluleCartographieSerializer(_Base):
    probabilite = serializers.IntegerField()
    impact = serializers.IntegerField()
    nombre = serializers.IntegerField()


class CartographieSerializer(_Base):
    version_id = serializers.UUIDField(allow_null=True)
    annee = serializers.IntegerField(allow_null=True)
    cellules = CelluleCartographieSerializer(many=True)


class TauxSerializer(_Base):
    cloturees = serializers.IntegerField()
    abandonnees = serializers.IntegerField()
    total = serializers.IntegerField()
    taux = serializers.FloatField(allow_null=True)
    echues = serializers.IntegerField()
    cloturees_echues = serializers.IntegerField()
    taux_echues = serializers.FloatField(allow_null=True)


class TauxParDirectionSerializer(TauxSerializer):
    direction_id = serializers.UUIDField()
    code = serializers.CharField()
    libelle = serializers.CharField()


class RapportDiffuseResumeSerializer(_Base):
    mission_id = serializers.UUIDField()
    reference = serializers.CharField()
    titre = serializers.CharField()
    statut = serializers.CharField()
    nombre_actions = serializers.IntegerField()
    actions_cloturees = serializers.IntegerField()


class RisqueEleveSerializer(_Base):
    id = serializers.UUIDField()
    code = serializers.CharField()
    libelle = serializers.CharField()
    processus_code = serializers.CharField()
    couvert = serializers.BooleanField()
    missions = serializers.ListField(child=serializers.CharField())


class RisquesElevesSerializer(_Base):
    couverts = serializers.IntegerField()
    non_couverts = serializers.IntegerField()
    risques = RisqueEleveSerializer(many=True)


class MissionSuiviResumeSerializer(_Base):
    mission_id = serializers.UUIDField()
    reference = serializers.CharField()
    titre = serializers.CharField()
    statut = serializers.CharField()
    date_fin_prevue = serializers.DateField(allow_null=True)


class EtapeEnCoursSerializer(_Base):
    mission_id = serializers.UUIDField()
    reference = serializers.CharField()
    numero = serializers.IntegerField()
    romain = serializers.CharField()
    libelle = serializers.CharField()
    date_fin_prevue = serializers.DateField(allow_null=True)
    en_retard = serializers.BooleanField()


class TestATraiterSerializer(_Base):
    test_id = serializers.UUIDField()
    mission_id = serializers.UUIDField()
    reference = serializers.CharField()
    code = serializers.CharField()
    libelle = serializers.CharField()
    sans_fiche = serializers.BooleanField()


class ActionAVerifierSerializer(_Base):
    suivi_id = serializers.UUIDField()
    mission_id = serializers.UUIDField()
    reference = serializers.CharField()
    libelle = serializers.CharField()
    declaree_le = serializers.DateTimeField(allow_null=True)


class ConstatARepondreSerializer(_Base):
    constat_id = serializers.UUIDField()
    mission_id = serializers.UUIDField()
    mission_reference = serializers.CharField()
    reference = serializers.CharField()
    titre = serializers.CharField()
    cycle = serializers.IntegerField()
    soumis_le = serializers.DateTimeField(allow_null=True)


class MonActionSerializer(_Base):
    suivi_id = serializers.UUIDField()
    mission_id = serializers.UUIDField()
    reference = serializers.CharField()
    libelle = serializers.CharField()
    statut = serializers.CharField()
    echeance = serializers.DateField()
    en_retard = serializers.BooleanField()
    jours_retard = serializers.IntegerField(allow_null=True)


class MaDemandeReportSerializer(_Base):
    demande_id = serializers.UUIDField()
    suivi_id = serializers.UUIDField()
    reference = serializers.CharField()
    libelle = serializers.CharField()
    echeance_actuelle = serializers.DateField()
    nouvelle_echeance = serializers.DateField()
    statut = serializers.CharField()


class TableauRaiSerializer(_Base):
    annee = serializers.IntegerField()
    missions_par_statut = MissionsParStatutSerializer(many=True)
    missions_en_retard = MissionEnRetardSerializer(many=True)
    etapes_en_retard = serializers.IntegerField()
    jalons_a_valider = JalonAValiderSerializer(many=True)
    actions_par_direction = LigneDirectionSerializer(many=True)
    file_decisions = FileDecisionsSerializer()
    cartographie = CartographieSerializer()
    taux = TauxSerializer()


class TableauAuditeurSerializer(_Base):
    mes_missions = MissionSuiviResumeSerializer(many=True)
    mes_etapes_en_cours = EtapeEnCoursSerializer(many=True)
    mes_tests_a_documenter = TestATraiterSerializer(many=True)
    actions_a_verifier = ActionAVerifierSerializer(many=True)


class TableauAuditeSerializer(_Base):
    constats_a_repondre = ConstatARepondreSerializer(many=True)
    mes_actions = MonActionSerializer(many=True)
    mes_demandes_report = MaDemandeReportSerializer(many=True)


class TableauDgSerializer(_Base):
    annee = serializers.IntegerField()
    rapports_diffuses = RapportDiffuseResumeSerializer(many=True)
    taux = TauxSerializer()
    taux_par_direction = TauxParDirectionSerializer(many=True)
    risques_eleves = RisquesElevesSerializer()

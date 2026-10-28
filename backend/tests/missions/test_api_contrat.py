import datetime
import uuid

import yaml
from django.utils import timezone
from rest_framework.test import APIClient

from apps.missions.models import EvenementEtape, StatutEtape, TypeEvenementEtape
from apps.users.models import Role
from tests.factories import EtapeMissionFactory, MissionFactory, make_user

MISSION_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
ETAPE_1 = uuid.UUID("22222222-2222-4222-8222-222222222221")
ETAPE_2 = uuid.UUID("22222222-2222-4222-8222-222222222222")


def test_api_contrat_fiche_suivi(api_client: APIClient, db: None) -> None:
    """JSON exact d'une fiche à deux lignes ; recopié tel quel dans les fixtures MSW de T8.

    `ecart_jours` positif = retard : 3 jours de retard (étape I), 2 jours d'avance (étape II).
    """
    rai = make_user(Role.RAI, id=900, username="rai.contrat", first_name="Awa", last_name="Traore")
    mission = MissionFactory(
        id=MISSION_ID,
        titre="Audit des achats",
        reference="DAI/2026/M01",
        annee=2026,
        numero=1,
        statut="EN_PLANIFICATION",
        budget_jours="12.0",
    )
    EtapeMissionFactory(
        id=ETAPE_1,
        mission=mission,
        numero=1,
        statut=StatutEtape.TERMINEE,
        date_debut_prevue=datetime.date(2026, 3, 2),
        date_fin_prevue=datetime.date(2026, 3, 10),
        date_debut_reelle=datetime.date(2026, 3, 2),
        date_fin_reelle=datetime.date(2026, 3, 13),
        charge_prevue_jours="2.0",
        charge_reelle_jours="3.5",
    )
    EtapeMissionFactory(
        id=ETAPE_2,
        mission=mission,
        numero=2,
        statut=StatutEtape.TERMINEE,
        date_debut_prevue=datetime.date(2026, 3, 11),
        date_fin_prevue=datetime.date(2026, 3, 20),
        date_debut_reelle=datetime.date(2026, 3, 13),
        date_fin_reelle=datetime.date(2026, 3, 18),
        charge_prevue_jours="3.0",
        charge_reelle_jours="3.0",
    )
    evenement = EvenementEtape.objects.create(
        etape_id=ETAPE_1,
        type=TypeEvenementEtape.TERMINEE,
        par=rai,
        le=datetime.datetime(2026, 3, 13, 10, 0, tzinfo=datetime.UTC),
        statut_avant=StatutEtape.EN_COURS,
        statut_apres=StatutEtape.TERMINEE,
    )
    assert evenement.pk
    api_client.force_authenticate(rai)
    r = api_client.get(f"/api/v1/missions/{MISSION_ID}/tracking/")
    assert r.status_code == 200, r.json()
    assert r.json() == {
        "mission": {
            "id": str(MISSION_ID),
            "reference": "DAI/2026/M01",
            "titre": "Audit des achats",
        },
        "budget_jours": "12.0",
        "total_prevu": "5.0",
        "total_reel": "6.5",
        "lignes": [
            {
                "numero": 1,
                "romain": "I",
                "titre": "Préciser les objectifs et le périmètre de la mission",
                "phase": "PLANIFICATION",
                "jalon": False,
                "statut": "TERMINEE",
                "debut_prevu": "2026-03-02",
                "fin_prevue": "2026-03-10",
                "debut_reel": "2026-03-02",
                "fin_reelle": "2026-03-13",
                "ecart_jours": 3,
                "charge_prevue": "2.0",
                "charge_reelle": "3.5",
            },
            {
                "numero": 2,
                "romain": "II",
                "titre": "Conduire la réunion d'ouverture",
                "phase": "PLANIFICATION",
                "jalon": False,
                "statut": "TERMINEE",
                "debut_prevu": "2026-03-11",
                "fin_prevue": "2026-03-20",
                "debut_reel": "2026-03-13",
                "fin_reelle": "2026-03-18",
                "ecart_jours": -2,
                "charge_prevue": "3.0",
                "charge_reelle": "3.0",
            },
        ],
        "evenements": [
            {
                "type": "TERMINEE",
                "par": {
                    "id": 900,
                    "username": "rai.contrat",
                    "nom_complet": "Awa Traore",
                    "role": "RAI",
                    "direction_code": "DAI",
                    "fonction": "Auditeur interne",
                },
                "le": "2026-03-13T10:00:00Z",
                "motif": "",
                "statut_avant": "EN_COURS",
                "statut_apres": "TERMINEE",
                "etape_romain": "I",
            }
        ],
    }
    assert timezone.is_aware(evenement.le)


def test_schema_expose_les_routes_missions(api_client: APIClient) -> None:
    r = api_client.get("/api/schema/")
    assert r.status_code == 200
    schema = yaml.safe_load(r.content)
    chemins = set(schema["paths"])
    attendus = {
        "/api/v1/users/",
        "/api/v1/missions/",
        "/api/v1/missions/{id}/",
        "/api/v1/missions/{id}/plan/",
        "/api/v1/missions/{id}/launch/",
        "/api/v1/missions/{id}/issue-order/",
        "/api/v1/missions/{id}/suspend/",
        "/api/v1/missions/{id}/resume/",
        "/api/v1/missions/{id}/cancel/",
        "/api/v1/missions/{id}/tracking/",
        "/api/v1/missions/{id}/risk-matrix/",
        "/api/v1/missions/{id}/default-auditees/",
        "/api/v1/missions/{id}/replace-chief/",
        "/api/v1/mission-assignments/",
        "/api/v1/mission-assignments/{id}/",
        "/api/v1/independence-declarations/",
        "/api/v1/independence-declarations/{id}/confirm/",
        "/api/v1/independence-declarations/{id}/arbitrate/",
        "/api/v1/mission-steps/",
        "/api/v1/mission-steps/{id}/",
        "/api/v1/mission-steps/{id}/start/",
        "/api/v1/mission-steps/{id}/complete/",
        "/api/v1/mission-steps/{id}/validate/",
        "/api/v1/mission-steps/{id}/return/",
        "/api/v1/mission-steps/{id}/reopen/",
        "/api/v1/mission-steps/{id}/not-applicable/",
        "/api/v1/mission-steps/{id}/restore/",
        "/api/v1/meetings/{id}/mark-held/",
        "/api/v1/interviews/{id}/mark-done/",
        "/api/v1/interviews/{id}/cancel/",
        "/api/v1/mission-risks/",
        "/api/v1/mission-risks/{id}/",
    }
    assert attendus <= chemins
    composants = set(schema["components"]["schemas"])
    assert {
        "UtilisateurResume",
        "MissionListe",
        "Mission",
        "Affectation",
        "Declaration",
        "Etape",
        "FicheSuivi",
        "Reunion",
        "Entretien",
        "RisqueMission",
        "MatriceMission",
        "MotifRequest",
        "ConfirmationRequest",
        "ArbitrageRequest",
        "RemplacerChefRequest",
        "DroitsMission",
        "TypeMissionEnum",
        "StatutMissionEnum",
        "EvenementDeclencheurEnum",
        "RoleMissionEnum",
        "PhaseEnum",
        "StatutEtapeEnum",
        "TypeEvenementEtapeEnum",
        "StatutDeclarationEnum",
        "TypeReunionEnum",
        "StatutEntretienEnum",
        "ActionEtapeEnum",
        "TypeDocumentSignableEnum",
    } <= composants
    # Pas de PUT.
    assert all("put" not in schema["paths"][p] for p in attendus)
    # La liste des étapes n'est pas paginée.
    liste = schema["paths"]["/api/v1/mission-steps/"]["get"]["responses"]["200"]
    assert liste["content"]["application/json"]["schema"]["type"] == "array"

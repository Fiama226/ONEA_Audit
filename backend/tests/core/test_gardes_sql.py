"""Gel en base (lot 9, T10, D6) : déclencheurs, rôle applicatif sans privilèges, maintenance.

Les tests créent un rôle de test `onea_t10_app` DANS la transaction du test (annulée à la fin) et
y basculent par `SET LOCAL ROLE`, comme le ferait le rôle applicatif de production.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from typing import Any

import pytest
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.core import gardes_sql
from apps.core.gardes_sql import (
    NOM_MODIFICATION,
    NOM_SUPPRESSION,
    TABLES_AJOUT_SEUL,
    declencheurs_attendus,
    installer,
    maintenance,
    verifier,
)
from apps.core.models import BaseModel
from apps.documents.models import Document, DocumentVersion, GabaritDocument
from apps.missions.models import EvenementEtape, Mission, TypeEvenementEtape
from apps.notifications.models import Notification, TypeNotification
from apps.programmation.models import ProgrammeAnnuel, StatutProgramme
from apps.referentiel.models import CartographieVersion, StatutCartographie
from apps.users.models import Role, User
from tests.factories import (
    ConfirmationFactory,
    DirectionFactory,
    EtapeMissionFactory,
    MissionFactory,
    RisqueFactory,
    make_user,
)
from tests.programmation.factories import ligne, programme

_mission: Any = MissionFactory
_risque: Any = RisqueFactory
_confirmation: Any = ConfirmationFactory
_etape: Any = EtapeMissionFactory
_direction: Any = DirectionFactory

ROLE = "onea_t10_app"
MOTIF = "ERREUR ONEA"
REFUS = "ERREUR ONEA|permission denied"  # privilège puis déclencheur : deux verrous

pytestmark = pytest.mark.django_db


@pytest.fixture
def role_app(db: None) -> str:
    """Rôle sans privilèges, créé dans la transaction du test (annulé avec elle)."""
    with connection.cursor() as c:
        c.execute(f"CREATE ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
    resultat = installer(role=ROLE)
    assert resultat["droits"] is True
    return ROLE


@contextmanager
def comme(role: str) -> Iterator[None]:
    with connection.cursor() as c:
        c.execute(f"SET LOCAL ROLE {role}")
    try:
        yield
    finally:
        with connection.cursor() as c:
            c.execute("RESET ROLE")


def sql(requete: str, params: list[Any] | None = None) -> None:
    with connection.cursor() as c:
        c.execute(requete, params)


def refuse(requete: str, params: list[Any] | None = None, *, message: str = MOTIF) -> None:
    """La requête échoue avec le message attendu ; la transaction du test reste utilisable."""
    with pytest.raises(DatabaseError, match=message), transaction.atomic():
        sql(requete, params)


def refuse_role(requete: str, params: list[Any] | None = None) -> None:
    """Sous le rôle applicatif, un DELETE est refusé par le privilège, puis par le déclencheur."""
    refuse(requete, params, message=REFUS)


def accepte(requete: str, params: list[Any] | None = None) -> int:
    with connection.cursor() as c:
        c.execute(requete, params)
        return int(c.rowcount)


def declencheurs_en_base() -> dict[str, set[str]]:
    with connection.cursor() as c:
        c.execute(
            "SELECT cl.relname, t.tgname FROM pg_trigger t JOIN pg_class cl ON cl.oid = t.tgrelid "
            "WHERE NOT t.tgisinternal AND left(t.tgname, 5) = 'onea_'"
        )
        sortie: dict[str, set[str]] = {}
        for table, nom in c.fetchall():
            sortie.setdefault(table, set()).add(nom)
        return sortie


# --- Couverture ----------------------------------------------------------------------------

TABLES_LOTS_6_A_8 = {
    # lot 6 : accomplissement, constats
    "accomplissement_programmedetravail",
    "accomplissement_testprevu",
    "accomplissement_fichedetest",
    "accomplissement_evenementfiche",
    "accomplissement_piecejustificative",
    "accomplissement_instantaneprogramme",
    "constats_constat",
    "constats_causeconstat",
    "constats_recommandation",
    "constats_reponseaudite",
    "constats_evenementconstat",
    # lot 7 : plan d'actions, communication
    "recommandations_action",
    "recommandations_acceptationrisque",
    "recommandations_engagementplanactions",
    "communication_rapport",
    "communication_rapportprovisoire",
    "communication_reponserapport",
    "communication_evenementrapport",
    "communication_destinatairediffusion",
    "communication_diffusion",
    # lot 8 : suivi, notifications
    "suivi_suiviaction",
    "suivi_evenementsuivi",
    "suivi_demandereport",
    "suivi_preuvemiseenoeuvre",
    "suivi_relance",
    "notifications_notification",
    # documents, signatures, consultations
    "documents_gabaritdocument",
    "documents_formatnumerotation",
    "documents_document",
    "documents_documentversion",
    "documents_consultationdocument",
    "signatures_parametresignature",
    "signatures_confirmation",
    "core_consultation",
}


def test_chaque_table_basemodel_a_son_declencheur() -> None:
    en_base = declencheurs_en_base()
    modeles = [m for m in apps.get_models() if issubclass(m, BaseModel) and not m._meta.abstract]
    assert len(modeles) > 50
    for modele in modeles:
        table = modele._meta.db_table
        noms = en_base.get(table, set())
        assert noms & {NOM_SUPPRESSION, NOM_MODIFICATION}, f"{table} sans garde de suppression"


def test_les_tables_des_lots_6_a_8_sont_couvertes() -> None:
    en_base = declencheurs_en_base()
    manquantes = {t for t in TABLES_LOTS_6_A_8 if t not in en_base}
    assert not manquantes, manquantes


def test_tables_en_ajout_seul_refusent_update_et_delete() -> None:
    en_base = declencheurs_en_base()
    for label in TABLES_AJOUT_SEUL:
        table = apps.get_model(label)._meta.db_table
        assert NOM_MODIFICATION in en_base[table], table
        assert NOM_SUPPRESSION not in en_base[table], table  # une seule garde, déjà plus stricte


def test_les_declencheurs_attendus_sont_tous_poses_et_actifs() -> None:
    assert verifier() == []
    assert len(declencheurs_attendus()) >= 70


def test_installation_idempotente() -> None:
    assert installer()["declencheurs"] == 0  # déjà à jour : rien à refaire


def test_reparation_d_un_declencheur_supprime() -> None:
    sql("DROP TRIGGER onea_refuser_suppression ON missions_mission")
    assert any("manquant" in p for p in verifier())
    assert installer()["declencheurs"] > 0
    assert verifier() == []


def test_commande_verifier_code_1_si_declencheur_desactive() -> None:
    sortie = StringIO()
    call_command("installer_gardes_sql", "--verifier", stdout=sortie)
    assert "conforme" in sortie.getvalue()
    sql("ALTER TABLE missions_mission DISABLE TRIGGER onea_refuser_suppression")
    with pytest.raises(CommandError, match="écart"):
        call_command("installer_gardes_sql", "--verifier", stderr=StringIO())


def test_commande_verifier_detecte_arguments_alteres() -> None:
    sql("DROP TRIGGER onea_colonnes_immuables ON documents_document")
    sql(
        "CREATE TRIGGER onea_colonnes_immuables BEFORE UPDATE ON documents_document "
        "FOR EACH ROW EXECUTE FUNCTION onea_colonnes_immuables('', 'annee')"
    )
    assert any("arguments différents" in p for p in verifier())


# --- Rôle applicatif -----------------------------------------------------------------------


def test_role_applicatif_conforme(role_app: str) -> None:
    assert verifier(role=role_app, exiger_role=True) == []
    with connection.cursor() as c:
        c.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolinherit FROM pg_roles "
            "WHERE rolname = %s",
            [role_app],
        )
        assert c.fetchone() == (False, False, False, False)
        c.execute(
            "SELECT count(*) FROM pg_class WHERE relkind IN ('r','p','S') "
            "AND pg_get_userbyid(relowner) = %s",
            [role_app],
        )
        assert c.fetchone() == (0,)


def test_verifier_signale_un_role_trop_puissant(role_app: str) -> None:
    sql(f"GRANT DELETE ON missions_mission TO {role_app}")
    assert any("DELETE sur missions_mission" in p for p in verifier(role=role_app))


def test_droits_du_role_applicatif(role_app: str) -> None:
    with connection.cursor() as c:
        c.execute(
            "SELECT has_table_privilege(%s, 'missions_mission', p) FROM "
            "unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','TRIGGER']) p",
            [role_app],
        )
        assert [r[0] for r in c.fetchall()] == [True, True, True, False, False, False]
        c.execute(
            "SELECT has_table_privilege(%s, 'django_session', 'DELETE'), "
            "has_table_privilege(%s, 'missions_mission_processus', 'DELETE')",
            [role_app, role_app],
        )
        assert c.fetchone() == (True, True)


def test_role_applicatif_ne_peut_ni_desactiver_ni_tronquer(role_app: str) -> None:
    with comme(role_app):
        refuse(
            "ALTER TABLE missions_mission DISABLE TRIGGER ALL", message="must be owner|propriétaire"
        )
        refuse("TRUNCATE missions_mission", message="permission denied|permission refusée")
        refuse("DROP TRIGGER onea_refuser_suppression ON missions_mission", message="must be owner")
        refuse(
            "CREATE OR REPLACE FUNCTION onea_refuser_suppression() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RETURN OLD; END $$",
            message="must be owner|permission denied",
        )
        refuse(
            "SET session_replication_role = replica", message="permission denied|permission refusée"
        )
        refuse(
            "CREATE TABLE onea_t10_intrus (x int)", message="permission denied|permission refusée"
        )


def test_role_applicatif_sans_effet_de_la_maintenance(role_app: str) -> None:
    mission = _mission()
    with comme(role_app):
        sql("SET LOCAL onea.maintenance = 'on'")
        refuse("DELETE FROM missions_mission WHERE id = %s", [mission.pk], message=REFUS)
    # Même avec le droit DELETE (erreur d'administration), le déclencheur refuse.
    sql(f"GRANT DELETE ON missions_mission TO {role_app}")
    with comme(role_app):
        sql("SET LOCAL onea.maintenance = 'on'")
        refuse("DELETE FROM missions_mission WHERE id = %s", [mission.pk])


def test_proprietaire_avec_maintenance_peut_supprimer() -> None:
    mission = _mission()
    refuse("DELETE FROM missions_mission WHERE id = %s", [mission.pk])  # propriétaire sans mode
    sql("SET LOCAL onea.maintenance = 'on'")
    assert accepte("DELETE FROM missions_mission WHERE id = %s", [mission.pk]) == 1


def test_maintenance_contextuelle_se_referme() -> None:
    mission = _mission()
    with maintenance():
        assert accepte("DELETE FROM missions_mission WHERE id = %s", [mission.pk]) == 1
    autre = _mission()
    refuse("DELETE FROM missions_mission WHERE id = %s", [autre.pk])


def test_hard_delete_reste_possible_pour_le_proprietaire() -> None:
    mission = _mission()
    mission.hard_delete()
    assert not Mission.all_objects.filter(pk=mission.pk).exists()


def test_hard_delete_refuse_au_role_applicatif(role_app: str) -> None:
    mission = _mission()
    with comme(role_app), pytest.raises(DatabaseError, match=REFUS), transaction.atomic():
        mission.hard_delete()


# --- Suppression physique ------------------------------------------------------------------


def test_delete_brut_refuse_sur_mission_risque_version(role_app: str) -> None:
    mission = _mission()
    risque = _risque()
    version = _version_prete(mission)
    with comme(role_app):
        refuse_role("DELETE FROM missions_mission WHERE id = %s", [mission.pk])
        refuse_role("DELETE FROM referentiel_risque WHERE id = %s", [risque.pk])
        refuse_role("DELETE FROM documents_documentversion WHERE id = %s", [version.pk])
        refuse_role("DELETE FROM missions_mission")


def test_delete_brut_refuse_par_declencheur_meme_au_proprietaire() -> None:
    mission = _mission()
    risque = _risque()
    version = _version_prete(mission)
    confirmation = _confirmation()
    for table, pk in (
        ("missions_mission", mission.pk),
        ("referentiel_risque", risque.pk),
        ("documents_documentversion", version.pk),
        ("signatures_confirmation", confirmation.pk),
    ):
        refuse(f"DELETE FROM {table} WHERE id = %s", [pk])  # noqa: S608


def test_delete_via_base_manager_refuse() -> None:
    mission = _mission()
    with pytest.raises(DatabaseError, match=MOTIF), transaction.atomic():
        Mission._base_manager.filter(pk=mission.pk).delete()
    with pytest.raises(DatabaseError, match=MOTIF), transaction.atomic():
        Mission._base_manager.all().delete()
    assert Mission.all_objects.filter(pk=mission.pk).exists()


def test_suppression_logique_reste_possible_pour_le_role(role_app: str) -> None:
    mission = _mission()
    auteur = make_user(Role.RAI)
    with comme(role_app):
        mission.soft_delete(auteur)
    mission.refresh_from_db()
    assert mission.deleted_at is not None


def test_ecritures_legitimes_du_role_applicatif(role_app: str) -> None:
    with comme(role_app):
        mission = _mission()
        assert Mission.objects.filter(pk=mission.pk).exists()
        _risque()
        Mission.all_objects.filter(pk=mission.pk).update(titre="Nouveau titre")


# --- Ajout seul ----------------------------------------------------------------------------


def test_update_et_delete_bruts_refuses_sur_les_tables_en_ajout_seul(role_app: str) -> None:
    confirmation = _confirmation()
    etape = _etape()
    auteur = make_user(Role.RAI)
    evenement = _evenement_etape(etape, auteur)
    with comme(role_app):
        refuse("UPDATE signatures_confirmation SET texte = 'x' WHERE id = %s", [confirmation.pk])
        refuse_role("DELETE FROM signatures_confirmation WHERE id = %s", [confirmation.pk])
        refuse("UPDATE missions_evenementetape SET motif = 'x' WHERE id = %s", [evenement.pk])
        refuse_role("DELETE FROM missions_evenementetape WHERE id = %s", [evenement.pk])
        refuse("UPDATE signatures_confirmation SET deleted_at = now()")


def test_auditlog_en_ajout_seul(role_app: str) -> None:
    mission = _mission()
    mission.titre = "Titre modifié"
    mission.save()
    with connection.cursor() as c:
        c.execute("SELECT count(*) FROM auditlog_logentry")
        assert c.fetchone()[0] >= 1
    with comme(role_app):
        refuse("UPDATE auditlog_logentry SET changes = '{}'")
        refuse_role("DELETE FROM auditlog_logentry")


def test_ajout_reste_possible_en_ajout_seul(role_app: str) -> None:
    with comme(role_app):
        _confirmation()
        mission = _mission()
        mission.titre = "Autre titre"
        mission.save()  # écrit une entrée du journal d'audit


# --- Colonnes immuables --------------------------------------------------------------------


def _evenement_etape(etape: Any, auteur: User) -> Any:
    code = TypeEvenementEtape.values[0]
    return EvenementEtape.objects.create(
        etape=etape, type=code, par=auteur, statut_avant="A_FAIRE", statut_apres="EN_COURS"
    )


def _version_prete(mission: Mission, statut: str = "PRETE") -> Any:
    auteur = make_user(Role.RAI)
    gabarit = GabaritDocument.objects.create(
        type_document="T10_DOC",
        version=1,
        fichier="gabarits/t10.docx",
        nom_original="t10.docx",
        taille=10,
        empreinte="a" * 64,
        contrat_version=1,
    )
    document = Document.objects.create(
        type_document="T10_DOC",
        mission=mission,
        content_type=ContentType.objects.get_for_model(Mission),
        object_id=mission.pk,
        numero=f"T10-{mission.pk}",
        annee=2026,
        sequence=1,
    )
    return DocumentVersion.objects.create(
        document=document,
        numero_version=1,
        statut=statut,
        gabarit=gabarit,
        demandee_par=auteur,
        fichier_docx="documents/t10.docx",
        empreinte_docx="b" * 64,
        taille_docx=10,
        genere_le=timezone.now(),
    )


def test_empreinte_d_une_version_prete_est_immuable(role_app: str) -> None:
    version = _version_prete(_mission())
    with comme(role_app):
        refuse(
            "UPDATE documents_documentversion SET empreinte_docx = %s WHERE id = %s",
            ["c" * 64, version.pk],
        )
        refuse("UPDATE documents_documentversion SET taille_docx = 1 WHERE id = %s", [version.pk])
        refuse(
            "UPDATE documents_documentversion SET fichier_docx = 'x' WHERE id = %s", [version.pk]
        )
        refuse(
            "UPDATE documents_documentversion SET deleted_at = now() WHERE id = %s", [version.pk]
        )
        refuse(
            "UPDATE documents_documentversion SET contexte = '{\"a\": 1}' WHERE id = %s",
            [version.pk],
        )


def test_version_prete_accepte_la_conversion_pdf_une_seule_fois(role_app: str) -> None:
    version = _version_prete(_mission())
    with comme(role_app):
        assert (
            accepte(
                "UPDATE documents_documentversion SET statut_pdf = 'EN_COURS', "
                "debut_traitement = now(), "
                "updated_at = now() WHERE id = %s",
                [version.pk],
            )
            == 1
        )
        assert (
            accepte(
                "UPDATE documents_documentversion SET fichier_pdf = 'documents/t10.pdf', "
                "empreinte_pdf = %s, taille_pdf = 5, statut_pdf = 'PRET' WHERE id = %s",
                ["d" * 64, version.pk],
            )
            == 1
        )
        accepte(
            "UPDATE documents_documentversion SET fichier_pdf = fichier_pdf WHERE id = %s",
            [version.pk],
        )
        refuse(
            "UPDATE documents_documentversion SET fichier_pdf = 'autre.pdf' WHERE id = %s",
            [version.pk],
        )
        refuse(
            "UPDATE documents_documentversion SET empreinte_pdf = %s WHERE id = %s",
            ["e" * 64, version.pk],
        )


def test_version_en_attente_reste_modifiable(role_app: str) -> None:
    version = _version_prete(_mission(), statut="EN_ATTENTE")
    with comme(role_app):
        assert (
            accepte(
                "UPDATE documents_documentversion SET statut = 'PRETE', "
                "empreinte_docx = %s WHERE id = %s",
                ["f" * 64, version.pk],
            )
            == 1
        )
        refuse("UPDATE documents_documentversion SET statut = 'ECHEC' WHERE id = %s", [version.pk])


def test_gabarit_et_numero_de_document_immuables(role_app: str) -> None:
    version = _version_prete(_mission())
    with comme(role_app):
        refuse("UPDATE documents_gabaritdocument SET empreinte = %s", ["0" * 64])
        refuse("UPDATE documents_gabaritdocument SET fichier = 'x'")
        refuse(
            "UPDATE documents_document SET numero = 'T10-X' WHERE id = %s", [version.document_id]
        )
        accepte("UPDATE documents_gabaritdocument SET commentaire = 'ok'")
        accepte("UPDATE documents_gabaritdocument SET statut = 'ARCHIVE'")


def test_notification_seuls_les_champs_d_etat_changent(role_app: str) -> None:
    destinataire = make_user(Role.AUDITE)
    notification = Notification.objects.create(
        destinataire=destinataire,
        type=TypeNotification.values[0],
        titre="Titre",
        message="Message",
        lien="/missions",
    )
    with comme(role_app):
        refuse(
            "UPDATE notifications_notification SET titre = 'autre' WHERE id = %s", [notification.pk]
        )
        refuse("UPDATE notifications_notification SET destinataire_id = %s", [make_user().pk])
        assert (
            accepte(
                "UPDATE notifications_notification SET lue_le = now(), "
                "updated_at = now() WHERE id = %s",
                [notification.pk],
            )
            == 1
        )
        assert (
            accepte(
                "UPDATE notifications_notification SET deleted_at = now() WHERE id = %s",
                [notification.pk],
            )
            == 1
        )


# --- États figés ---------------------------------------------------------------------------


def _cartographie(statut: str) -> Any:
    version = _risque().version
    if statut == StatutCartographie.VALIDEE:
        CartographieVersion._base_manager.filter(pk=version.pk).update(
            statut=StatutCartographie.VALIDEE, validee_le=timezone.now(), validee_par=make_user()
        )
        version.refresh_from_db()
    return version


def test_risque_d_une_cartographie_validee_est_fige(role_app: str) -> None:
    version = _cartographie(StatutCartographie.VALIDEE)
    risque = version.risques.first()
    assert risque is not None
    with comme(role_app):
        refuse("UPDATE referentiel_risque SET libelle = 'x' WHERE id = %s", [risque.pk])
        refuse("UPDATE referentiel_risque SET deleted_at = now() WHERE id = %s", [risque.pk])
        refuse(
            "UPDATE referentiel_cartographieversion SET libelle = 'x' WHERE id = %s", [version.pk]
        )
        refuse(
            "UPDATE referentiel_cartographieversion SET deleted_at = now() WHERE id = %s",
            [version.pk],
        )
    with comme(role_app):
        refuse(
            "INSERT INTO referentiel_risque (id, created_at, updated_at, version_id, processus_id, "
            "numero, rang, code, libelle, probabilite, impact, priorite) "
            "SELECT gen_random_uuid(), now(), now(), version_id, processus_id, 99, 99, 'T10-99', "
            "'x', 3, 3, priorite FROM referentiel_risque WHERE id = %s",
            [risque.pk],
        )


def test_risque_d_un_brouillon_reste_modifiable(role_app: str) -> None:
    version = _cartographie(StatutCartographie.BROUILLON)
    risque = version.risques.first()
    assert risque is not None
    with comme(role_app):
        assert (
            accepte("UPDATE referentiel_risque SET libelle = 'modifié' WHERE id = %s", [risque.pk])
            == 1
        )
        assert (
            accepte(
                "UPDATE referentiel_cartographieversion SET libelle = 'modifiée' WHERE id = %s",
                [version.pk],
            )
            == 1
        )
        # La validation elle-même (ligne encore BROUILLON en base) passe.
        assert (
            accepte(
                "UPDATE referentiel_cartographieversion SET statut = 'VALIDEE', "
                "validee_le = now(), "
                "validee_par_id = %s WHERE id = %s",
                [make_user().pk, version.pk],
            )
            == 1
        )
        refuse(
            "UPDATE referentiel_cartographieversion SET libelle = 'trop tard' WHERE id = %s",
            [version.pk],
        )
        refuse("UPDATE referentiel_risque SET libelle = 'trop tard' WHERE id = %s", [risque.pk])


def _programme(statut: str) -> ProgrammeAnnuel:
    prog = programme()
    ligne(programme=prog, numero=1)
    if statut == StatutProgramme.VALIDE:
        ProgrammeAnnuel._base_manager.filter(pk=prog.pk).update(
            statut=StatutProgramme.VALIDE, valide_le=timezone.now(), valide_par=make_user()
        )
    return prog


def test_ligne_d_un_programme_valide_est_figee(role_app: str) -> None:
    prog = _programme(StatutProgramme.VALIDE)
    ligne_id: Any = prog.lignes.values_list("pk", flat=True).first()
    with comme(role_app):
        refuse("UPDATE programmation_ligneprogramme SET titre = 'x' WHERE id = %s", [ligne_id])
        refuse(
            "UPDATE programmation_ligneprogramme SET deleted_at = now() WHERE id = %s", [ligne_id]
        )
        refuse("UPDATE programmation_programmeannuel SET libelle = 'x' WHERE id = %s", [prog.pk])
        refuse(
            "INSERT INTO programmation_ligneprogramme (id, created_at, updated_at, programme_id, "
            "numero, titre, type, processus_id, debut_prevu, fin_prevue, justification) "
            "SELECT gen_random_uuid(), now(), now(), programme_id, 9, 't', type, processus_id, "
            "debut_prevu, fin_prevue, '' FROM programmation_ligneprogramme WHERE id = %s",
            [ligne_id],
        )
        refuse(
            "INSERT INTO programmation_ligneprogramme_entites (ligneprogramme_id, direction_id) "
            "VALUES (%s, %s)",
            [ligne_id, _direction_id()],
        )


def _direction_id() -> Any:
    return _direction().pk


def test_ligne_d_un_programme_brouillon_reste_modifiable(role_app: str) -> None:
    prog = _programme(StatutProgramme.BROUILLON)
    ligne_id: Any = prog.lignes.values_list("pk", flat=True).first()
    direction = _direction_id()
    with comme(role_app):
        assert (
            accepte(
                "UPDATE programmation_ligneprogramme SET titre = 'ok' WHERE id = %s", [ligne_id]
            )
            == 1
        )
        assert (
            accepte(
                "INSERT INTO programmation_ligneprogramme_entites "
                "(ligneprogramme_id, direction_id) VALUES (%s, %s)",
                [ligne_id, direction],
            )
            == 1
        )
        assert (
            accepte(
                "DELETE FROM programmation_ligneprogramme_entites WHERE ligneprogramme_id = %s",
                [ligne_id],
            )
            == 1
        )
        accepte(
            "INSERT INTO programmation_ligneprogramme_entites (ligneprogramme_id, direction_id) "
            "VALUES (%s, %s)",
            [ligne_id, direction],
        )
        assert (
            accepte(
                "UPDATE programmation_programmeannuel SET statut = 'VALIDE', valide_le = now(), "
                "valide_par_id = %s WHERE id = %s",
                [make_user().pk, prog.pk],
            )
            == 1
        )
        refuse(
            "DELETE FROM programmation_ligneprogramme_entites WHERE ligneprogramme_id = %s",
            [ligne_id],
        )


# --- Maintenance et fonctions --------------------------------------------------------------


def test_proprietaire_en_maintenance_contourne_les_gardes() -> None:
    confirmation = _confirmation()
    refuse("UPDATE signatures_confirmation SET texte = 'x' WHERE id = %s", [confirmation.pk])
    sql("SET LOCAL onea.maintenance = 'on'")
    assert (
        accepte("UPDATE signatures_confirmation SET texte = 'x' WHERE id = %s", [confirmation.pk])
        == 1
    )
    assert accepte("DELETE FROM signatures_confirmation WHERE id = %s", [confirmation.pk]) == 1
    sql("SET LOCAL onea.maintenance = 'off'")
    autre = _confirmation()
    refuse("DELETE FROM signatures_confirmation WHERE id = %s", [autre.pk])


def test_messages_en_francais_et_sqlstate_p0001() -> None:
    mission = _mission()
    with pytest.raises(DatabaseError) as info, transaction.atomic():
        sql("DELETE FROM missions_mission WHERE id = %s", [mission.pk])
    assert getattr(info.value.__cause__, "sqlstate", None) == "P0001"
    assert "suppression physique interdite" in str(info.value)


def test_fonctions_figees_sur_pg_catalog() -> None:
    with connection.cursor() as c:
        c.execute(
            "SELECT p.proname, p.proconfig, p.prosecdef FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = current_schema() AND left(p.proname, 5) = 'onea_'"
        )
        lignes = c.fetchall()
    assert len(lignes) >= 8
    for nom, config, definer in lignes:
        assert config == ["search_path=pg_catalog"], nom
        assert definer is False, nom


def test_aucun_declencheur_ne_depend_d_une_colonne_inconnue() -> None:
    # `_attnames` échoue franc si une colonne figée n'existe pas : l'attendu se construit.
    assert gardes_sql.declencheurs_attendus()

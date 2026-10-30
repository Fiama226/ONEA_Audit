from datetime import date

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.communication.exceptions import AjoutSeulError
from apps.communication.models import (
    CategorieDestinataire,
    DestinataireDiffusion,
    Diffusion,
    EvenementRapport,
    Rapport,
    RapportProvisoire,
    ReponseRapport,
    StatutRapport,
    TypeEvenementRapport,
)
from apps.constats.models import Constat
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import MissionFigeeError
from apps.missions.models import Mission, StatutMission
from tests.communication.factories import (
    DestinataireFactory,
    RapportFactory,
    RapportProvisoireFactory,
    ReponseRapportFactory,
    creer_diffusion,
)
from tests.factories import make_user

pytestmark = pytest.mark.django_db


def test_un_seul_rapport_actif_par_mission(mission_en_communication: Mission) -> None:
    premier = RapportFactory(mission=mission_en_communication)
    with pytest.raises(IntegrityError), transaction.atomic():
        RapportFactory(mission=mission_en_communication, numero_version=2)
    # Supprimé logiquement : le rapport ne compte plus, mais son numéro n'est jamais réattribué.
    premier.soft_delete(make_user())
    with pytest.raises(IntegrityError), transaction.atomic():
        RapportFactory(mission=mission_en_communication, numero_version=1)
    RapportFactory(mission=mission_en_communication, numero_version=2)


def test_rapport_remplace_ne_compte_pas_comme_actif(mission_en_communication: Mission) -> None:
    remplace = RapportFactory(
        mission=mission_en_communication, fige=True, statut=StatutRapport.REMPLACE
    )
    corrige = RapportFactory(
        mission=mission_en_communication, numero_version=2, corrige_de=remplace
    )
    assert corrige.corrige_de_id == remplace.pk
    with pytest.raises(IntegrityError), transaction.atomic():
        RapportFactory(mission=mission_en_communication, numero_version=3)


def test_empreinte_obligatoire_des_soumis_valides_diffuses(
    mission_en_communication: Mission,
) -> None:
    for statut in (StatutRapport.SOUMIS, StatutRapport.VALIDE, StatutRapport.DIFFUSE):
        with pytest.raises(IntegrityError), transaction.atomic():
            RapportFactory(mission=mission_en_communication, statut=statut)
        with pytest.raises(IntegrityError), transaction.atomic():
            RapportFactory(mission=mission_en_communication, statut=statut, empreinte_soumise="xyz")
    RapportFactory(mission=mission_en_communication)  # BROUILLON : empreinte vide permise


def test_provisoire_et_diffusion_immuables(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication, fige=True)
    provisoire = RapportProvisoireFactory(rapport=rapport)
    diffusion = creer_diffusion(rapport)
    for objet, modele, champ, valeur in (
        (provisoire, RapportProvisoire, "date_limite_reponses", date(2027, 1, 1)),
        (diffusion, Diffusion, "message", "Autre message"),
    ):
        setattr(objet, champ, valeur)
        with pytest.raises(AjoutSeulError):
            objet.save()
        with pytest.raises(AjoutSeulError):
            objet.save(update_fields=[champ])
        with pytest.raises(AjoutSeulError):
            objet.soft_delete(make_user())
        with pytest.raises(AjoutSeulError):
            modele.objects.filter(pk=objet.pk).update(**{champ: valeur})
        with pytest.raises(AjoutSeulError):
            modele.all_objects.bulk_update([objet], [champ])
        with pytest.raises(AjoutSeulError):
            modele.all_objects.bulk_create(
                [objet], update_conflicts=True, update_fields=[champ], unique_fields=["id"]
            )
        assert modele.objects.count() == 1


def test_provisoire_empreinte_et_numero(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication)
    RapportProvisoireFactory(rapport=rapport)
    with pytest.raises(IntegrityError), transaction.atomic():
        RapportProvisoireFactory(rapport=rapport)  # même numéro
    with pytest.raises(IntegrityError), transaction.atomic():
        RapportProvisoireFactory(rapport=rapport, numero=2, empreinte="pas-un-sha")
    RapportProvisoireFactory(rapport=rapport, numero=2)


def test_diffusion_une_seule_par_rapport(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication, fige=True)
    creer_diffusion(rapport)
    with pytest.raises(IntegrityError), transaction.atomic():
        creer_diffusion(rapport)


def test_reponse_ajout_seul(mission_en_communication: Mission, constat: Constat) -> None:
    provisoire = RapportProvisoireFactory(rapport=RapportFactory(mission=mission_en_communication))
    reponse = ReponseRapportFactory(provisoire=provisoire, constat=constat)
    reponse.commentaire = "modifié"
    with pytest.raises(AjoutSeulError):
        reponse.save()
    with pytest.raises(AjoutSeulError):
        reponse.soft_delete(make_user())
    with pytest.raises(AjoutSeulError):
        ReponseRapport.objects.filter(pk=reponse.pk).update(commentaire="x")
    with pytest.raises(AjoutSeulError):
        ReponseRapport.all_objects.bulk_update([reponse], ["commentaire"])
    with pytest.raises(AjoutSeulError):
        ReponseRapport.all_objects.bulk_create(
            [reponse], update_conflicts=True, update_fields=["commentaire"], unique_fields=["id"]
        )
    assert ReponseRapport.objects.count() == 1


def test_reponse_commentaire_non_vide(mission_en_communication: Mission, constat: Constat) -> None:
    provisoire = RapportProvisoireFactory(rapport=RapportFactory(mission=mission_en_communication))
    for vide in ("", "   "):
        with pytest.raises(IntegrityError), transaction.atomic():
            ReponseRapportFactory(provisoire=provisoire, constat=constat, commentaire=vide)


def test_reponse_gelee_par_xvi_close(mission_en_communication: Mission, constat: Constat) -> None:
    from apps.missions.exceptions import EtapeCloseError
    from apps.missions.models import StatutEtape
    from tests.missions.conftest import forcer_etapes

    provisoire = RapportProvisoireFactory(rapport=RapportFactory(mission=mission_en_communication))
    ReponseRapportFactory(provisoire=provisoire, constat=constat)
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError) as exc:
        ReponseRapportFactory(provisoire=provisoire, constat=constat)
    assert exc.value.romain == "XVI"


def test_reponse_meme_mission(mission_en_communication: Mission) -> None:
    from tests.factories import MissionFactory

    provisoire = RapportProvisoireFactory(rapport=RapportFactory(mission=mission_en_communication))
    autre = MissionFactory()
    with pytest.raises(RegleMetierError):
        ReponseRapportFactory(provisoire=provisoire, mission=autre)


def test_evenement_ajout_seul(rapport_brouillon: Rapport) -> None:
    ev = EvenementRapport.journaliser(
        rapport_brouillon,
        TypeEvenementRapport.CREE,
        par=make_user(),
        statut_avant="",
    )
    assert ev.statut_apres == StatutRapport.BROUILLON
    ev.motif = "x"
    with pytest.raises(AjoutSeulError):
        ev.save()
    with pytest.raises(AjoutSeulError):
        ev.soft_delete(make_user())
    with pytest.raises(AjoutSeulError):
        EvenementRapport.objects.filter(pk=ev.pk).update(motif="x")
    with pytest.raises(AjoutSeulError):
        EvenementRapport.all_objects.bulk_update([ev], ["motif"])


def test_destinataire_interne_ou_externe(rapport_brouillon: Rapport) -> None:
    DestinataireFactory(rapport=rapport_brouillon)
    DestinataireFactory(
        rapport=rapport_brouillon,
        utilisateur=None,
        nom_externe="Cour des comptes",
        qualite="Autorité de contrôle",
        categorie=CategorieDestinataire.AUTRE,
    )
    with pytest.raises(IntegrityError), transaction.atomic():  # ni l'un ni l'autre
        DestinataireFactory(rapport=rapport_brouillon, utilisateur=None)
    with pytest.raises(IntegrityError), transaction.atomic():  # les deux
        DestinataireFactory(rapport=rapport_brouillon, nom_externe="Cour des comptes")


def test_destinataire_unique_actif_par_utilisateur(rapport_brouillon: Rapport) -> None:
    premier = DestinataireFactory(rapport=rapport_brouillon)
    with pytest.raises(IntegrityError), transaction.atomic():
        DestinataireFactory(rapport=rapport_brouillon, utilisateur=premier.utilisateur)
    premier.soft_delete(make_user())
    DestinataireFactory(rapport=rapport_brouillon, utilisateur=premier.utilisateur)


def test_destinataires_figes_apres_diffusion_sauf_suivi(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication, fige=True)
    interne = DestinataireFactory(rapport=rapport)
    externe = DestinataireFactory(
        rapport=rapport, utilisateur=None, nom_externe="Bailleur", categorie="AUTRE"
    )
    # Avant la diffusion : modification et suppression permises, suivi interdit.
    interne.qualite = "Directeur général"
    interne.save()
    with pytest.raises(RegleMetierError):
        DestinataireDiffusion.objects.filter(pk=interne.pk).update(notifie_le=timezone.now())
    # Le rapport est diffusé (état posé par une écriture directe : test de la garde seule).
    Rapport.all_objects.filter(pk=rapport.pk).update(statut=StatutRapport.VALIDE)
    Rapport.all_objects.filter(pk=rapport.pk).update(statut=StatutRapport.DIFFUSE)
    with pytest.raises(RegleMetierError):
        DestinataireFactory(rapport=rapport)  # ajout
    interne.qualite = "Autre"
    with pytest.raises(RegleMetierError):
        interne.save()  # modification
    with pytest.raises(RegleMetierError):
        DestinataireDiffusion.objects.filter(pk=interne.pk).update(qualite="x")
    with pytest.raises(RegleMetierError):
        DestinataireDiffusion.all_objects.bulk_update([interne], ["qualite"])
    with pytest.raises(RegleMetierError):
        externe.soft_delete(make_user())  # suppression
    with pytest.raises(RegleMetierError):  # changement de rapport
        DestinataireDiffusion.objects.filter(pk=interne.pk).update(
            rapport=RapportFactory(
                mission=mission_en_communication,
                numero_version=2,
                fige=True,
                statut=StatutRapport.REMPLACE,
            )
        )
    # Suivi : permis, par les champs de suivi seulement.
    interne = DestinataireDiffusion.objects.get(pk=interne.pk)
    interne.notifie_le = timezone.now()
    interne.save(update_fields=["notifie_le"])
    DestinataireDiffusion.objects.filter(pk=externe.pk).update(
        remis_hors_plateforme_le=timezone.now()
    )
    assert DestinataireDiffusion.objects.get(pk=externe.pk).remis_hors_plateforme_le is not None


@pytest.mark.parametrize("app", ["communication"])
def test_mission_suspendue_refuse_toutes_ecritures_lot7(
    app: str, mission_en_communication: Mission, constat: Constat
) -> None:
    rapport = RapportFactory(mission=mission_en_communication, fige=True)
    soumis = rapport
    provisoire = RapportProvisoireFactory(rapport=rapport)
    reponse = ReponseRapportFactory(provisoire=provisoire, constat=constat)
    destinataire = DestinataireFactory(rapport=rapport)
    Mission.objects.filter(pk=mission_en_communication.pk).update(statut=StatutMission.SUSPENDUE)
    rapport.synthese = "x"
    destinataire.qualite = "x"
    appels = (
        lambda: RapportFactory(mission=mission_en_communication, numero_version=3),
        lambda: rapport.save(),
        lambda: rapport.soft_delete(make_user()),
        lambda: Rapport.objects.filter(pk=rapport.pk).update(synthese="y"),
        lambda: Rapport.all_objects.bulk_update([rapport], ["synthese"]),
        lambda: Rapport.objects.filter(pk=soumis.pk).update(statut=StatutRapport.RENVOYE),
        lambda: RapportProvisoireFactory(rapport=rapport, numero=2),
        lambda: ReponseRapportFactory(provisoire=provisoire, constat=constat),
        lambda: ReponseRapport.all_objects.bulk_create([reponse]),
        lambda: EvenementRapport.journaliser(
            rapport, TypeEvenementRapport.SOUMIS, par=make_user(), statut_avant="BROUILLON"
        ),
        lambda: DestinataireFactory(rapport=rapport),
        lambda: destinataire.save(),
        lambda: DestinataireDiffusion.objects.filter(pk=destinataire.pk).update(qualite="z"),
        lambda: destinataire.soft_delete(make_user()),
        lambda: creer_diffusion(soumis),
    )
    for appel in appels:
        with pytest.raises(MissionFigeeError):
            appel()
    assert Rapport.objects.get(pk=soumis.pk).statut == StatutRapport.SOUMIS

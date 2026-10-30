# ruff: noqa: F811
import pytest
from django.core.exceptions import PermissionDenied

from apps.communication.models import DestinataireDiffusion, EvenementRapport, Rapport
from apps.communication.services.correction import emettre_rapport_corrige
from apps.communication.services.diffusion import (
    ajouter_destinataire,
    diffuser,
    retirer_destinataire,
)
from apps.communication.services.soumission import soumettre_rapport
from apps.communication.services.validation import renvoyer_rapport, valider_rapport
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission
from apps.users.models import User
from tests.communication.support_t8 import (  # noqa: F401
    admin,
    creer_version,
    dg,
    rapport_diffuse,
    rapport_soumis_reel,
    rapport_valide,
)


def _etat_etapes(rapport: Rapport) -> dict[int, str]:
    return dict(
        EtapeMission.objects.filter(mission_id=rapport.mission_id).values_list("numero", "statut")
    )


def test_rapport_corrige_recopie_les_destinataires_et_remplace(
    rapport_diffuse: Rapport, rai: User, dg: User
) -> None:
    corrige = emettre_rapport_corrige(rapport_diffuse, motif=" Erreur matérielle ", by=rai)
    ancien = Rapport.all_objects.get(pk=rapport_diffuse.pk)
    assert ancien.statut == "REMPLACE"
    assert corrige.statut == "BROUILLON" and corrige.numero_version == 2
    assert corrige.corrige_de == ancien and corrige.motif_correction == "Erreur matérielle"
    assert corrige.synthese == ancien.synthese and corrige.conclusion == ancien.conclusion
    assert corrige.cycle == 0 and corrige.confirmation_validation_id is None
    copie = {
        (d.utilisateur_id, d.nom_externe, d.categorie): d
        for d in DestinataireDiffusion.objects.filter(rapport=corrige)
    }
    origine = {
        (d.utilisateur_id, d.nom_externe, d.categorie)
        for d in DestinataireDiffusion.objects.filter(rapport=ancien)
    }
    assert set(copie) == origine and (dg.pk, "", "DG") in copie
    assert all(
        d.notifie_le is None
        and d.premiere_consultation_le is None
        and d.accuse_reception_le is None
        for d in copie.values()
    )
    types = list(EvenementRapport.objects.filter(rapport=ancien).values_list("type", flat=True))
    assert types[-1] == "CORRIGE"
    assert EvenementRapport.objects.filter(rapport=corrige, type="CREE").exists()


def test_recopies_non_retirables_ajout_permis(
    rapport_diffuse: Rapport, rai: User, dg: User
) -> None:
    corrige = emettre_rapport_corrige(rapport_diffuse, motif="Erreur.", by=rai)
    recopie = DestinataireDiffusion.objects.get(rapport=corrige, utilisateur=dg)
    with pytest.raises(RegleMetierError, match="ne peut pas être retiré"):
        retirer_destinataire(recopie, by=rai)
    nouveau = ajouter_destinataire(corrige, by=rai, nom_externe="Nouveau")
    retirer_destinataire(nouveau, by=rai)  # un ajout propre au rapport corrigé se retire


def test_rapport_corrige_ne_touche_pas_aux_etapes(rapport_diffuse: Rapport, rai: User) -> None:
    avant = _etat_etapes(rapport_diffuse)
    corrige = emettre_rapport_corrige(rapport_diffuse, motif="Erreur.", by=rai)
    assert _etat_etapes(corrige) == avant and avant[18] == "VALIDEE"
    assert Mission.objects.get(pk=corrige.mission_id).statut == "RAPPORT_DIFFUSE"


def test_chaine_du_rapport_corrige_sans_etapes(
    rapport_diffuse: Rapport, rai: User, chef: User
) -> None:
    avant = _etat_etapes(rapport_diffuse)
    corrige = emettre_rapport_corrige(rapport_diffuse, motif="Erreur.", by=rai)
    soumis = soumettre_rapport(corrige, by=chef)
    assert soumis.statut == "SOUMIS" and soumis.cycle == 1
    renvoye = renvoyer_rapport(soumis, motif="Complétez.", by=rai)
    assert renvoye.statut == "RENVOYE"
    soumis = soumettre_rapport(renvoye, by=chef)
    valide = valider_rapport(soumis, by=rai)
    assert valide.statut == "VALIDE" and valide.confirmation_validation is not None
    assert valide.instantane_soumis["rapport"]["corrige_de"] == 1
    version = creer_version(valide)
    d = diffuser(valide, message="Version corrigée.", by=rai)
    assert d.version_rapport == version
    assert d.version_rapport.document.numero.endswith("-02")
    assert Rapport.objects.get(pk=valide.pk).statut == "DIFFUSE"
    assert _etat_etapes(valide) == avant
    assert Mission.objects.get(pk=valide.mission_id).statut == "RAPPORT_DIFFUSE"
    # Les confirmations du rapport remplacé et du corrigé sont distinctes.
    ancien = Rapport.all_objects.get(pk=rapport_diffuse.pk)
    assert ancien.confirmation_validation_id != valide.confirmation_validation_id
    assert d.rapport_id != ancien.diffusion.rapport_id


def test_emission_reservee_au_rai_avec_motif(
    rapport_diffuse: Rapport, rai: User, chef: User, admin: User
) -> None:
    for intrus in (chef, admin):
        with pytest.raises(PermissionDenied):
            emettre_rapport_corrige(rapport_diffuse, motif="Erreur.", by=intrus)
    with pytest.raises(RegleMetierError, match="motif"):
        emettre_rapport_corrige(rapport_diffuse, motif="   ", by=rai)
    assert Rapport.objects.get(pk=rapport_diffuse.pk).statut == "DIFFUSE"


def test_emission_refusee_si_non_diffuse(rapport_valide: Rapport, rai: User) -> None:
    with pytest.raises(RegleMetierError, match="diffusé"):
        emettre_rapport_corrige(rapport_valide, motif="Erreur.", by=rai)


def test_un_rapport_remplace_ne_se_corrige_plus(rapport_diffuse: Rapport, rai: User) -> None:
    emettre_rapport_corrige(rapport_diffuse, motif="Erreur.", by=rai)
    with pytest.raises(RegleMetierError, match="diffusé"):
        emettre_rapport_corrige(rapport_diffuse, motif="Encore.", by=rai)
    assert Rapport.objects.filter(mission_id=rapport_diffuse.mission_id).count() == 2

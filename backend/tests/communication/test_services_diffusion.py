# ruff: noqa: F811
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection

from apps.communication import signals
from apps.communication.models import (
    CategorieDestinataire,
    DestinataireDiffusion,
    Diffusion,
    EvenementRapport,
    Rapport,
    StatutRapport,
)
from apps.communication.services.diffusion import (
    accuser_reception,
    ajouter_destinataire,
    diffuser,
    marquer_remis_hors_plateforme,
    modifier_destinataire,
    noter_consultation,
    preremplir_destinataires,
    retirer_destinataire,
)
from apps.core.exceptions import RegleMetierError
from apps.core.gardes_sql import maintenance
from apps.missions.models import EtapeMission, Mission
from apps.missions.services import aujourd_hui
from apps.signatures.parametres import modifier_mode
from apps.users.models import Role, User
from tests.communication.support_t8 import (  # noqa: F401
    admin,
    creer_version,
    dg,
    rapport_diffuse,
    rapport_soumis_reel,
    rapport_valide,
    signataire_factice,
)
from tests.factories import make_user
from tests.signatures.fakes import SignataireFactice


def test_chaine_diffusion_fige_les_versions(rapport_valide: Rapport, rai: User) -> None:
    final = creer_version(rapport_valide)
    note = creer_version(rapport_valide, "NOTE_SYNTHETIQUE")
    d = diffuser(rapport_valide, message="  Pour information.  ", by=rai)
    assert d.version_rapport == final and d.version_note == note
    assert d.message == "Pour information." and d.diffusee_par == rai
    r = Rapport.objects.get(pk=rapport_valide.pk)
    assert r.statut == StatutRapport.DIFFUSE
    assert Mission.objects.get(pk=r.mission_id).statut == "RAPPORT_DIFFUSE"
    evenement = EvenementRapport.objects.get(rapport=r, type="DIFFUSE")
    assert (evenement.statut_avant, evenement.statut_apres) == ("VALIDE", "DIFFUSE")
    assert all(x.notifie_le is not None for x in DestinataireDiffusion.objects.filter(rapport=r))


def test_diffusion_exige_version_pdf_prete(rapport_valide: Rapport, rai: User) -> None:
    with pytest.raises(RegleMetierError, match="pas encore généré"):
        diffuser(rapport_valide, by=rai)
    creer_version(rapport_valide, pdf=False)
    with pytest.raises(RegleMetierError, match="pas encore généré"):
        diffuser(rapport_valide, by=rai)
    creer_version(rapport_valide, docx=False)
    with pytest.raises(RegleMetierError, match="pas encore généré"):
        diffuser(rapport_valide, by=rai)
    assert Rapport.objects.get(pk=rapport_valide.pk).statut == StatutRapport.VALIDE


def test_diffusion_ignore_une_version_d_un_autre_cycle(rapport_valide: Rapport, rai: User) -> None:
    creer_version(rapport_valide, confirmation_id=None)
    with pytest.raises(RegleMetierError, match="pas encore généré"):
        diffuser(rapport_valide, by=rai)


def test_diffusion_reservee_au_rai(
    rapport_valide: Rapport, chef: User, admin: User, dg: User
) -> None:
    creer_version(rapport_valide)
    for intrus in (chef, admin, dg):
        with pytest.raises(PermissionDenied):
            diffuser(rapport_valide, by=intrus)
    assert not Diffusion.objects.exists()


def test_diffusion_exige_un_rapport_valide(rapport_soumis_reel: Rapport, rai: User) -> None:
    with pytest.raises(RegleMetierError, match="validé"):
        diffuser(rapport_soumis_reel, by=rai)


def test_diffusion_exige_un_destinataire(rapport_valide: Rapport, rai: User) -> None:
    creer_version(rapport_valide)
    for d in list(DestinataireDiffusion.objects.filter(rapport=rapport_valide)):
        retirer_destinataire(d, by=rai)
    with pytest.raises(RegleMetierError, match="au moins un destinataire"):
        diffuser(rapport_valide, by=rai)


def test_diffusion_refuse_une_confirmation_alteree(rapport_valide: Rapport, rai: User) -> None:
    creer_version(rapport_valide)
    with maintenance(), connection.cursor() as c:
        c.execute(
            "UPDATE signatures_confirmation SET texte = 'Falsifié' WHERE id = %s",
            [rapport_valide.confirmation_validation_id],
        )
    with pytest.raises(RegleMetierError, match="intégrité"):
        diffuser(rapport_valide, by=rai)


def test_diffusion_deux_fois_refusee(rapport_diffuse: Rapport, rai: User) -> None:
    with pytest.raises(RegleMetierError, match="validé"):
        diffuser(rapport_diffuse, by=rai)
    assert Diffusion.objects.filter(rapport=rapport_diffuse).count() == 1


def test_porte_signature_electronique(
    rapport_soumis_reel: Rapport, rai: User, admin: User, signataire_factice: SignataireFactice
) -> None:
    from apps.communication.services.validation import valider_rapport

    modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION_ET_SIGNATURE", by=admin)
    r = valider_rapport(rapport_soumis_reel, by=rai)
    version = creer_version(r)
    with pytest.raises(RegleMetierError, match="signé électroniquement"):
        diffuser(r, by=rai)
    signataire_factice.signer(version)
    assert diffuser(r, by=rai).rapport.statut == StatutRapport.DIFFUSE


def test_porte_signature_sans_signataire_enregistre_echoue_ferme(
    rapport_soumis_reel: Rapport, rai: User, admin: User, signataire_factice: SignataireFactice
) -> None:
    from apps.communication.services.validation import valider_rapport
    from apps.signatures.electronique import enregistrer_signataire_electronique

    modifier_mode("VALIDATION_RAPPORT", mode="SIGNATURE_ELECTRONIQUE", by=admin)
    r = valider_rapport(rapport_soumis_reel, by=rai)
    version = creer_version(r)
    signataire_factice.signer(version)
    enregistrer_signataire_electronique(None)
    with pytest.raises(RegleMetierError, match="signé électroniquement"):
        diffuser(r, by=rai)


def test_diffusion_mail_sans_piece_jointe(
    rapport_valide: Rapport, rai: User, django_capture_on_commit_callbacks: Any
) -> None:
    creer_version(rapport_valide)
    recus: list[dict[str, Any]] = []
    signals.rapport_diffuse.connect(
        lambda **kw: recus.append(kw), dispatch_uid="t8-mail", weak=False
    )
    try:
        with patch("apps.communication.services.diffusion.send_mail_task") as tache:
            with django_capture_on_commit_callbacks(execute=False) as callbacks:
                d = diffuser(rapport_valide, message="Bonjour.", by=rai)
            tache.delay.assert_not_called()
            assert recus == []  # jamais avant la validation de la transaction
            for callback in callbacks:
                callback()
    finally:
        signals.rapport_diffuse.disconnect(dispatch_uid="t8-mail")
    internes = DestinataireDiffusion.objects.filter(
        rapport=rapport_valide, utilisateur__isnull=False
    )
    assert tache.delay.call_count == internes.count() >= 1
    for appel in tache.delay.call_args_list:
        a_qui, sujet, modele, contexte = appel.args
        assert len(a_qui) == 1 and modele == "diffusion_rapport" and "Rapport" in sujet
        assert set(contexte) == {
            "nom",
            "reference",
            "titre",
            "message",
            "corrige",
            "motif_correction",
            "lien",
        }
        assert contexte["message"] == "Bonjour."
    assert len(recus) == 1
    assert recus[0]["rapport"].pk == rapport_valide.pk and recus[0]["diffusion"] == d
    assert recus[0]["par"] == rai and recus[0]["sender"] is Rapport


def test_gabarit_du_mail_se_rend() -> None:
    from django.template.loader import render_to_string

    contexte = {
        "nom": "A",
        "reference": "DAI/2026/M01",
        "titre": "Titre",
        "message": "Msg",
        "corrige": True,
        "motif_correction": "Erreur",
        "lien": "https://x/rapport",
    }
    for extension in ("txt", "html"):
        rendu = render_to_string(f"email/diffusion_rapport.{extension}", contexte)
        assert "DAI/2026/M01" in rendu and "Erreur" in rendu and "https://x/rapport" in rendu


# --------------------------------------------------------------------------- liste


def test_preremplissage_idempotent_et_actifs_seulement(
    rapport_valide: Rapport, rai: User, dg: User
) -> None:
    make_user(Role.DG, is_active=False)
    avant = DestinataireDiffusion.objects.filter(rapport=rapport_valide).count()
    assert preremplir_destinataires(rapport_valide, by=rai) == []
    assert DestinataireDiffusion.objects.filter(rapport=rapport_valide).count() == avant
    assert not DestinataireDiffusion.objects.filter(
        rapport=rapport_valide, utilisateur__is_active=False
    ).exists()


def test_un_destinataire_retire_n_est_pas_rajoute(
    rapport_valide: Rapport, rai: User, dg: User
) -> None:
    d = DestinataireDiffusion.objects.get(rapport=rapport_valide, utilisateur=dg)
    retirer_destinataire(d, by=rai)
    assert preremplir_destinataires(rapport_valide, by=rai) == []


def test_ajouter_modifier_retirer(rapport_valide: Rapport, rai: User) -> None:
    externe = ajouter_destinataire(
        rapport_valide, by=rai, nom_externe=" Cour des comptes ", qualite="Tutelle"
    )
    assert externe.nom_externe == "Cour des comptes" and externe.categorie == "AUTRE"
    modifie = modifier_destinataire(externe, by=rai, qualite="Autorité de tutelle")
    assert modifie.qualite == "Autorité de tutelle"
    with pytest.raises(RegleMetierError):
        modifier_destinataire(externe, by=rai, utilisateur=rai)
    interne = ajouter_destinataire(rapport_valide, by=rai, utilisateur=rai)
    assert interne.utilisateur == rai
    with pytest.raises(RegleMetierError, match="déjà"):
        ajouter_destinataire(rapport_valide, by=rai, utilisateur=rai)
    with pytest.raises(RegleMetierError, match="pas les deux"):
        ajouter_destinataire(rapport_valide, by=rai, utilisateur=rai, nom_externe="X")
    with pytest.raises(RegleMetierError):
        ajouter_destinataire(rapport_valide, by=rai)
    with pytest.raises(RegleMetierError, match="inactif"):
        ajouter_destinataire(
            rapport_valide, by=rai, utilisateur=make_user(Role.DG, is_active=False)
        )
    retirer_destinataire(externe, by=rai)
    assert not DestinataireDiffusion.objects.filter(pk=externe.pk).exists()


def test_liste_reservee_au_rai(rapport_valide: Rapport, chef: User, dg: User) -> None:
    d = DestinataireDiffusion.objects.get(rapport=rapport_valide, utilisateur=dg)
    with pytest.raises(PermissionDenied):
        ajouter_destinataire(rapport_valide, by=chef, nom_externe="X")
    with pytest.raises(PermissionDenied):
        modifier_destinataire(d, by=chef, qualite="X")
    with pytest.raises(PermissionDenied):
        retirer_destinataire(d, by=chef)


def test_liste_figee_apres_diffusion(rapport_diffuse: Rapport, rai: User, dg: User) -> None:
    d = DestinataireDiffusion.objects.get(rapport=rapport_diffuse, utilisateur=dg)
    with pytest.raises(RegleMetierError, match="diffusé"):
        ajouter_destinataire(rapport_diffuse, by=rai, nom_externe="X")
    with pytest.raises(RegleMetierError, match="diffusé"):
        modifier_destinataire(d, by=rai, qualite="X")
    with pytest.raises(RegleMetierError, match="diffusé"):
        retirer_destinataire(d, by=rai)
    with pytest.raises(RegleMetierError, match="diffusé"):
        preremplir_destinataires(rapport_diffuse, by=rai)


# --------------------------------------------------------------------------- suivi


def test_suivi_consultation_et_accuse(rapport_diffuse: Rapport, dg: User, rai: User) -> None:
    d = DestinataireDiffusion.objects.get(rapport=rapport_diffuse, utilisateur=dg)
    assert d.premiere_consultation_le is None and d.accuse_reception_le is None
    noter_consultation(rapport_diffuse, dg)
    d.refresh_from_db()
    premiere = d.premiere_consultation_le
    assert premiere is not None
    noter_consultation(rapport_diffuse, dg)
    d.refresh_from_db()
    assert d.premiere_consultation_le == premiere
    noter_consultation(rapport_diffuse, rai)  # non destinataire : sans effet ni erreur
    accuser_reception(rapport_diffuse, by=dg)
    d.refresh_from_db()
    accuse = d.accuse_reception_le
    assert accuse is not None
    accuser_reception(rapport_diffuse, by=dg)
    d.refresh_from_db()
    assert d.accuse_reception_le == accuse


def test_accuse_sans_consultation_pose_la_consultation(rapport_diffuse: Rapport, dg: User) -> None:
    accuser_reception(rapport_diffuse, by=dg)
    d = DestinataireDiffusion.objects.get(rapport=rapport_diffuse, utilisateur=dg)
    assert d.premiere_consultation_le == d.accuse_reception_le


def test_accuse_refuse_au_non_destinataire(
    rapport_diffuse: Rapport, rai: User, admin: User
) -> None:
    for intrus in (rai, admin, make_user(Role.DG)):
        with pytest.raises(PermissionDenied):
            accuser_reception(rapport_diffuse, by=intrus)


def test_accuse_refuse_avant_diffusion(rapport_valide: Rapport, dg: User) -> None:
    with pytest.raises(RegleMetierError, match="n'est pas diffusé"):
        accuser_reception(rapport_valide, by=dg)
    noter_consultation(rapport_valide, dg)
    d = DestinataireDiffusion.objects.get(rapport=rapport_valide, utilisateur=dg)
    assert d.premiere_consultation_le is None


def test_externe_remis_hors_plateforme(rapport_valide: Rapport, rai: User, chef: User) -> None:
    creer_version(rapport_valide)
    externe = ajouter_destinataire(rapport_valide, by=rai, nom_externe="Tutelle")
    with pytest.raises(RegleMetierError, match="n'est pas diffusé"):
        marquer_remis_hors_plateforme(externe, le=aujourd_hui(), by=rai)
    diffuser(rapport_valide, by=rai)
    externe.refresh_from_db()
    assert externe.notifie_le is None
    with pytest.raises(PermissionDenied):
        marquer_remis_hors_plateforme(externe, le=aujourd_hui(), by=chef)
    for hors_borne in (aujourd_hui() + timedelta(days=1), aujourd_hui() - timedelta(days=1)):
        with pytest.raises(RegleMetierError, match="date de remise"):
            marquer_remis_hors_plateforme(externe, le=hors_borne, by=rai)
    d = marquer_remis_hors_plateforme(externe, le=aujourd_hui(), by=rai)
    assert d.remis_hors_plateforme_le is not None
    interne = DestinataireDiffusion.objects.filter(rapport=rapport_valide, utilisateur=chef).get()
    with pytest.raises(RegleMetierError, match="externe"):
        marquer_remis_hors_plateforme(interne, le=aujourd_hui(), by=rai)


def test_suivi_n_ouvre_pas_la_liste(rapport_diffuse: Rapport, dg: User) -> None:
    """Après diffusion, seul le suivi s'écrit : la catégorie reste figée même par le modèle."""
    d = DestinataireDiffusion.objects.get(rapport=rapport_diffuse, utilisateur=dg)
    d.categorie = CategorieDestinataire.AUTRE
    with pytest.raises(RegleMetierError):
        d.save()


def test_etapes_inchangees_apres_diffusion_initiale(rapport_diffuse: Rapport) -> None:
    statuts = dict(
        EtapeMission.objects.filter(
            mission_id=rapport_diffuse.mission_id, numero__gte=15
        ).values_list("numero", "statut")
    )
    assert statuts[18] == "VALIDEE" and statuts[15] == "TERMINEE"

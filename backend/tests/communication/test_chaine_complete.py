# ruff: noqa: F811
"""Chaîne complète : soumission, validation, diffusion (D9, D11)."""

import pytest

from apps.communication.models import Rapport
from apps.communication.services.diffusion import diffuser
from apps.communication.services.soumission import soumettre_rapport
from apps.communication.services.validation import valider_rapport
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission
from apps.signatures.parametres import modifier_mode
from apps.signatures.services import verifier
from apps.users.models import User
from tests.communication.support_t8 import (  # noqa: F401
    XV_A_XVII,
    admin,
    creer_version,
    dg,
    rapport_soumis_reel,
    signataire_factice,
)
from tests.missions.conftest import forcer_etapes
from tests.signatures.fakes import SignataireFactice


def test_chaine_soumission_validation_diffusion(
    rapport_redige: Rapport, chef: User, rai: User, dg: User
) -> None:
    forcer_etapes(rapport_redige.mission, XV_A_XVII)
    soumis = soumettre_rapport(rapport_redige, by=chef)
    r = valider_rapport(soumis, by=rai)
    assert r.confirmation_validation is not None and verifier(r.confirmation_validation)
    assert r.confirmation_validation.donnees["empreinte_soumise"] == r.empreinte_soumise
    creer_version(r)
    d = diffuser(r, by=rai)
    assert d.version_rapport.confirmation_id == r.confirmation_validation_id
    assert Mission.objects.get(pk=r.mission_id).statut == "RAPPORT_DIFFUSE"


def test_porte_diffusion_signature_electronique(
    rapport_soumis_reel: Rapport,
    rai: User,
    admin: User,
    dg: User,
    signataire_factice: SignataireFactice,
) -> None:
    modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION_ET_SIGNATURE", by=admin)
    r = valider_rapport(rapport_soumis_reel, by=rai)
    version = creer_version(r)
    with pytest.raises(RegleMetierError, match="signé électroniquement"):
        diffuser(r, by=rai)
    signataire_factice.signer(version)
    assert diffuser(r, by=rai).rapport.statut == "DIFFUSE"

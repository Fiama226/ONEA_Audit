from io import BytesIO
from typing import Any

import factory

from apps.accomplissement.managers import prochain_numero
from apps.accomplissement.models import (
    FicheDeTest,
    PieceJustificative,
    ProgrammeDeTravail,
    TestPrevu,
)
from apps.accomplissement.stockage import stockage_preuves
from apps.users.models import Role
from tests.factories import MissionFactory, ObjectifAuditFactory, UserFactory


class ProgrammeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgrammeDeTravail

    mission = factory.SubFactory(MissionFactory)
    objectif = factory.SubFactory(ObjectifAuditFactory, mission=factory.SelfAttribute("..mission"))
    techniques = "Entretiens, examen documentaire."
    criteres_preuve = "Preuve suffisante et fiable."


class TestPrevuFactory(factory.django.DjangoModelFactory):
    __test__ = False

    class Meta:
        model = TestPrevu

    mission = factory.SubFactory(MissionFactory)
    programme = factory.SubFactory(ProgrammeFactory, mission=factory.SelfAttribute("..mission"))
    numero = factory.LazyAttribute(lambda o: prochain_numero(TestPrevu, o.mission.pk))
    code = factory.LazyAttribute(lambda o: f"T-{o.numero:02d}")
    libelle = factory.Sequence(lambda n: f"Test {n}")
    objectif_test = "Vérifier le contrôle."
    procedure = "Examiner un échantillon de pièces."
    ordre = factory.LazyAttribute(lambda o: o.numero)


class FicheFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FicheDeTest

    mission = factory.SelfAttribute("test.mission")
    test = factory.SubFactory(TestPrevuFactory)
    auteur = factory.SubFactory(UserFactory, role=Role.AUDITEUR)


class PieceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PieceJustificative

    fiche = factory.SubFactory(FicheFactory)
    mission = factory.SelfAttribute("fiche.mission")
    numero = factory.LazyAttribute(lambda o: prochain_numero(PieceJustificative, o.mission.pk))
    libelle = factory.Sequence(lambda n: f"Pièce {n}")
    type_mime = "application/pdf"
    nom_fichier_original = "piece.pdf"
    deposee_par = factory.SubFactory(UserFactory, role=Role.AUDITEUR)

    @classmethod
    def _create(cls, model_class: type[PieceJustificative], *args: Any, **kwargs: Any) -> Any:
        contenu: bytes = kwargs.pop("contenu", b"%PDF-1.4 preuve")
        stocke = stockage_preuves().deposer(
            BytesIO(contenu), prefixe=f"preuves/{kwargs['mission'].pk}", taille_max=1024 * 1024
        )
        kwargs.update(
            cle_stockage=stocke.cle, empreinte_sha256=stocke.sha256, taille_octets=stocke.taille
        )
        return super()._create(model_class, *args, **kwargs)

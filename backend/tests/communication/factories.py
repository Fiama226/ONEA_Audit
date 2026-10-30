import hashlib
import json
from datetime import date
from typing import Any

import factory
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.communication.models import (
    CategorieDestinataire,
    DestinataireDiffusion,
    Diffusion,
    Rapport,
    RapportProvisoire,
    ReponseRapport,
    StatutRapport,
)
from apps.constats.models import Constat
from apps.documents.models import (
    Document,
    DocumentVersion,
    GabaritDocument,
    StatutGabarit,
    StatutGeneration,
)
from apps.missions.models import Mission
from apps.signatures.models import TypeDocumentSignable
from apps.users.models import Role
from tests.constats.factories import ConstatFactory
from tests.factories import ConfirmationFactory, MissionFactory, UserFactory

INSTANTANE = {"synthese": "Synthèse", "constats": [{"reference": "C-01"}]}


def empreinte_de(instantane: Any) -> str:
    """SHA-256 de la forme canonique d'un instantané."""
    canon = json.dumps(instantane, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


class RapportFactory(factory.django.DjangoModelFactory):
    """Rapport BROUILLON ; `statut=` à la création pour les autres états."""

    class Meta:
        model = Rapport

    class Params:
        fige = factory.Trait(
            statut=StatutRapport.SOUMIS,
            soumis_par=factory.SubFactory(UserFactory, role=Role.AUDITEUR),
            soumis_le=factory.LazyFunction(timezone.now),
            cycle=1,
            instantane_soumis=factory.LazyFunction(lambda: dict(INSTANTANE)),
            empreinte_soumise=factory.LazyAttribute(lambda o: empreinte_de(o.instantane_soumis)),
        )

    mission = factory.SubFactory(MissionFactory)
    numero_version = 1
    synthese = "Synthèse"
    conclusion = "Conclusion"


class RapportProvisoireFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RapportProvisoire

    rapport = factory.SubFactory(RapportFactory)
    mission = factory.SelfAttribute("rapport.mission")
    numero = 1
    transmis_par = factory.SubFactory(UserFactory, role=Role.AUDITEUR)
    date_limite_reponses = date(2026, 12, 31)
    instantane = factory.LazyFunction(lambda: dict(INSTANTANE))
    empreinte = factory.LazyAttribute(lambda o: empreinte_de(o.instantane))


class ReponseRapportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReponseRapport

    provisoire = factory.SubFactory(RapportProvisoireFactory)
    mission = factory.SelfAttribute("provisoire.mission")
    constat = factory.SubFactory(ConstatFactory, mission=factory.SelfAttribute("..mission"))
    auteur = factory.SubFactory(UserFactory, role=Role.AUDITE)
    commentaire = "La direction prend acte et s'engage."
    confirmation = factory.SubFactory(
        ConfirmationFactory,
        objet=factory.SelfAttribute("..provisoire"),
        type_document=TypeDocumentSignable.REPONSE_RAPPORT_PROVISOIRE,
        signataire=factory.SelfAttribute("..auteur"),
    )


class DestinataireFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DestinataireDiffusion

    rapport = factory.SubFactory(RapportFactory)
    mission = factory.SelfAttribute("rapport.mission")
    utilisateur = factory.SubFactory(UserFactory, role=Role.DG)
    categorie = CategorieDestinataire.DG


def version_document(mission: Mission, *, sequence: int = 1) -> DocumentVersion:
    """Version de document minimale (sans fichier) pour pointer une `Diffusion`."""
    code = f"T7D{sequence}"
    auteur = UserFactory(role=Role.RAI)
    gabarit = GabaritDocument.objects.create(
        type_document=code,
        version=1,
        statut=StatutGabarit.ACTIF,
        fichier="gabarits/t.docx",
        nom_original="t.docx",
        taille=1,
        empreinte="a" * 64,
        contrat_version=1,
    )
    document = Document.objects.create(
        type_document=code,
        mission=mission,
        content_type=ContentType.objects.get_for_model(mission),
        object_id=mission.pk,
        numero=f"{mission.reference}/{code}-01",
        annee=2026,
        sequence=sequence,
    )
    version: DocumentVersion = DocumentVersion.objects.create(
        document=document,
        numero_version=1,
        statut=StatutGeneration.PRETE,
        gabarit=gabarit,
        demandee_par=auteur,
        empreinte_contexte="b" * 64,
    )
    return version


def creer_diffusion(rapport: Rapport) -> Diffusion:
    diffusion: Diffusion = Diffusion.objects.create(
        rapport=rapport,
        mission=rapport.mission,
        version_rapport=version_document(rapport.mission),
        diffusee_par=UserFactory(role=Role.RAI),
        message="Rapport diffusé.",
    )
    return diffusion


__all__ = ["Constat", "creer_diffusion", "version_document"]

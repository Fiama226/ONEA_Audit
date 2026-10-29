"""Contrôles de livrables des étapes gérées au lot 3 (D7) ; les lots suivants ajoutent les leurs."""

from collections.abc import Callable, Iterable

from django.contrib.contenttypes.models import ContentType

from apps.signatures.models import Confirmation, TypeDocumentSignable

from ..models import (
    DeclarationIndependance,
    Entretien,
    EtapeMission,
    EvenementEtape,
    Mission,
    Reunion,
    RisqueMission,
    StatutEntretien,
    TypeEvenementEtape,
    TypeReunion,
)

MSG_ORDRE = "L'ordre de mission n'a pas été émis."
Controle = Callable[[EtapeMission], str | None]


def declarations_en_attente(mission_id: object) -> list[str]:
    """Noms des intervenants dont la déclaration d'indépendance n'est pas levée."""
    declarations = DeclarationIndependance.objects.filter(
        affectation__mission_id=mission_id, affectation__deleted_at__isnull=True
    ).select_related("affectation__utilisateur")
    return [
        d.affectation.utilisateur.get_full_name() or d.affectation.utilisateur.username
        for d in declarations
        if not d.levee
    ]


def _ordre_mission(etape: EtapeMission) -> str | None:
    """Ordre émis, et ré-émis (nouvelle confirmation) après toute réouverture de l'étape I."""
    emis = Mission.objects.filter(pk=etape.mission_id, ordre_mission_emis_le__isnull=False).exists()
    if not emis:
        return MSG_ORDRE
    reouverture = (
        EvenementEtape.objects.filter(
            etape__mission_id=etape.mission_id,
            etape__numero=1,
            type=TypeEvenementEtape.ROUVERTE,
        )
        .order_by("-le")
        .values_list("le", flat=True)
        .first()
    )
    if reouverture is None:
        return None
    reemis = Confirmation.objects.filter(
        type_document=TypeDocumentSignable.ORDRE_MISSION,
        content_type=ContentType.objects.get_for_model(Mission),
        object_id=etape.mission_id,
        confirme_le__gt=reouverture,
    ).exists()
    return None if reemis else MSG_ORDRE


def _reunion_tenue(type_reunion: str, libelle: str) -> Controle:
    def controle(etape: EtapeMission) -> str | None:
        tenue = Reunion.objects.filter(
            mission_id=etape.mission_id, type=type_reunion, tenue_le__isnull=False
        ).exists()
        return None if tenue else f"La réunion {libelle} n'est pas marquée comme tenue."

    return controle


def _entretien_planifie(etape: EtapeMission) -> str | None:
    existe = (
        Entretien.objects.filter(mission_id=etape.mission_id)
        .exclude(statut=StatutEntretien.ANNULE)
        .exists()
    )
    return None if existe else "Aucun entretien n'est planifié."


def _declarations(etape: EtapeMission) -> str | None:
    noms = declarations_en_attente(etape.mission_id)
    if noms:
        return f"Déclarations d'indépendance en attente : {', '.join(noms)}."
    return None


def _risque_selectionne(etape: EtapeMission) -> str | None:
    if RisqueMission.objects.filter(mission_id=etape.mission_id).exists():
        return None
    return "Aucun risque n'est sélectionné pour la mission."


CONTROLES: dict[int, list[Controle]] = {
    1: [_ordre_mission],
    2: [
        _reunion_tenue(TypeReunion.OUVERTURE, "d'ouverture"),
        _entretien_planifie,
        _declarations,
    ],
    4: [_risque_selectionne],
    11: [_reunion_tenue(TypeReunion.LANCEMENT, "de lancement")],
}


def enregistrer_controles(numero: int, controles: Iterable[Controle]) -> None:
    """Ajoute des contrôles à l'étape `numero` (idempotent ; plusieurs lots peuvent s'y brancher)"""
    existants = CONTROLES.setdefault(numero, [])
    for controle in controles:
        if controle not in existants:
            existants.append(controle)


def livrables_manquants(etape: EtapeMission) -> list[str]:
    definition = etape.definition
    if definition.lot_livrables > 3 and etape.numero not in CONTROLES:
        return [
            f"Les livrables de l'étape {definition.romain} sont gérés à partir du lot "
            f"{definition.lot_livrables}."
        ]
    messages = (controle(etape) for controle in CONTROLES.get(etape.numero, []))
    return [m for m in messages if m]

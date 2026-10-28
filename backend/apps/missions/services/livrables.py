"""Contrôles de livrables des étapes gérées au lot 3 (D7) ; les lots suivants ajoutent les leurs."""

from collections.abc import Callable

from ..models import (
    DeclarationIndependance,
    Entretien,
    EtapeMission,
    Mission,
    Reunion,
    RisqueMission,
    StatutEntretien,
    TypeReunion,
)

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
    emis = Mission.objects.filter(pk=etape.mission_id, ordre_mission_emis_le__isnull=False).exists()
    return None if emis else "L'ordre de mission n'a pas été émis."


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


def livrables_manquants(etape: EtapeMission) -> list[str]:
    definition = etape.definition
    if definition.lot_livrables > 3:
        return [
            f"Les livrables de l'étape {definition.romain} sont gérés à partir du lot "
            f"{definition.lot_livrables}."
        ]
    messages = (controle(etape) for controle in CONTROLES.get(etape.numero, []))
    return [m for m in messages if m]

import threading
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext

from apps.core.exceptions import RegleMetierError
from apps.referentiel.exceptions import CartographieFigeeError
from apps.referentiel.models import (
    CartographieVersion,
    NiveauRisque,
    ObjetAuditable,
    PrioriteRisque,
    Risque,
    StatutCartographie,
)
from apps.referentiel.services import (
    CelluleMatrice,
    comparer_versions,
    creer_risque,
    creer_version,
    matrice,
    modifier_risque,
    modifier_version,
    supprimer_risque,
    supprimer_version,
    valider_version,
    version_courante,
)
from apps.users.models import User
from tests.factories import make_user
from tests.referentiel import typed

pytestmark = pytest.mark.django_db

MSG_FIGEE = "La cartographie {annee} est validée : elle ne peut plus être modifiée."


def _risque(version: CartographieVersion, rai: User, processus: Any = None, **kw: Any) -> Risque:
    return creer_risque(
        version=version,
        processus=processus or typed.processus(),
        libelle=kw.pop("libelle", "x"),
        probabilite=kw.pop("probabilite", 1),
        impact=kw.pop("impact", 1),
        by=rai,
        **kw,
    )


def test_codes_attribues_par_processus(rai: User) -> None:
    v = typed.version()
    fep, gsi = typed.processus(code="FEP"), typed.processus(code="GSI")
    codes = [
        creer_risque(version=v, processus=p, libelle="x", probabilite=1, impact=1, by=rai).code
        for p in (fep, gsi, fep)
    ]
    assert codes == ["1-FEP-R1", "2-GSI-R1", "3-FEP-R2"]


def test_creer_risque_renseigne_created_by_score_niveau(rai: User) -> None:
    r = _risque(typed.version(), rai, probabilite=4, impact=4)
    assert r.created_by == rai
    assert (r.score, r.niveau) == (16, NiveauRisque.ELEVE)


def test_numero_supprime_jamais_reattribue(rai: User) -> None:
    v = typed.version()
    p = typed.processus(code="FEP")
    r1 = _risque(v, rai, p)
    r2 = _risque(v, rai, p)
    supprimer_risque(r2, by=rai)
    r3 = _risque(v, rai, p)
    assert (r1.numero, r2.numero, r3.numero) == (1, 2, 3)
    assert r3.rang == 3
    assert r3.code == "3-FEP-R3"


def test_priorite_par_defaut_depuis_niveau(rai: User) -> None:
    v = typed.version()
    assert _risque(v, rai, probabilite=3, impact=5).priorite == PrioriteRisque.PRIORITAIRE
    assert _risque(v, rai, probabilite=3, impact=3).priorite == PrioriteRisque.AMELIORATION
    assert _risque(v, rai, probabilite=1, impact=1).priorite == PrioriteRisque.OBSERVATION
    explicite = _risque(v, rai, probabilite=5, impact=5, priorite=PrioriteRisque.OBSERVATION)
    assert explicite.priorite == PrioriteRisque.OBSERVATION


@pytest.mark.parametrize(("p", "i"), [(0, 3), (6, 3), (3, 0), (3, 6)])
def test_probabilite_impact_hors_bornes_refuses(rai: User, p: int, i: int) -> None:
    with pytest.raises(RegleMetierError) as exc:
        _risque(typed.version(), rai, probabilite=p, impact=i)
    assert "probabilite" in exc.value.errors or "impact" in exc.value.errors


def test_objet_d_un_autre_processus_refuse(rai: User) -> None:
    obj = typed.objet()
    with pytest.raises(RegleMetierError) as exc:
        _risque(typed.version(), rai, typed.processus(), objet_auditable=obj)
    assert exc.value.errors["objet_auditable"] == [
        "L'objet auditable doit appartenir au processus du risque."
    ]


def test_modifier_risque_recalcule_et_trace(rai: User) -> None:
    r = _risque(typed.version(), rai, probabilite=2, impact=2)
    r = modifier_risque(r, probabilite=5, impact=5, libelle="Nouveau", by=rai)
    assert (r.score, r.niveau, r.libelle) == (25, NiveauRisque.ELEVE, "Nouveau")
    assert r.updated_by == rai


def test_processus_d_un_risque_non_modifiable(rai: User) -> None:
    r = _risque(typed.version(), rai)
    with pytest.raises(RegleMetierError) as exc:
        modifier_risque(r, processus=typed.processus(), by=rai)
    assert exc.value.errors["processus"] == ["Le processus d'un risque ne peut pas être modifié."]


def test_risque_de_version_validee_immuable_meme_hors_service(rai: User) -> None:
    r = typed.risque()
    valider_version(r.version, by=rai)
    msg = MSG_FIGEE.format(annee=r.version.annee)
    with pytest.raises(CartographieFigeeError, match=msg):
        modifier_risque(r, probabilite=2, by=rai)
    with pytest.raises(CartographieFigeeError):
        supprimer_risque(r, by=rai)
    with pytest.raises(CartographieFigeeError):
        _risque(r.version, rai)
    r.refresh_from_db()
    r.libelle = "contournement"
    with pytest.raises(CartographieFigeeError, match=msg):
        r.save()
    r.refresh_from_db()
    with pytest.raises(CartographieFigeeError):
        r.soft_delete(rai)


def test_erreur_figee_est_une_regle_metier(rai: User) -> None:
    r = typed.risque()
    valider_version(r.version, by=rai)
    with pytest.raises(RegleMetierError):
        modifier_risque(r, libelle="y", by=rai)


def test_valider_version_vide_refuse(rai: User) -> None:
    v = typed.version()
    with pytest.raises(
        RegleMetierError, match="Une cartographie sans risque ne peut pas être validée."
    ):
        valider_version(v, by=rai)
    v.refresh_from_db()
    assert v.statut == StatutCartographie.BROUILLON


def test_valider_version_renseigne_et_gele(rai: User) -> None:
    v = typed.version()
    _risque(v, rai)
    valider_version(v, by=rai)
    v.refresh_from_db()
    assert v.statut == StatutCartographie.VALIDEE
    assert v.validee_par == rai
    assert v.validee_le is not None


def test_version_validee_ni_modifiable_ni_supprimable(rai: User) -> None:
    v = typed.version()
    _risque(v, rai)
    valider_version(v, by=rai)
    msg = MSG_FIGEE.format(annee=v.annee)
    with pytest.raises(CartographieFigeeError, match=msg):
        modifier_version(v, libelle="autre", by=rai)
    with pytest.raises(CartographieFigeeError):
        supprimer_version(v, by=rai)
    with pytest.raises(CartographieFigeeError):
        valider_version(v, by=rai)
    v.refresh_from_db()
    v.libelle = "contournement"
    with pytest.raises(CartographieFigeeError):
        v.save()
    v.refresh_from_db()
    with pytest.raises(CartographieFigeeError):
        v.soft_delete(rai)


def test_modifier_version_brouillon(rai: User) -> None:
    v = modifier_version(typed.version(), libelle="Nouveau", commentaire="c", by=rai)
    assert (v.libelle, v.commentaire, v.updated_by) == ("Nouveau", "c", rai)


def test_annee_deja_prise_422_sur_annee(rai: User) -> None:
    creer_version(annee=2026, libelle="2026", by=rai)
    with pytest.raises(RegleMetierError) as exc:
        creer_version(annee=2026, libelle="bis", by=rai)
    assert exc.value.errors["annee"] == ["Une cartographie existe déjà pour l'année 2026."]


def test_copie_conserve_les_codes_et_ignore_les_supprimes(rai: User) -> None:
    src = typed.version(annee=2025)
    fep = typed.processus(code="FEP")
    obj = typed.objet(processus=fep)
    r1 = _risque(src, rai, fep, probabilite=3, impact=4, objet_auditable=obj, vulnerabilite="v")
    r2 = _risque(src, rai, fep)
    r3 = _risque(src, rai, fep)
    supprimer_risque(r2, by=rai)
    valider_version(src, by=rai)

    nv = creer_version(annee=2026, libelle="2026", source=src, by=rai)
    copies = list(nv.risques.order_by("numero"))
    assert [c.code for c in copies] == [r1.code, r3.code]
    assert (copies[0].numero, copies[0].rang) == (r1.numero, r1.rang)
    assert (copies[0].probabilite, copies[0].impact) == (3, 4)
    assert copies[0].vulnerabilite == "v"
    assert copies[0].objet_auditable == obj
    assert copies[0].created_by == rai
    assert nv.source == src
    assert nv.statut == StatutCartographie.BROUILLON
    assert src.risques.count() == 2


def test_copie_n_reprend_l_objet_que_s_il_est_actif(rai: User) -> None:
    src = typed.version(annee=2025)
    p = typed.processus()
    obj = typed.objet(processus=p)
    r = _risque(src, rai, p, objet_auditable=obj)
    obj.soft_delete(rai)
    nv = creer_version(annee=2026, libelle="2026", source=src, by=rai)
    assert nv.risques.get(code=r.code).objet_auditable is None
    assert ObjetAuditable.all_objects.get(pk=obj.pk).deleted_at is not None


def test_copie_continue_la_numerotation(rai: User) -> None:
    src = typed.version(annee=2025)
    p = typed.processus(code="FEP")
    _risque(src, rai, p)
    nv = creer_version(annee=2026, libelle="2026", source=src, by=rai)
    assert _risque(nv, rai, p).code == "2-FEP-R2"


def test_supprimer_brouillon_supprime_ses_risques(rai: User) -> None:
    v = typed.version()
    r = _risque(v, rai)
    supprimer_version(v, by=rai)
    v.refresh_from_db()
    r.refresh_from_db()
    assert v.deleted_at is not None
    assert r.deleted_at is not None
    assert Risque.objects.filter(version=v).count() == 0


def test_version_courante(rai: User) -> None:
    assert version_courante() is None
    brouillon = typed.version(annee=2030)
    _risque(brouillon, rai)
    assert version_courante() is None
    for annee in (2024, 2025):
        v = typed.version(annee=annee)
        _risque(v, rai)
        valider_version(v, by=rai)
    courante = version_courante()
    assert courante is not None
    assert courante.annee == 2025


def test_validation_historisee(rai: User) -> None:
    v = typed.version()
    _risque(v, rai)
    valider_version(v, by=rai)
    entrees = [
        e
        for e in LogEntry.objects.get_for_object(v).order_by("-timestamp")
        if "statut" in (e.changes or {})
    ]
    assert entrees
    assert entrees[0].changes["statut"] == [
        StatutCartographie.BROUILLON.value,
        StatutCartographie.VALIDEE.value,
    ]
    assert entrees[0].actor == rai


def test_matrice_version_vide_25_cases_a_zero() -> None:
    cases = matrice(typed.version())
    assert len(cases) == 25
    assert all(c.nombre == 0 and c.codes == [] for c in cases)
    assert (cases[0].probabilite, cases[0].impact) == (5, 1)
    assert (cases[4].probabilite, cases[4].impact) == (5, 5)
    assert (cases[-1].probabilite, cases[-1].impact) == (1, 5)
    assert cases[0] == CelluleMatrice(5, 1, 5, "FAIBLE", 0, [])


def test_matrice_regroupe_les_codes(rai: User, django_assert_num_queries: Any) -> None:
    v = typed.version()
    p = typed.processus(code="FEP")
    a = _risque(v, rai, p, probabilite=3, impact=5)
    b = _risque(v, rai, p, probabilite=3, impact=5)
    _risque(v, rai, p, probabilite=1, impact=1)
    mort = _risque(v, rai, p, probabilite=3, impact=5)
    supprimer_risque(mort, by=rai)
    with django_assert_num_queries(1):
        cases = matrice(v)
    cellule = next(c for c in cases if (c.probabilite, c.impact) == (3, 5))
    assert cellule.nombre == 2
    assert cellule.niveau == NiveauRisque.ELEVE
    assert cellule.score == 15
    assert cellule.codes == [a.code, b.code]
    assert sum(c.nombre for c in cases) == 3


def test_comparer_versions(rai: User) -> None:
    p = typed.processus(code="FEP")
    ref = typed.version(annee=2025)
    r1 = _risque(ref, rai, p, probabilite=2, impact=3)
    retire = _risque(ref, rai, p)
    inchange = _risque(ref, rai, p, libelle="stable")
    valider_version(ref, by=rai)

    cible = creer_version(annee=2026, libelle="2026", source=ref, by=rai)
    modifier_risque(cible.risques.get(code=r1.code), probabilite=4, by=rai)
    supprimer_risque(cible.risques.get(code=retire.code), by=rai)
    ajoute = _risque(cible, rai, p)

    comp = comparer_versions(ref, cible)
    assert [r.code for r in comp.ajoutes] == [ajoute.code]
    assert [r.code for r in comp.retires] == [retire.code]
    assert [m.code for m in comp.modifies] == [r1.code]
    ch = comp.modifies[0].changements
    assert ch["probabilite"] == ("2", "4")
    assert ch["score"] == ("6", "12")
    assert ch["niveau"] == ("FAIBLE", "MOYEN")
    assert "libelle" not in ch
    assert inchange.code not in [m.code for m in comp.modifies]


def test_comparer_objet_auditable_par_libelle(rai: User) -> None:
    p = typed.processus()
    o1 = typed.objet(processus=p, libelle="Objet A")
    ref = typed.version(annee=2025)
    r = _risque(ref, rai, p)
    cible = creer_version(annee=2026, libelle="2026", source=ref, by=rai)
    modifier_risque(cible.risques.get(code=r.code), objet_auditable=o1, by=rai)
    comp = comparer_versions(ref, cible)
    assert comp.modifies[0].changements["objet_auditable"] == (None, "Objet A")


def test_verrou_de_ligne_pris_sur_la_version(rai: User) -> None:
    v = typed.version()
    with CaptureQueriesContext(connection) as ctx:
        _risque(v, rai)
    assert any("FOR UPDATE" in q["sql"] for q in ctx.captured_queries)


@pytest.mark.django_db(transaction=True)
def test_numerotation_concurrente_sans_doublon() -> None:
    rai = make_user("RAI")
    v = typed.version()
    p = typed.processus(code="FEP")
    nb_threads = 6
    barriere = threading.Barrier(nb_threads)
    erreurs: list[BaseException] = []
    codes: list[str] = []

    def travailler() -> None:
        try:
            barriere.wait(timeout=10)
            r = creer_risque(
                version=CartographieVersion.objects.get(pk=v.pk),
                processus=p,
                libelle="x",
                probabilite=1,
                impact=1,
                by=rai,
            )
            codes.append(r.code)
        except BaseException as e:  # noqa: BLE001
            erreurs.append(e)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=travailler) for _ in range(nb_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not erreurs
    assert sorted(codes) == sorted(f"{n}-FEP-R{n}" for n in range(1, nb_threads + 1))
    assert Risque.objects.filter(version=v).count() == nb_threads

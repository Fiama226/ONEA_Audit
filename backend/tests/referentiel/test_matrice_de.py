from apps.referentiel.services import matrice_de


def test_matrice_de_25_cases_et_ordre() -> None:
    cellules = matrice_de([(5, 1, "R2"), (5, 1, "R1"), (1, 5, "R3")])
    assert len(cellules) == 25
    assert (cellules[0].probabilite, cellules[0].impact) == (5, 1)
    assert (cellules[4].probabilite, cellules[4].impact) == (5, 5)
    assert (cellules[-1].probabilite, cellules[-1].impact) == (1, 5)
    assert cellules[0].codes == ["R2", "R1"] and cellules[0].nombre == 2  # ordre reçu
    assert cellules[-1].codes == ["R3"]
    assert cellules[-1].score == 5
    assert sum(c.nombre for c in cellules) == 3


def test_matrice_de_vide() -> None:
    cellules = matrice_de([])
    assert len(cellules) == 25 and all(c.nombre == 0 and c.codes == [] for c in cellules)

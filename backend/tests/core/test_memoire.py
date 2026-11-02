from apps.core.memoire import memo_lecture, memoise


def test_hors_bloc_recalcule_toujours() -> None:
    appels: list[int] = []

    def calcul() -> int:
        appels.append(1)
        return len(appels)

    assert memoise("k", calcul) == 1
    assert memoise("k", calcul) == 2


def test_dans_bloc_calcule_une_fois_par_cle_puis_oublie() -> None:
    appels: list[int] = []

    def calcul() -> int:
        appels.append(1)
        return len(appels)

    with memo_lecture():
        assert memoise("a", calcul) == 1
        assert memoise("a", calcul) == 1
        assert memoise("b", calcul) == 2
    assert memoise("a", calcul) == 3  # le mémo n'a pas survécu au bloc


def test_memo_none_est_memorise() -> None:
    appels: list[int] = []

    def calcul() -> None:
        appels.append(1)

    with memo_lecture():
        memoise("n", calcul)
        memoise("n", calcul)
    assert len(appels) == 1

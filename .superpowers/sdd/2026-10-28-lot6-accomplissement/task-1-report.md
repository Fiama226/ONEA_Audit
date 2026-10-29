# Lot 6 T1 report
Reused from lot 5 T2: etape_changee signal, enregistrer_controles, ETAPES_GEREES (existing tests test_signals.py, test_livrables_extension.py).
Delta: acces.peut_valider_travaux (= peut_valider_jalon(...,13)) + 2 tests in tests/missions/test_acces.py.
Red: first run failed on a fixture error in my test (duplicate active supervisor), fixed; green after impl.
Checks: pytest missions+signatures+analyse 630 passed; ruff, format, mypy strict, makemigrations --check clean.

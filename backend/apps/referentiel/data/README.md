# Données de référence ONEA

`referentiel-onea.csv` : les 17 directions et 11 processus de
`docs/domaine/cartographie-risques-onea.md`, à charger explicitement avec
`python manage.py import_referentiel apps/referentiel/data/referentiel-onea.csv --user <login>`
(jamais automatiquement).

**À confirmer par l'ONEA** : seuls les codes et le libellé « Département Audit Interne » (DAI)
sont sourcés tels quels. Les autres noms de directions sont des développements des
indications entre parenthèses du document source (« DRH », « DM (Marchés) »...) et doivent
être validés avant mise en production.

"""Secrets lus dans des fichiers (lot 9, T17, D16), vérifiés dans un sous-processus propre."""

# ruff: noqa: S105  (valeurs factices de test)

import json
from pathlib import Path
from typing import Any

import pytest

from tests.test_prod_settings import PROD_ENV, load_prod

SONDE = """
import json
import django
django.setup()
from django.conf import settings
print(json.dumps({
    "secret_key": settings.SECRET_KEY,
    "fallbacks": settings.SECRET_KEY_FALLBACKS,
    "db_password": settings.DATABASES["default"]["PASSWORD"],
    "db_user": settings.DATABASES["default"]["USER"],
    "db_host": settings.DATABASES["default"]["HOST"],
    "redis_url": settings.REDIS_URL,
    "broker": settings.CELERY_BROKER_URL,
    "cache": settings.CACHES["default"]["LOCATION"],
    "email_password": settings.EMAIL_HOST_PASSWORD,
    "email_user": settings.EMAIL_HOST_USER,
    "oidc": settings.OIDC_RP_CLIENT_SECRET,
    "kc": settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET,
    "meili": settings.RECHERCHE["CLE"],
    "metrics": settings.METRICS_TOKEN,
}))
"""


def _ecrire(dossier: Path, nom: str, contenu: str) -> str:
    chemin = dossier / nom
    chemin.write_bytes(contenu.encode())
    return str(chemin)


def _sans(*noms: str) -> dict[str, str]:
    return {k: v for k, v in PROD_ENV.items() if k not in noms}


def _charger(env: dict[str, str]) -> dict[str, Any]:
    resultat = load_prod(env, SONDE)
    assert resultat.returncode == 0, resultat.stderr
    donnees: dict[str, Any] = json.loads(resultat.stdout.strip().splitlines()[-1])
    return donnees


def test_fichier_prioritaire_et_saut_de_ligne_final_retire(tmp_path: Path) -> None:
    env = {
        **PROD_ENV,
        "SECRET_KEY": "depuis-la-variable-" + "x" * 40,
        "SECRET_KEY_FILE": _ecrire(tmp_path, "sk", "cle-du-fichier-" + "y" * 40 + "\n"),
        "METRICS_TOKEN": "variable",
        "METRICS_TOKEN_FILE": _ecrire(tmp_path, "mt", "jeton-fichier\r\n"),
        "MEILI_MASTER_KEY_FILE": _ecrire(tmp_path, "mk", "cle-meili\n"),
        "OIDC_RP_CLIENT_SECRET_FILE": _ecrire(tmp_path, "oidc", "secret-oidc\n"),
        "KEYCLOAK_ADMIN_API_CLIENT_SECRET_FILE": _ecrire(tmp_path, "kc", "secret-kc\n"),
    }
    donnees = _charger(env)
    assert donnees["secret_key"] == "cle-du-fichier-" + "y" * 40
    assert donnees["metrics"] == "jeton-fichier"
    assert donnees["meili"] == "cle-meili"
    assert donnees["oidc"] == "secret-oidc"
    assert donnees["kc"] == "secret-kc"


def test_seul_le_saut_de_ligne_final_est_retire(tmp_path: Path) -> None:
    env = {**PROD_ENV, "METRICS_TOKEN_FILE": _ecrire(tmp_path, "mt", " a b \n\n")}
    assert _charger(env)["metrics"] == " a b "


def test_variable_utilisee_sans_fichier() -> None:
    donnees = _charger({**PROD_ENV, "METRICS_TOKEN": "par-variable"})
    assert donnees["metrics"] == "par-variable"
    assert donnees["kc"] == "prod-sync-secret"


@pytest.mark.parametrize(
    "nom",
    [
        "SECRET_KEY",
        "METRICS_TOKEN",
        "MEILI_MASTER_KEY",
        "OIDC_RP_CLIENT_SECRET",
        "KEYCLOAK_ADMIN_API_CLIENT_SECRET",
        "DATABASE_PASSWORD",
        "REDIS_PASSWORD",
        "EMAIL_PASSWORD",
        "SECRET_KEY_FALLBACKS",
    ],
)
def test_fichier_absent_nomme_la_variable(tmp_path: Path, nom: str) -> None:
    manquant = str(tmp_path / "inexistant")
    resultat = load_prod({**PROD_ENV, f"{nom}_FILE": manquant}, SONDE)
    assert resultat.returncode != 0
    assert "ImproperlyConfigured" in resultat.stderr
    assert f"{nom}_FILE" in resultat.stderr


def test_la_valeur_du_secret_n_apparait_pas_dans_les_erreurs(tmp_path: Path) -> None:
    env = {
        **PROD_ENV,
        "MEILI_MASTER_KEY_FILE": _ecrire(tmp_path, "mk", "CHANGE_ME_valeur-secrete-xyz\n"),
    }
    resultat = load_prod(env, SONDE)
    assert resultat.returncode != 0
    assert "MEILI_MASTER_KEY" in resultat.stderr
    assert "valeur-secrete-xyz" not in resultat.stderr


def test_base_et_redis_construits_depuis_les_composants(tmp_path: Path) -> None:
    mdp_base = "p@ss/w:rd#1"
    env = {
        **_sans("DATABASE_URL"),
        "DATABASE_URL": "postgres://onea_app@db:5432/onea",
        "DATABASE_PASSWORD_FILE": _ecrire(tmp_path, "db", mdp_base + "\n"),
        "REDIS_URL": "redis://redis:6379/0",
        "REDIS_PASSWORD_FILE": _ecrire(tmp_path, "redis", "r@dis:pw\n"),
    }
    donnees = _charger(env)
    assert donnees["db_password"] == mdp_base
    assert donnees["db_user"] == "onea_app"
    assert donnees["db_host"] == "db"
    # Mot de passe encodé : l'URL reste analysable malgré les caractères spéciaux.
    assert donnees["redis_url"] == "redis://:r%40dis%3Apw@redis:6379/0"
    assert donnees["broker"] == donnees["redis_url"]
    assert donnees["cache"] == "redis://:r%40dis%3Apw@redis:6379/1"


def test_mot_de_passe_fichier_remplace_celui_de_l_url(tmp_path: Path) -> None:
    env = {
        **PROD_ENV,
        "DATABASE_URL": "postgres://u:ancien@db:5432/onea",
        "DATABASE_PASSWORD_FILE": _ecrire(tmp_path, "db", "nouveau\n"),
        "REDIS_URL": "redis://:ancien@redis:6379/0",
        "REDIS_PASSWORD_FILE": _ecrire(tmp_path, "redis", "nouveau\n"),
    }
    donnees = _charger(env)
    assert donnees["db_password"] == "nouveau"
    assert donnees["redis_url"] == "redis://:nouveau@redis:6379/0"


def test_mot_de_passe_smtp_fichier_prioritaire_sur_l_url(tmp_path: Path) -> None:
    env = {**PROD_ENV, "EMAIL_PASSWORD_FILE": _ecrire(tmp_path, "smtp", "mdp-du-fichier\n")}
    donnees = _charger(env)
    assert donnees["email_password"] == "mdp-du-fichier"
    assert donnees["email_user"] == "user"


def test_mot_de_passe_smtp_de_l_url_si_fichier_vide(tmp_path: Path) -> None:
    env = {**PROD_ENV, "EMAIL_PASSWORD_FILE": _ecrire(tmp_path, "smtp", "\n")}
    assert _charger(env)["email_password"] == "pw"


def test_anciennes_cles_acceptees_pendant_la_rotation(tmp_path: Path) -> None:
    env = {
        **PROD_ENV,
        "SECRET_KEY_FALLBACKS_FILE": _ecrire(tmp_path, "fb", "ancienne-1\nancienne-2\n"),
    }
    assert _charger(env)["fallbacks"] == ["ancienne-1", "ancienne-2"]


@pytest.mark.parametrize(
    "variable",
    [
        "SECRET_KEY",
        "METRICS_TOKEN",
        "MEILI_MASTER_KEY",
        "OIDC_RP_CLIENT_SECRET",
        "KEYCLOAK_ADMIN_API_CLIENT_SECRET",
    ],
)
def test_valeur_change_me_refusee_en_production(variable: str) -> None:
    env = {**PROD_ENV, variable: "CHANGE_ME_a_remplacer"}
    resultat = load_prod(env, SONDE)
    assert resultat.returncode != 0
    assert "ImproperlyConfigured" in resultat.stderr


def test_change_me_refuse_aussi_depuis_un_fichier(tmp_path: Path) -> None:
    env = {**PROD_ENV, "SECRET_KEY_FILE": _ecrire(tmp_path, "sk", "CHANGE_ME_cle\n")}
    resultat = load_prod(env, SONDE)
    assert resultat.returncode != 0
    assert "SECRET_KEY" in resultat.stderr


def test_change_me_refuse_pour_les_mots_de_passe_de_connexion(tmp_path: Path) -> None:
    for env in (
        {**PROD_ENV, "DATABASE_URL": "postgres://u:CHANGE_ME_x@db:5432/onea"},
        {**PROD_ENV, "REDIS_URL": "redis://:CHANGE_ME_x@redis:6379/0"},
        {**PROD_ENV, "EMAIL_URL": "smtp://user:CHANGE_ME_x@smtp.onea.bf:587"},
        {**PROD_ENV, "DATABASE_PASSWORD_FILE": _ecrire(tmp_path, "d", "CHANGE_ME_x\n")},
    ):
        resultat = load_prod(env, SONDE)
        assert resultat.returncode != 0, env
        assert "ImproperlyConfigured" in resultat.stderr


def test_secret_key_vide_refuse(tmp_path: Path) -> None:
    env = {**PROD_ENV, "SECRET_KEY_FILE": _ecrire(tmp_path, "sk", "\n")}
    resultat = load_prod(env, SONDE)
    assert resultat.returncode != 0
    assert "SECRET_KEY" in resultat.stderr

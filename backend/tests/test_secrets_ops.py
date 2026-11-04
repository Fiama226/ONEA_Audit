"""Secrets d'exploitation (lot 9, T17, D16) : générateur, Compose, modèles et détection de fuite.

Vérifications sans Docker réel (le banc `scripts/recette/tests/secrets.sh` couvre `docker inspect`
sur la pile de recette). Les tests de droits POSIX sont ignorés sous Windows.
"""

import os
import re
import shutil
import stat
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

RACINE = Path(__file__).resolve().parents[2]
GENERATEUR = RACINE / "scripts" / "generer-secrets.sh"
COMPOSE = RACINE / "docker" / "compose.prod.yml"

pytestmark = pytest.mark.skipif(not GENERATEUR.exists(), reason="dépôt complet absent")

SECRETS = [
    "secret_key",
    "secret_key_fallbacks",
    "postgres_password",
    "postgres_app_password",
    "redis_password",
    "meili_master_key",
    "metrics_token",
    "email_password",
]
POSIX = os.name == "posix"


def _sh() -> str | None:
    trouve = shutil.which("sh")
    if trouve:
        return trouve
    git = Path(r"C:\Program Files\Git\usr\bin\sh.exe")
    return str(git) if git.exists() else None


SH = _sh()
besoin_sh = pytest.mark.skipif(SH is None, reason="sh introuvable")
besoin_posix = pytest.mark.skipif(not POSIX, reason="droits POSIX requis")


def _lancer(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    assert SH is not None
    base = {k: v for k, v in os.environ.items() if k != "ONEA_SECRETS_DIR"}
    # Git pour Windows : les utilitaires (mkdir, od, tr...) vivent à côté de sh.exe.
    base["PATH"] = str(Path(SH).parent) + os.pathsep + base.get("PATH", "")
    return subprocess.run(  # noqa: S603
        [SH, str(GENERATEUR), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**base, **(env or {})},
        timeout=60,
        check=False,
    )


def _arg(chemin: Path) -> str:
    """Chemin passé à sh : sous Windows, forme MSYS (`/c/Users/...`) du sh de Git."""
    posix = chemin.as_posix()
    if os.name == "nt" and re.match(r"^[A-Za-z]:/", posix):
        return f"/{posix[0].lower()}{posix[2:]}"
    return posix


# --- Générateur ------------------------------------------------------------------------------


@besoin_sh
def test_syntaxe_des_scripts() -> None:
    assert SH is not None
    for nom in (
        "scripts/generer-secrets.sh",
        "scripts/recette/up.sh",
        "scripts/recette/lib.sh",
        "scripts/recette/tests/secrets.sh",
    ):
        r = subprocess.run(  # noqa: S603
            [SH, "-n", str(RACINE / nom)], capture_output=True, text=True, check=False
        )
        assert r.returncode == 0, f"{nom} : {r.stderr}"


@besoin_sh
def test_cree_tous_les_fichiers_sans_afficher_de_valeur(tmp_path: Path) -> None:
    dossier = tmp_path / "secrets"
    r = _lancer("--dossier", _arg(dossier), "--sans-proprietaire")
    assert r.returncode == 0, r.stderr
    for nom in SECRETS:
        f = dossier / nom
        assert f.is_file(), nom
        contenu = f.read_text()
        if nom in {"email_password", "secret_key_fallbacks"}:
            assert contenu == ""
            continue
        valeur = contenu.rstrip("\n")
        assert re.fullmatch(r"[0-9a-f]{64}", valeur) or (
            nom == "secret_key" and re.fullmatch(r"[0-9a-f]{96}", valeur)
        ), nom
        assert valeur not in r.stdout + r.stderr
    vides = {"email_password", "secret_key_fallbacks"}
    valeurs = [(dossier / n).read_text() for n in SECRETS if n not in vides]
    assert len(set(valeurs)) == len(valeurs)  # tous distincts


@besoin_sh
def test_ne_reecrit_jamais_un_fichier_existant(tmp_path: Path) -> None:
    dossier = tmp_path / "secrets"
    dossier.mkdir()
    (dossier / "secret_key").write_text("valeur-existante\n")
    (dossier / "metrics_token").write_text("")  # existant, même vide
    r = _lancer("--dossier", _arg(dossier), "--sans-proprietaire")
    assert r.returncode == 0, r.stderr
    assert (dossier / "secret_key").read_text() == "valeur-existante\n"
    assert (dossier / "metrics_token").read_text() == ""
    avant = {n: (dossier / n).read_text() for n in SECRETS}
    r2 = _lancer("--dossier", _arg(dossier), "--sans-proprietaire")
    assert r2.returncode == 0
    assert {n: (dossier / n).read_text() for n in SECRETS} == avant
    assert "0 créé" in r2.stdout


@besoin_sh
def test_ne_suit_pas_un_lien_symbolique_existant(tmp_path: Path) -> None:
    dossier = tmp_path / "secrets"
    dossier.mkdir()
    cible = tmp_path / "cible"
    cible.write_text("intact")
    try:
        (dossier / "redis_password").symlink_to(cible)
    except (OSError, NotImplementedError):
        pytest.skip("liens symboliques indisponibles")
    r = _lancer("--dossier", _arg(dossier), "--sans-proprietaire")
    assert r.returncode == 0
    assert cible.read_text() == "intact"


@besoin_sh
def test_dossier_obligatoire_et_absolu(tmp_path: Path) -> None:
    assert _lancer().returncode == 2
    assert _lancer("--dossier", "relatif/secrets").returncode == 2
    assert _lancer("--dossier", _arg(tmp_path), "--proprietaire", "root").returncode == 2


@besoin_sh
def test_dossier_par_variable_d_environnement(tmp_path: Path) -> None:
    dossier = tmp_path / "via-env"
    r = _lancer("--sans-proprietaire", env={"ONEA_SECRETS_DIR": _arg(dossier)})
    assert r.returncode == 0, r.stderr
    assert (dossier / "secret_key").is_file()


@besoin_sh
@besoin_posix
def test_dossier_0700_fichiers_0600(tmp_path: Path) -> None:
    dossier = tmp_path / "secrets"
    r = _lancer("--dossier", _arg(dossier), "--sans-proprietaire")
    assert r.returncode == 0, r.stderr
    assert stat.S_IMODE(dossier.stat().st_mode) == 0o700
    for nom in SECRETS:
        assert stat.S_IMODE((dossier / nom).stat().st_mode) == 0o600, nom


@besoin_sh
@besoin_posix
def test_verification_detecte_les_ecarts(tmp_path: Path) -> None:
    dossier = tmp_path / "secrets"
    _lancer("--dossier", _arg(dossier), "--sans-proprietaire")
    assert _lancer("--verifier", "--dossier", _arg(dossier)).returncode == 0

    (dossier / "redis_password").chmod(0o644)
    r = _lancer("--verifier", "--dossier", _arg(dossier))
    assert r.returncode == 1 and "redis_password" in r.stderr
    (dossier / "redis_password").chmod(0o600)

    (dossier / "metrics_token").write_text("CHANGE_ME_x\n")
    r = _lancer("--verifier", "--dossier", _arg(dossier))
    assert r.returncode == 1 and "metrics_token" in r.stderr
    (dossier / "metrics_token").write_text("ok\n")

    (dossier / "meili_master_key").write_text("")
    r = _lancer("--verifier", "--dossier", _arg(dossier))
    assert r.returncode == 1 and "meili_master_key" in r.stderr
    (dossier / "meili_master_key").write_text("ok\n")

    (dossier / "secret_key").unlink()
    r = _lancer("--verifier", "--dossier", _arg(dossier))
    assert r.returncode == 1 and "secret_key" in r.stderr


# --- Compose, modèles, détection de fuite ----------------------------------------------------


def _compose() -> dict[str, Any]:
    yaml = pytest.importorskip("yaml")
    data: dict[str, Any] = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return data


def test_compose_declare_les_secrets_et_chaque_service_les_monte() -> None:
    compose = _compose()
    assert set(compose["secrets"]) == set(SECRETS)
    for definition in compose["secrets"].values():
        assert definition["file"].startswith("${ONEA_SECRETS_DIR")
    services = compose["services"]
    for nom in ("web", "worker", "beat", "migrate", "db", "redis", "meilisearch"):
        env = services[nom].get("environment", {})
        for cle, valeur in env.items():
            if cle.endswith("_FILE"):
                secret = str(valeur).rsplit("/", 1)[-1]
                assert secret in services[nom]["secrets"], f"{nom} : {cle} sans secret monté"
    # Chaque secret déclaré est utilisé par au moins un service.
    montes = {s for svc in services.values() for s in svc.get("secrets", [])}
    assert montes == set(SECRETS)


def test_compose_sans_secret_en_clair_dans_l_environnement() -> None:
    services = _compose()["services"]
    interdits = {
        "SECRET_KEY",
        "SECRET_KEY_FALLBACKS",
        "POSTGRES_PASSWORD",
        "POSTGRES_APP_PASSWORD",
        "REDIS_PASSWORD",
        "MEILI_MASTER_KEY",
        "METRICS_TOKEN",
        "EMAIL_PASSWORD",
        "DATABASE_PASSWORD",
    }
    for nom, service in services.items():
        env = service.get("environment", {})
        assert not interdits & set(env), f"{nom} : secret en clair dans l'environnement"
    # Aucune interpolation de variable de secret dans le fichier.
    texte = COMPOSE.read_text(encoding="utf-8")
    for ref in re.findall(r"\$\{([A-Z_]+)", texte):
        if re.search(r"PASSWORD|SECRET|TOKEN|_KEY", ref):
            assert ref == "ONEA_SECRETS_DIR", ref
    # Les URL de connexion ne contiennent plus de mot de passe.
    for nom in ("web", "worker", "beat", "migrate"):
        for cle in ("DATABASE_URL", "REDIS_URL"):
            valeur = re.sub(r"\$\{[^}]*\}", "X", str(services[nom]["environment"][cle]))
            assert not re.search(r"://[^/@]*:[^/@]*@", valeur), f"{nom} : {cle}"


def test_valkey_ne_recoit_pas_le_mot_de_passe_en_argument() -> None:
    redis = _compose()["services"]["redis"]
    commande = " ".join(redis["entrypoint"]) + " " + str(redis.get("command", ""))
    assert "--requirepass" not in commande
    assert "/run/secrets/redis_password" in commande
    assert "/run/secrets/redis_password" in str(redis["healthcheck"]["test"])


def test_modele_de_production_sans_secret() -> None:
    lignes = (RACINE / ".env.prod.example").read_text(encoding="utf-8").splitlines()
    for ligne in lignes:
        if ligne.lstrip().startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        if cle == "ONEA_SECRETS_DIR":
            continue
        if re.search(r"PASSWORD|SECRET|TOKEN|_KEY$", cle):
            raise AssertionError(f"{cle} ne doit pas figurer dans .env.prod.example")
        if "CHANGE_ME" in valeur:
            raise AssertionError(cle)
    assert any(ligne.startswith("ONEA_SECRETS_DIR=") for ligne in lignes)
    # Le mot de passe SMTP n'est plus dans l'URL du modèle.
    url = next(ligne for ligne in lignes if ligne.startswith("EMAIL_URL="))
    assert not re.search(r"://[^/@]*:[^/@]*@", url)


def test_modele_de_recette_sans_secret_applicatif() -> None:
    texte = (RACINE / ".env.recette.example").read_text(encoding="utf-8")
    for cle in (
        "SECRET_KEY",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "MEILI_MASTER_KEY",
    ):
        assert not re.search(rf"^{cle}=", texte, re.MULTILINE), cle
    assert "ONEA_SECRETS_DIR=" in texte


def test_gitleaks_configure_en_local_et_en_ci() -> None:
    config = tomllib.loads((RACINE / ".gitleaks.toml").read_text(encoding="utf-8"))
    assert config["extend"]["useDefault"] is True
    assert config["allowlists"], "exceptions attendues (valeurs de développement listées)"
    precommit = (RACINE / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "github.com/gitleaks/gitleaks" in precommit and "id: gitleaks" in precommit
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "gitleaks" in ci and "git --redact" in ci
    assert re.search(r"gitleaks:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}", ci)


def test_gitignore_protege_les_fichiers_de_secrets() -> None:
    texte = (RACINE / ".gitignore").read_text(encoding="utf-8")
    assert ".env.*" in texte and "secrets/" in texte


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker introuvable")
def test_compose_config_valide_avec_un_environnement_factice(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "certs").mkdir()
    env = tmp_path / "env"
    env.write_text(
        "\n".join(
            [
                f"ONEA_SECRETS_DIR={(tmp_path / 's').as_posix()}",
                "PUBLIC_HOST=audit.example.org",
                f"TLS_CERT_DIR={(tmp_path / 'certs').as_posix()}",
                "APP_VERSION=1.0.0",
                "EMAIL_URL=smtp+tls://user@smtp.example.org:587",
                f"DOCUMENTS_HOST_DIR={(tmp_path / 'docs').as_posix()}",
            ]
        )
    )
    docker = shutil.which("docker") or "docker"
    r = subprocess.run(  # noqa: S603
        [docker, "compose", "--env-file", str(env), "-f", str(COMPOSE), "config", "-q"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if r.returncode != 0 and "Cannot connect" in r.stderr:
        pytest.skip("daemon docker indisponible")
    assert r.returncode == 0, r.stderr
    # Sans ONEA_SECRETS_DIR, Compose refuse de démarrer (jamais de dossier implicite).
    env.write_text(env.read_text().replace("ONEA_SECRETS_DIR=", "AUTRE="))
    sans = subprocess.run(  # noqa: S603
        [docker, "compose", "--env-file", str(env), "-f", str(COMPOSE), "config", "-q"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={k: v for k, v in os.environ.items() if k != "ONEA_SECRETS_DIR"},
    )
    assert sans.returncode != 0 and "ONEA_SECRETS_DIR" in sans.stderr
